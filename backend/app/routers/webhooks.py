"""Stripe webhook receiver.

Stripe POSTs payment events here. We verify the signature, transform the event
into our Payment model, run Smart Match, and persist.

Run locally with:
    stripe listen --forward-to localhost:8000/webhooks/stripe

Trigger a test event with:
    stripe trigger payment_intent.succeeded
"""

from __future__ import annotations

import logging
from datetime import datetime

import stripe
from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings
from app.integrations.sheets import get_store
from app.models.invoice import InvoiceStatus
from app.models.payment import MatchStatus, Payment, PaymentSource
from app.services.smart_match import smart_match

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict:
    payload = await request.body()

    # Verify signature unless we're running without a secret (dev convenience)
    if settings.stripe_webhook_secret:
        if not stripe_signature:
            raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")
        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=stripe_signature,
                secret=settings.stripe_webhook_secret,
            )
        except (ValueError, stripe.SignatureVerificationError) as e:
            log.warning("Invalid Stripe webhook signature: %s", e)
            raise HTTPException(status_code=400, detail="Invalid signature") from e
    else:
        # No secret configured -> parse the body directly. Dev only.
        import json

        event = json.loads(payload)

    event_type = event.get("type", "")

    # We only care about successful charges
    if event_type not in ("payment_intent.succeeded", "charge.succeeded"):
        return {"received": True, "ignored": event_type}

    obj = event["data"]["object"]
    payment = _stripe_event_to_payment(obj)

    store = get_store()
    open_invoices = [
        i
        for i in store.list_invoices()
        if i.status in (InvoiceStatus.SENT, InvoiceStatus.OVERDUE, InvoiceStatus.AT_RISK)
    ]

    # The judge is wired in once Gemini integration lands - falls back to needs_review for now
    result = smart_match(payment, open_invoices, judge=None)

    payment.matched_invoice_id = result.invoice_id
    payment.match_confidence = result.confidence
    payment.match_reasoning = result.reasoning
    payment.match_status = MatchStatus(result.status)
    store.upsert_payment(payment)

    if result.status == "confirmed" and result.invoice_id:
        invoice = store.get_invoice(result.invoice_id)
        if invoice:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = datetime.now()
            invoice.matched_payment_id = payment.payment_id
            store.upsert_invoice(invoice)
            store.log_activity(
                invoice.invoice_id,
                "auto_matched",
                actor="agent",
                details=f"Payment {payment.payment_id} matched via {result.method}",
            )

    return {
        "received": True,
        "payment_id": payment.payment_id,
        "match_status": result.status,
        "invoice_id": result.invoice_id,
    }


def _stripe_event_to_payment(obj: dict) -> Payment:
    """Map a Stripe payment_intent or charge object into our Payment model."""
    amount_cents = obj.get("amount_received") or obj.get("amount") or 0
    metadata = obj.get("metadata") or {}
    billing = obj.get("billing_details") or {}
    customer_email = (
        billing.get("email")
        or obj.get("receipt_email")
        or metadata.get("email")
        or ""
    )
    customer_name = billing.get("name") or metadata.get("name") or ""

    return Payment(
        payment_id=obj.get("id", f"PAY-{datetime.now().timestamp():.0f}"),
        source=PaymentSource.STRIPE,
        payer_name=customer_name,
        payer_email=customer_email,
        amount=amount_cents / 100.0,
        received_at=datetime.fromtimestamp(obj.get("created", datetime.now().timestamp())),
    )
