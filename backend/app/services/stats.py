"""Dashboard stat calculations."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.integrations.sheets import Store
from app.models.invoice import InvoiceStatus
from app.models.payment import MatchStatus
from app.models.stats import DashboardStats, HighRiskClient


def _safe_dso(invoices: list, today: date) -> int:
    """Average days from issue -> paid for invoices paid in the last 90 days."""
    paid = [
        i for i in invoices if i.status == InvoiceStatus.PAID and i.paid_at is not None
    ]
    if not paid:
        return 0
    durations = [
        max(0, (i.paid_at.date() - i.issued_date).days)
        for i in paid
    ]
    return round(sum(durations) / len(durations))


def compute_stats(store: Store, today: date | None = None) -> DashboardStats:
    today = today or date.today()
    invoices = store.list_invoices()
    payments = store.list_payments()

    # Collected in last 30 days
    cutoff_30 = today - timedelta(days=30)
    collected_30d = sum(
        i.amount
        for i in invoices
        if i.status == InvoiceStatus.PAID
        and i.paid_at is not None
        and i.paid_at.date() >= cutoff_30
    )

    # Outstanding
    outstanding_invoices = [
        i
        for i in invoices
        if i.status in (InvoiceStatus.SENT, InvoiceStatus.OVERDUE, InvoiceStatus.AT_RISK)
    ]
    outstanding_total = sum(i.amount for i in outstanding_invoices)
    outstanding_count = len(outstanding_invoices)

    # Cash at risk
    at_risk = [i for i in invoices if i.status == InvoiceStatus.AT_RISK]
    cash_at_risk = sum(i.amount for i in at_risk)
    cash_at_risk_count = len(at_risk)

    # Needs review
    needs_review_count = sum(1 for p in payments if p.match_status == MatchStatus.NEEDS_REVIEW)

    # DSO
    dso_days = _safe_dso(invoices, today)

    # Recovered Revenue MTD: sum of paid invoices for the current calendar month
    month_start = today.replace(day=1)
    recovered_revenue_mtd = sum(
        i.amount
        for i in invoices
        if i.status == InvoiceStatus.PAID
        and i.paid_at is not None
        and i.paid_at.date() >= month_start
    )

    # High risk clients
    by_email: dict[str, list] = {}
    for i in invoices:
        by_email.setdefault(i.email, []).append(i)
    high_risk: list[HighRiskClient] = []
    for email, items in by_email.items():
        max_risk = max((i.risk_score for i in items), default=0)
        if max_risk >= 70:
            outstanding = sum(
                i.amount
                for i in items
                if i.status in (InvoiceStatus.OVERDUE, InvoiceStatus.AT_RISK, InvoiceStatus.SENT)
            )
            sample = next(i for i in items if i.risk_score == max_risk)
            high_risk.append(
                HighRiskClient(
                    business_name=sample.business_name or sample.customer_name,
                    email=email,
                    risk_score=max_risk,
                    reason=sample.risk_reason or "Pattern of late payments.",
                    outstanding=outstanding,
                )
            )
    high_risk.sort(key=lambda c: c.outstanding, reverse=True)

    return DashboardStats(
        collected_30d=round(collected_30d, 2),
        outstanding_total=round(outstanding_total, 2),
        outstanding_count=outstanding_count,
        cash_at_risk=round(cash_at_risk, 2),
        cash_at_risk_count=cash_at_risk_count,
        dso_days=dso_days,
        dso_target=30,
        needs_review_count=needs_review_count,
        recovered_revenue_mtd=round(recovered_revenue_mtd, 2),
        high_risk_clients=high_risk[:5],
    )
