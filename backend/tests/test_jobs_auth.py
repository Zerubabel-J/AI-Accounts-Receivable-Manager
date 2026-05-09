"""Cron endpoints must reject requests without the right Bearer token.

This is the cheapest test that prevents a real ops disaster: if cron auth
silently breaks, Cloud Scheduler returns 401 forever and we don't notice.
"""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_run_reminders_requires_auth():
    r = client.post("/jobs/run-reminders")
    assert r.status_code == 401


def test_run_reminders_rejects_wrong_token():
    r = client.post(
        "/jobs/run-reminders",
        headers={"Authorization": "Bearer not-the-real-secret"},
    )
    assert r.status_code == 401


def test_run_reminders_accepts_correct_token():
    r = client.post(
        "/jobs/run-reminders",
        headers={"Authorization": f"Bearer {settings.cron_secret}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_daily_summary_same_protections():
    r1 = client.post("/jobs/run-daily-summary")
    assert r1.status_code == 401

    r2 = client.post(
        "/jobs/run-daily-summary",
        headers={"Authorization": f"Bearer {settings.cron_secret}"},
    )
    assert r2.status_code == 200
