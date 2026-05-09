# Backend - AI AR Manager

FastAPI service. Python 3.11+.

## Local dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # fill in values
uvicorn app.main:app --reload --port 8000
```

Health check: `curl http://localhost:8000/health`

## Tests

```bash
pytest
```

Smart Match engine (`tests/test_smart_match.py`) is the only fully TDD'd module — that's where the demo lives or dies.

## Layout

```
app/
  main.py              FastAPI app entry
  config.py            settings (env vars)
  models/              pydantic models
  routers/             HTTP routes
  services/            business logic (smart_match, reminder, daily_summary)
  integrations/        external clients (sheets, gemini, gmail, stripe)
tests/
  test_smart_match.py
```

## Deploy (Render)

- Build command: `pip install -e .`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Set all env vars from `.env.example`
