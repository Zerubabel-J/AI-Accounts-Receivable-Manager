# AI Accounts Receivable Manager

An autonomous AR agent for B2B SMBs. Watches incoming payments, matches them to open invoices using a hybrid deterministic + AI engine, sends calibrated follow-ups to late payers, and emails the user a daily summary.

Built for the Brain3 Level-1 assignment.

## Quick links

- [Solution Design (SRS)](./docs/SRS.md) — what we promised to build
- [Build Spec](./docs/BUILD_SPEC.md) — engineer-facing detail
- [CLAUDE.md](./CLAUDE.md) — project context for Claude sessions

## Stack

- **Frontend:** Next.js 15 + Tailwind + shadcn/ui (deployed on Vercel)
- **Backend:** FastAPI / Python 3.11+ (deployed on Render)
- **AI:** Google Gemini 2.5 Flash
- **Data:** Google Sheets
- **Payments:** Stripe sandbox + webhooks
- **Email:** Gmail API
- **Cron:** GCP Cloud Scheduler

All on free tiers. No credit card required.

## Run locally

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # fill in
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000.

## Layout

```
/frontend       Next.js app
/backend        FastAPI app
/docs           SRS, build spec, architecture notes
/scripts        seed.py and other one-offs
```

## Status

Phase 1 (Setup) complete. See [BUILD_SPEC.md](./docs/BUILD_SPEC.md) §8 for the build timeline.
