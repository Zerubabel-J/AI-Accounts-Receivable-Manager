"""Review Queue endpoints. Human-in-the-loop for payments the AI flagged."""

from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.integrations.sheets import get_store
from app.models.invoice import InvoiceStatus
from app.models.payment import MatchStatus, Payment

router = APIRouter(prefix="/review-queue", tags=["review"])


@router.get("", response_model=list[Payment])
def list_review_queue() -> list[Payment]:
    return [
        p
        for p in get_store().list_payments()
        if p.match_status == MatchStatus.NEEDS_REVIEW and not p.reviewed_by_user
    ]


@router.post("/{payment_id}/approve", response_model=Payment)
def approve_match(payment_id: str) -> Payment:
    store = get_store()
    payment = store.get_payment(payment_id)
    if payment is None:
        raise HTTPException(404, "Payment not found")
    if not payment.matched_invoice_id:
        raise HTTPException(400, "Payment has no candidate invoice to approve")

    invoice = store.get_invoice(payment.matched_invoice_id)
    if invoice is None:
        raise HTTPException(404, "Linked invoice not found")

    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = datetime.now()
    invoice.matched_payment_id = payment.payment_id
    store.upsert_invoice(invoice)

    payment.match_status = MatchStatus.CONFIRMED
    payment.reviewed_by_user = True
    store.upsert_payment(payment)

    store.log_activity(
        invoice.invoice_id,
        "approved_match",
        actor="user",
        details=f"Approved match with payment {payment.payment_id}",
    )
    return payment


@router.post("/{payment_id}/reject", response_model=Payment)
def reject_match(payment_id: str) -> Payment:
    store = get_store()
    payment = store.get_payment(payment_id)
    if payment is None:
        raise HTTPException(404, "Payment not found")

    payment.matched_invoice_id = None
    payment.match_status = MatchStatus.NO_MATCH
    payment.reviewed_by_user = True
    payment.match_reasoning = "User rejected the proposed match."
    store.upsert_payment(payment)
    return payment
