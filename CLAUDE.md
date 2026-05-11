# Project: AI Accounts Receivable Manager

> **Brain3 Level-1 Assignment** - 1-day project. Approved scope by Kidus (kidus@brain3.ai). 

## What this project is

An autonomous AI agent that handles Accounts Receivable for B2B companies (SMB to mid-market). It watches incoming payments, matches them to open invoices using a hybrid deterministic + AI engine, sends calibrated follow-up emails to late payers, and gives the user a daily summary of cash collected, cash at risk, and items needing review.

**Target user:** Controller / AR Manager / founder at a 10-200 person B2B company.

**The pitch:** replaces $5K-$15K/mo of manual AR work + $500/mo of legacy software (HighRadius, Versapay) with a $99-$499/mo tool. The user only handles judgment calls; the agent handles the routine 80%.

## Stack (locked)

| Layer | Tech | Notes |
|---|---|---|
| Frontend | Next.js 15 (App Router) + Tailwind + shadcn/ui | TypeScript |
| Backend | FastAPI (Python 3.11+) | async, typed |
| AI | Google Gemini 2.5 Flash | free tier, ~1500 req/day |
| Database | Google Sheets (via Sheets API) | transparent for demo |
| Payments | Stripe sandbox + webhooks | Stripe CLI for local dev |
| Email | Gmail API (OAuth) | sends from user's address |
| Cron | GCP Cloud Scheduler | 3 free jobs/mo, we use 2 |
| Hosting | Vercel (frontend) + Render (backend) | both free tier |

## Repo layout

```
/frontend       Next.js app
/backend        FastAPI app
/docs           SRS, architecture notes, build spec
/scripts        seed.py and other one-offs
README.md       project overview + run instructions
CLAUDE.md       this file
```

## Core workflow (the mental model)

```
INVOICE -> WAIT -> PAYMENT -> SMART MATCH -> UPDATE -> NOTIFY
                                  ^
                            AI lives here
```

**Smart Match** is the core engine. Given an incoming payment, it must decide if it pays an existing invoice. Output is one of three:

- **Confirmed** (high confidence, auto-match) -> update invoice to Paid
- **Needs Review** (medium confidence) -> surface in Review Queue with reasoning
- **No Match** (low confidence) -> AI drafts an outreach email asking the payer

Smart Match cascade:
1. Exact email match -> verify amount -> Confirmed
2. Exact business name match -> verify amount -> Confirmed
3. Fuzzy match (Gemini-judged on email + name + phone + amount) -> Confirmed if confidence >= 0.85, Needs Review if 0.6-0.85, No Match if < 0.6
4. Reconciliation checks (always): amount sane, not a duplicate, not already paid

## Invoice states

- **Sent** (yellow) - issued, not yet due
- **Overdue** (blue) - past due date, in reminder flow
- **Paid** (green) - matched and confirmed
- **At Risk** (red) - 3+ reminders ignored, or flagged by risk score

## Conventions

### Backend (Python)
- Python 3.11+, async-first
- Type hints everywhere; pydantic for I/O models
- One file = one responsibility (no god-modules)
- All external API calls in dedicated modules under `backend/integrations/`
- Tests use pytest; only the Smart Match engine gets full TDD; everything else gets light smoke coverage
- Format: `ruff format` (don't bikeshed style)
- No print statements; use `logging`

### Frontend (TypeScript)
- Next.js 15 App Router, server components by default
- Use shadcn/ui components; don't reinvent buttons/cards
- Tailwind utility classes inline; no CSS modules
- API calls go through `frontend/lib/api.ts` - one place to swap base URL for dev/prod
- Format: Prettier defaults

### Git
- Commit often, small commits with imperative messages
- Branch: `main` (solo build, no PR review)
- Never commit secrets; always use `.env`

## Hard rules (don't break these)

1. **Never send a real email without user approval.** Drafts only; human-in-the-loop for everything outbound to clients.
2. **Stripe stays in test mode.** No real money flows.
3. **Cron endpoints must require a shared secret in the Authorization header.** Public URLs are exposed.
4. **Gemini outputs must be parsed defensively.** Always assume the LLM returns malformed JSON sometimes; have a fallback.
5. **Keep the demo seed data realistic.** ~80 invoices, ~$340K outstanding, mix of states. Empty UIs ruin the demo.

## What we are NOT building (out of scope for the day)

- Multi-tenancy / accounts / login (single hardcoded user)
- ACH / Plaid / bank-feed integration (Stripe only)
- QuickBooks / Xero sync (CSV import + Sheets only)
- Mobile app
- Payment processing (we observe payments, don't initiate them)
- Audit-grade compliance / accounting software replacement

## The "more valuable" angle

The more valuable, the better. Two specific value moves we are building:

1. **Recovered Revenue counter** on the dashboard - "$12,840 recovered this month by AI follow-ups." Turns the tool into an ROI story.
2. **AI explanations everywhere** - every flag, match, and risk score has a one-click "why?" expansion showing Gemini's reasoning. Makes the agent feel transparent, not magical.

## Files and references

- `docs/SRS.md` - the approved spec sent to the reviewer 
- `docs/BUILD_SPEC.md` - engineer-facing detail (endpoints, screens, Smart Match cases)
- `scripts/seed.py` - generates realistic demo data
