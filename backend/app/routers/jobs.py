"""Cron-triggered endpoints. Hit by Cloud Scheduler.

Both endpoints require a Bearer token matching CRON_SECRET.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from app.config import settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


def _check_cron_auth(authorization: str | None) -> None:
    if not authorization or authorization != f"Bearer {settings.cron_secret}":
        raise HTTPException(status_code=401, detail="Invalid cron token")


@router.post("/run-reminders")
async def run_reminders(authorization: str | None = Header(default=None)) -> dict:
    _check_cron_auth(authorization)
    # Real implementation lands in the crons phase
    log.info("run-reminders triggered (stub)")
    return {"status": "ok", "sent": 0, "stub": True}


@router.post("/run-daily-summary")
async def run_daily_summary(authorization: str | None = Header(default=None)) -> dict:
    _check_cron_auth(authorization)
    log.info("run-daily-summary triggered (stub)")
    return {"status": "ok", "summary_sent": False, "stub": True}
