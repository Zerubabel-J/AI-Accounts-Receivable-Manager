"""Daily Summary - the morning email to the user.

Builds an HTML brief with collected/at-risk/needs-review/high-risk and either
sends it via Gmail or returns it as a payload for preview during the demo.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.integrations.sheets import Store
from app.models.invoice import InvoiceStatus
from app.models.payment import MatchStatus
from app.services.stats import compute_stats


def build_summary(store: Store, today: date | None = None) -> dict:
    today = today or date.today()
    stats = compute_stats(store, today)

    yesterday = today - timedelta(days=1)
    invoices = store.list_invoices()

    collected_yday = [
        i
        for i in invoices
        if i.status == InvoiceStatus.PAID
        and i.paid_at is not None
        and i.paid_at.date() == yesterday
    ]
    yday_total = sum(i.amount for i in collected_yday)

    payments = store.list_payments()
    needs_review = [p for p in payments if p.match_status == MatchStatus.NEEDS_REVIEW]

    return {
        "as_of": today.isoformat(),
        "yesterday_collected": round(yday_total, 2),
        "yesterday_count": len(collected_yday),
        "outstanding_total": stats.outstanding_total,
        "outstanding_count": stats.outstanding_count,
        "cash_at_risk": stats.cash_at_risk,
        "cash_at_risk_count": stats.cash_at_risk_count,
        "needs_review_count": len(needs_review),
        "high_risk": [
            {
                "business_name": c.business_name,
                "outstanding": c.outstanding,
                "reason": c.reason,
            }
            for c in stats.high_risk_clients[:3]
        ],
        "generated_at": datetime.now().isoformat(),
    }


def render_html(summary: dict) -> str:
    """Plain HTML email body. Inline styles only (some clients strip <style>)."""
    rows = ""
    for c in summary["high_risk"]:
        rows += (
            f'<li><strong>{c["business_name"]}</strong> - '
            f'${c["outstanding"]:,.0f} outstanding<br/>'
            f'<span style="color:#64748b;font-size:13px">{c["reason"]}</span></li>'
        )

    return f"""
    <div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:560px;color:#0f172a">
      <h2 style="margin:0 0 8px">Good morning. Your AR brief.</h2>
      <p style="color:#64748b;margin:0 0 24px">{summary["as_of"]}</p>

      <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
        <tr>
          <td style="padding:12px;background:#ecfdf5;border-radius:6px">
            <div style="font-size:13px;color:#047857">Collected yesterday</div>
            <div style="font-size:22px;font-weight:600">${summary["yesterday_collected"]:,.0f}</div>
            <div style="font-size:12px;color:#64748b">{summary["yesterday_count"]} invoices</div>
          </td>
          <td style="padding:12px;background:#fef2f2;border-radius:6px">
            <div style="font-size:13px;color:#b91c1c">Cash at risk</div>
            <div style="font-size:22px;font-weight:600">${summary["cash_at_risk"]:,.0f}</div>
            <div style="font-size:12px;color:#64748b">{summary["cash_at_risk_count"]} invoices</div>
          </td>
        </tr>
      </table>

      <p>Outstanding: <strong>${summary["outstanding_total"]:,.0f}</strong>
        across {summary["outstanding_count"]} invoices.</p>
      <p>{summary["needs_review_count"]} payments waiting for your review.</p>

      <h3 style="margin:24px 0 8px">Watch list</h3>
      <ul style="padding-left:18px">{rows}</ul>
    </div>
    """
