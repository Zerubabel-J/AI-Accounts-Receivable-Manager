# Build Spec — AI Accounts Receivable Manager

> Engineer-facing detail. The SRS is for Kidus; this is for whoever is writing code (us). This is the build checklist.

---

## 1. Data model (Google Sheets schema)

Three sheets in one spreadsheet.

### Sheet: `invoices`

| Column | Type | Notes |
|---|---|---|
| `invoice_id` | string | `INV-0001`, generated, primary key |
| `customer_name` | string | "Sarah Chen" |
| `business_name` | string | "Acme Corp" |
| `email` | string | normalized lowercase |
| `phone` | string | digits only, optional |
| `amount` | number | dollars, 2 decimals |
| `issued_date` | ISO date | `2025-01-15` |
| `due_date` | ISO date | issued + net terms |
| `status` | enum | `sent` \| `overdue` \| `paid` \| `at_risk` |
| `risk_score` | number | 0-100, set by AI |
| `risk_reason` | string | short explanation, set by AI |
| `reminder_count` | number | how many reminders sent |
| `last_reminder_at` | ISO datetime | nullable |
| `paid_at` | ISO datetime | nullable, set when status -> paid |
| `matched_payment_id` | string | nullable |

### Sheet: `payments`

| Column | Type | Notes |
|---|---|---|
| `payment_id` | string | `PAY-0001` or Stripe ID |
| `source` | enum | `stripe` \| `manual` |
| `payer_name` | string | from Stripe charge |
| `payer_email` | string | normalized lowercase |
| `amount` | number | dollars |
| `received_at` | ISO datetime | |
| `matched_invoice_id` | string | nullable |
| `match_confidence` | number | 0-1 |
| `match_reasoning` | string | set by AI |
| `match_status` | enum | `confirmed` \| `needs_review` \| `no_match` |
| `reviewed_by_user` | boolean | true when human approves |

### Sheet: `activity`

Append-only audit log. `timestamp | invoice_id | action | actor | details`.

---

## 2. Backend API surface (FastAPI)

### Routes

```
GET    /health                       -> {"status": "ok"}

# Invoices
GET    /invoices                     -> list (filterable by status)
POST   /invoices                     -> create
GET    /invoices/{id}                -> detail
PATCH  /invoices/{id}                -> update status / fields
POST   /invoices/{id}/send-reminder  -> send reminder now (manual)

# Payments
GET    /payments                     -> list
POST   /payments                     -> manual payment entry (testing)

# Smart Match / Review
GET    /review-queue                 -> payments with match_status=needs_review
POST   /review-queue/{payment_id}/approve -> confirm match
POST   /review-queue/{payment_id}/reject  -> reject and re-match

# Dashboard stats
GET    /stats                        -> { collected, outstanding, at_risk, dso, recovered_revenue }

# Webhooks
POST   /webhooks/stripe              -> Stripe payment events

# Cron jobs (require Bearer token)
POST   /jobs/run-reminders           -> daily reminder sweep
POST   /jobs/run-daily-summary       -> daily summary email
```

### Module layout

```
backend/
  app/
    main.py                  # FastAPI app, route registration
    config.py                # env vars, settings (pydantic-settings)
    deps.py                  # dependency-injection (auth, sheets client)
    models/
      invoice.py             # pydantic models
      payment.py
      stats.py
    routers/
      invoices.py
      payments.py
      review.py
      stats.py
      webhooks.py
      jobs.py
    services/
      smart_match.py         # THE core engine (TDD here)
      reminder.py            # reminder cadence logic
      daily_summary.py       # daily summary builder
      risk_scoring.py        # client risk calculation
    integrations/
      sheets.py              # Google Sheets client
      gemini.py              # Gemini API client
      gmail.py               # Gmail API client
      stripe_client.py       # Stripe verification
  tests/
    test_smart_match.py      # full TDD coverage
    test_jobs_auth.py        # cron-secret auth
    conftest.py
  pyproject.toml
  .env.example
```

---

## 3. Smart Match — the core engine

This is the function the demo lives or dies on. Treat it as the heart.

### Signature

```python
def smart_match(payment: Payment, open_invoices: list[Invoice]) -> MatchResult:
    ...

class MatchResult(BaseModel):
    invoice_id: str | None
    confidence: float           # 0..1
    status: Literal["confirmed", "needs_review", "no_match"]
    reasoning: str
    method: Literal["exact_email", "exact_business", "fuzzy_ai", "none"]
```

### Algorithm

1. **Exact email match** on `payer_email == invoice.email`
   - If 1 match and amount matches: `confirmed`, confidence 1.0, method `exact_email`
   - If multiple matches: pass to step 3 (fuzzy) with these as candidates

2. **Exact business name match** (normalized: lowercase, strip "LLC/Inc/Corp/Co", strip whitespace)
   - If 1 match and amount within 5%: `confirmed`, confidence 0.95, method `exact_business`

3. **Fuzzy AI judgment** — call Gemini with payment + top-5 candidate invoices (filtered by amount within +/-10%)
   - Prompt asks Gemini to return JSON: `{invoice_id, confidence, reasoning}` for the best match, or `null`
   - Parse defensively (LLMs return malformed JSON occasionally)
   - confidence >= 0.85 -> `confirmed`
   - 0.6 <= confidence < 0.85 -> `needs_review`
   - confidence < 0.6 -> `no_match`

4. **Reconciliation safeguards** (run before returning `confirmed`)
   - Amount must match within +/-1% (catch partial payments -> `needs_review`)
   - Invoice must not already be `paid` (catch duplicates -> `needs_review`)
   - Payment must not already be matched (catch duplicates -> `no_match` with reasoning)

### Test cases (write these FIRST)

| # | Scenario | Expected |
|---|---|---|
| 1 | Email matches exactly, amount matches | confirmed, exact_email |
| 2 | Email matches, amount $5 off on $1000 (0.5%) | confirmed (within tolerance) |
| 3 | Email matches, amount $200 off on $1000 (20%) | needs_review (partial?) |
| 4 | Business name matches exactly with "LLC" suffix on one side | confirmed, exact_business |
| 5 | Email and business both differ, but Gemini says 0.92 confidence | confirmed, fuzzy_ai |
| 6 | Email/business differ, Gemini returns 0.7 | needs_review |
| 7 | Email/business differ, Gemini returns 0.4 | no_match |
| 8 | Invoice is already paid | needs_review (duplicate?) with reasoning |
| 9 | Gemini returns malformed JSON | falls back to no_match gracefully |
| 10 | Two invoices have same email; amounts disambiguate | confirmed on amount-matching one |

---

## 4. Reminder cadence

Daily cron sweeps `invoices` where `status in ('sent', 'overdue')`.

Per invoice, decide whether to send a reminder today:

| Days past due | reminder_count | Action |
|---|---|---|
| 0 (due today) | 0 | Send "friendly" reminder, count -> 1, status -> overdue |
| 7 | 1 | Send "firmer" reminder, count -> 2 |
| 14 | 2 | Send "escalation" reminder (CC user), count -> 3 |
| 30+ | 3+ | Mark `at_risk`, do NOT auto-send. Surface in dashboard for human escalation. |

Email content: drafted by Gemini, parameterized on tone (friendly/firm/escalation), client name, invoice details, and client risk profile.

**Demo override:** all reminders are dry-run by default — they show in Activity log but don't actually send unless `SEND_EMAILS_FOR_REAL=true`. This protects demo recordings.

---

## 5. Daily Summary

Runs once per day. Builds and emails a summary to the user.

Content:
- Collected yesterday: `$X across N invoices`
- Outstanding total: `$Y across N invoices`
- Cash at Risk: `$Z across N invoices`
- Needs Review: `N items`
- High-risk clients flagged: `up to 3, with one-line reason each`
- Link to dashboard

Template: HTML email, simple branded layout. Send via Gmail API.

---

## 6. Risk scoring

For each client (grouped by email), look at their last N invoices:
- Average days late
- Variance (consistent late vs erratic)
- Worsening trend (last 3 vs prior 3)

Compose into a 0-100 score; >= 70 is "high risk."

The score itself is deterministic; Gemini writes the human-readable reason: "Late on 4 of last 5 invoices; average 23 days; trend worsening."

---

## 7. Frontend (Next.js) screens

### `/` Dashboard
Top stats row (4 cards):
1. Collected (last 30 days) - $X (green)
2. Outstanding - $Y across N invoices (neutral)
3. Cash at Risk - $Z across N invoices (red)
4. DSO - days, vs target (with delta arrow)

Below, two columns:
- **Left:** Needs Review queue (top 5, click to expand)
- **Right:** High-risk client watchlist with reasoning

Bottom: Recovered Revenue counter ("**$12,840 recovered this month** by AI follow-ups")

### `/invoices` Invoices
Table: id, customer, business, amount, due_date, status badge, risk_score
- Filters: status, search by name
- Row click -> drawer with full detail + activity log
- Inline actions: Send Reminder, Mark Paid

### `/review` Review Queue
For each `needs_review` payment:
- Side-by-side: payment vs candidate invoice
- Confidence bar + AI reasoning text
- Buttons: Approve, Reject (with re-match), Skip

### `/settings` Settings (mostly placeholder for demo)
- Connect Stripe / Connect Gmail (show OAuth status)
- Reminder cadence sliders
- Risk threshold

---

## 8. Build order (the real timeline)

| Hours | Phase | What |
|---|---|---|
| 0:00-0:45 | Setup | Dirs, .gitignore, CLAUDE.md, BUILD_SPEC, scaffolds, first commit |
| 0:45-2:00 | Backend foundation | FastAPI scaffold, config, Sheets client, models, seed.py |
| 2:00-3:30 | Smart Match (TDD) | Write tests, implement engine, all 10 cases pass |
| 3:30-4:15 | Stripe webhook | Endpoint, signature verification, end-to-end with `stripe trigger` |
| 4:15-5:30 | Frontend foundation | Next.js, Tailwind, shadcn, layout, API client, mock data render |
| 5:30-6:30 | Frontend screens | Dashboard, Invoices, Review Queue with real backend data |
| 6:30-7:15 | Crons | Reminder + Daily Summary endpoints, deploy to Render, set up Cloud Scheduler |
| 7:15-8:00 | Value moves | Recovered Revenue counter, AI explanation popovers |
| 8:00-9:00 | Polish + demo prep | Realistic seed data, dry-run the demo end-to-end |
| 9:00-11:00 | Video + README | Record demo, write README, push final commits |

---

## 9. Demo script (5 minutes)

Pre-recording: wake Render backend by hitting `/health`. Make sure seed data is loaded.

| Time | Beat |
|---|---|
| 0:00-0:30 | Hook: "AR is the most boring, most expensive problem at every B2B SMB. I built an AI that does it." |
| 0:30-1:15 | Open dashboard. Walk through the 4 top stats. Point out Cash at Risk and Recovered Revenue. |
| 1:15-2:30 | Live: trigger a Stripe test payment via CLI. Watch it land in the dashboard. Smart Match auto-confirms with reasoning visible. |
| 2:30-3:30 | Trigger an "ambiguous" payment (different email, similar business name). Show it landing in Review Queue with AI's reasoning. Click Approve. |
| 3:30-4:15 | Open the Daily Summary email in Gmail (pre-fired). Show what arrives in user's inbox each morning. |
| 4:15-4:45 | Quick architecture walkthrough — show repo, point to Smart Match engine, point to seeded test cases. |
| 4:45-5:00 | Close: "Same engine scales to enterprise. This MVP proves the core intelligence." |

---

## 10. Pre-flight checklist (before recording)

- [ ] Backend deployed and warm
- [ ] Frontend deployed and pointed at backend
- [ ] Cloud Scheduler jobs enabled
- [ ] Stripe CLI authenticated, sandbox key set
- [ ] Gmail OAuth completed
- [ ] Seed data loaded (~80 invoices, mixed states)
- [ ] `SEND_EMAILS_FOR_REAL=true` for one rehearsal, then back to false
- [ ] Test all 3 demo payment scenarios in dry-run
