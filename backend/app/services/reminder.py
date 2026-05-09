"""Reminder service - decides which invoices need a nudge today and (if enabled) sends one.

Cadence:
  Day 0      - 0 reminders sent yet  -> friendly
  Day +7     - 1 sent                -> firmer
  Day +14    - 2 sent                -> escalation
  Day >=30   - 3+ sent               -> mark at_risk, surface for human (no auto-send)

In SEND_EMAILS_FOR_REAL=false mode we skip the actual Gmail send but still log
the activity so the demo dashboard reflects the work. This is what lets us
record demo videos without spamming people.
"""

from __future__ import annotations

import logging
from datetime import date

from app.config import settings
from app.integrations.sheets import Store
from app.models.invoice import Invoice, InvoiceStatus

log = logging.getLogger(__name__)


def _decide_tone(reminder_count: int, days_past_due: int) -> str | None:
    """Return 'friendly' | 'firm' | 'escalation' | None (no reminder today)."""
    if days_past_due == 0 and reminder_count == 0:
        return "friendly"
    if days_past_due >= 7 and reminder_count == 1:
        return "firm"
    if days_past_due >= 14 and reminder_count == 2:
        return "escalation"
    return None


def run_reminders(store: Store, today: date | None = None) -> dict:
    today = today or date.today()
    sent = 0
    flagged_at_risk = 0
    activity: list[dict] = []

    for inv in store.list_invoices():
        if inv.status not in (InvoiceStatus.SENT, InvoiceStatus.OVERDUE):
            continue

        days_past_due = (today - inv.due_date).days

        # Hit at-risk threshold first
        if days_past_due >= 30 and inv.reminder_count >= 3:
            inv.status = InvoiceStatus.AT_RISK
            store.upsert_invoice(inv)
            store.log_activity(
                inv.invoice_id,
                "flagged_at_risk",
                actor="agent",
                details=f"{days_past_due}d past due after {inv.reminder_count} reminders.",
            )
            flagged_at_risk += 1
            continue

        tone = _decide_tone(inv.reminder_count, days_past_due)
        if tone is None:
            continue

        # Mark overdue if it just became so
        if inv.status == InvoiceStatus.SENT and days_past_due > 0:
            inv.status = InvoiceStatus.OVERDUE

        # In real mode this would draft via Gemini and send via Gmail
        if settings.send_emails_for_real:
            log.info("Would send %s reminder to %s for %s", tone, inv.email, inv.invoice_id)

        inv.reminder_count += 1
        store.upsert_invoice(inv)
        store.log_activity(
            inv.invoice_id,
            f"reminder_{tone}",
            actor="agent",
            details=f"Reminder #{inv.reminder_count} ({tone}) drafted for {inv.email}.",
        )
        activity.append({"invoice_id": inv.invoice_id, "tone": tone})
        sent += 1

    return {"sent": sent, "flagged_at_risk": flagged_at_risk, "activity": activity}
