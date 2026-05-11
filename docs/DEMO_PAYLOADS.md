# Demo Cheat Sheet — Smart Match cases

Open these three tabs side by side:

- API docs:   <http://127.0.0.1:8000/docs>
- Dashboard:  <http://localhost:3000>
- Sheet:      your Google Sheet

In the API docs, scroll to **POST /invoices/{invoice_id}/pay** → click **Try it out**.

For each case below: put the `invoice_id` in the path field, paste the JSON
into the body, click **Execute**, then switch to the Sheet (refresh) and the
Dashboard to show what changed.

---

## Run the tests first (1 line, 16 pass)

```bash
cd backend && .venv/bin/python -m pytest -v
```

Expected: **16 passed in ~0.3s**. Show this on screen before the live demo so the
audience sees the engine is covered by real tests before you start clicking.

---

## Case 1 — Exact match (email path) 🟢

**Invoice:** `INV-0048` (Aurora Systems, tomas@aurorasys.com, $7,500)

**Body:**
```json
{
  "payer_name": "Tomas Berg",
  "payer_email": "tomas@aurorasys.com",
  "amount": 7500
}
```

**Response:** `confirmed` · method `exact_email` · confidence **1.00**

**On the Sheet:**
- `INV-0048` status flips from `sent`/`overdue` to **paid**
- `paid_at` gets today's timestamp
- `matched_payment_id` gets the new `PAY-SIM-...` id
- A new row appears in the `payments` tab with this payment
- A new row appears in the `activity` tab: `auto_matched_via_pay_endpoint`

**On the Dashboard:**
- **Outstanding** drops by $7,500
- **Collected (30d)** rises by $7,500
- **Recovered Revenue (this month)** rises by $7,500

**Narration:** "Email matches the invoice exactly, amount matches. Smart Match
confirms via the email path. No AI call needed. 100%."

---

## Case 2 — Fuzzy match (business-name path) 🟡

**Invoice:** `INV-0063` (Coastal Imports, fatima@coastalimports.com, $1,250)

**Body:**
```json
{
  "payer_name": "Coastal Imports LLC",
  "payer_email": "ap@coastal-imports.com",
  "amount": 1250
}
```

**Response:** `confirmed` · method `exact_business` · confidence **0.95**

**On the Sheet:**
- `INV-0063` flips to **paid** with `paid_at` and `matched_payment_id`
- New payment row, new activity row

**On the Dashboard:**
- **Outstanding** drops by $1,250
- **Collected (30d)** and **Recovered Revenue** rise by $1,250

**Narration:** "Different email this time, but the business name matches after
we normalize 'LLC'. Smart Match confirms via the business path. Still no AI
call — pure deterministic matching."

---

## Case 3 — Smart match (Gemini judges) 🟣

**Invoice:** `INV-0016` (Northwind Trading, dkim@northwind.com, $9,200)

**Body:**
```json
{
  "payer_name": "Northwind",
  "payer_email": "accounting+nwind@gmail.com",
  "amount": 9200
}
```

**Response:** `confirmed` · method `fuzzy_ai` · confidence **~0.90** ·
**reasoning sentence written by Gemini** explaining why

**On the Sheet:**
- `INV-0016` flips to **paid** with `paid_at` and `matched_payment_id`
- Payment row has Gemini's reasoning saved in `match_reasoning`

**On the Dashboard:**
- **Outstanding** drops by $9,200
- **Collected (30d)** and **Recovered Revenue** rise by $9,200

**Narration:** "Garbled payer name, alias email. Now Gemini reasons about it.
Read the reasoning — that's the AI doing what a human Controller would do."

---

## Case 4 — Unknown payer (no match) 🔴

**Invoice:** `INV-0037` (Ironclad Mfg, cmendez@ironclad.com, $7,500)

**Body:**
```json
{
  "payer_name": "Mystery Buyer Co",
  "payer_email": "ap@randomcorp.example",
  "amount": 12750
}
```

**Response:** `no_match` (or `needs_review`) · confidence **0.0** ·
reasoning explains why nothing matched

**On the Sheet:**
- `INV-0037` is **unchanged** — still `sent`/`overdue`
- The unmatched payment row IS appended to `payments` with
  `match_status=no_match` (so we have an audit trail of the failed match)

**On the Dashboard:**
- **Outstanding** does not change
- **Needs Your Review** count may rise by 1 (if the result was `needs_review`)

**Narration:** "Totally unknown payer, amount way off. System doesn't guess —
it flags for human review. That's what makes this trustworthy for a CFO."

---

## Demo recap in one line

> Exact → Fuzzy → Smart → Unknown.
> Three confirms, one flag, full audit trail in the Sheet, KPIs update live.
