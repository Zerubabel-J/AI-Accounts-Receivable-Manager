"""Cron-triggered endpoints. Hit by Cloud Scheduler.

Both endpoints require a Bearer token matching CRON_SECRET.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.integrations.sheets import get_store
from app.services.daily_summary import build_summary, render_html
from app.services.reminder import run_reminders as run_reminders_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


def _check_cron_auth(authorization: str | None) -> None:
    if not authorization or authorization != f"Bearer {settings.cron_secret}":
        raise HTTPException(status_code=401, detail="Invalid cron token")


@router.post("/run-reminders")
async def run_reminders(authorization: str | None = Header(default=None)) -> dict:
    _check_cron_auth(authorization)
    result = run_reminders_service(get_store())
    log.info("run-reminders sent=%d at_risk=%d", result["sent"], result["flagged_at_risk"])
    return {"status": "ok", **result}


@router.post("/run-daily-summary")
async def run_daily_summary(authorization: str | None = Header(default=None)) -> dict:
    _check_cron_auth(authorization)
    summary = build_summary(get_store())
    html = render_html(summary)
    # Sending via Gmail is wired up in the deploy phase. For now we just return it.
    log.info("run-daily-summary built (yday_collected=%s)", summary["yesterday_collected"])
    return {"status": "ok", "summary": summary, "html_preview_len": len(html)}
