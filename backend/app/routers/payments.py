"""Payment routes + a /simulate endpoint so the demo can fire a payment without Stripe CLI."""

import random
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.integrations.sheets import get_store
from app.models.invoice import InvoiceStatus
from app.models.payment import MatchStatus, Payment, PaymentSource
from app.services.smart_match import smart_match

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("", response_model=list[Payment])
def list_payments() -> list[Payment]:
    return get_store().list_payments()


@router.get("/{payment_id}", response_model=Payment)
def get_payment(payment_id: str) -> Payment:
    p = get_store().get_payment(payment_id)
    if p is None:
        raise HTTPException(404, "Payment not found")
    return p


class SimulateRequest(BaseModel):
    scenario: Literal["clean_match", "fuzzy_match", "no_match"] = "clean_match"


@router.post("/simulate")
def simulate_payment(req: SimulateRequest) -> dict:
    """Fire a fake payment for the demo. Mimics what a Stripe webhook would do."""
    store = get_store()
    open_invoices = [
        i
        for i in store.list_invoices()
        if i.status in (InvoiceStatus.SENT, InvoiceStatus.OVERDUE)
    ]
    if not open_invoices:
        raise HTTPException(400, "No open invoices to simulate against")

    payment_id = f"PAY-SIM-{int(datetime.now().timestamp())}"

    # Pick a target that produces a clean demo. For fuzzy_match we want a
    # business+amount combo that's unique among open invoices, so the engine
    # can confirm via exact_business without amount collisions.
    if req.scenario == "fuzzy_match":
        from collections import Counter

        biz_amount_counts = Counter(
            (i.business_name, i.amount) for i in open_invoices
        )
        unique = [
            i
            for i in open_invoices
            if biz_amount_counts[(i.business_name, i.amount)] == 1 and i.business_name
        ]
        target = random.choice(unique) if unique else random.choice(open_invoices)
    else:
        target = random.choice(open_invoices)

    if req.scenario == "clean_match":
        # Same email, same amount -> exact_email confirmed
        payment = Payment(
            payment_id=payment_id,
            source=PaymentSource.STRIPE,
            payer_name=target.customer_name,
            payer_email=target.email,
            amount=target.amount,
            received_at=datetime.now(),
        )
    elif req.scenario == "fuzzy_match":
        # Different email but same business name -> exact_business confirmed
        payment = Payment(
            payment_id=payment_id,
            source=PaymentSource.STRIPE,
            payer_name=f"{target.business_name} LLC",
            payer_email=f"ap@{target.business_name.lower().replace(' ', '')}.com",
            amount=target.amount,
            received_at=datetime.now(),
        )
    else:  # no_match
        payment = Payment(
            payment_id=payment_id,
            source=PaymentSource.STRIPE,
            payer_name="Unknown Sender Co",
            payer_email="ap@strangecorp.com",
            amount=round(random.uniform(500, 5000), 2),
            received_at=datetime.now(),
        )

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
                "auto_matched_simulated",
                actor="agent",
                details=f"Demo payment {payment.payment_id} via {result.method}",
            )

    return {
        "payment_id": payment.payment_id,
        "scenario": req.scenario,
        "match_status": result.status,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
        "method": result.method,
        "invoice_id": result.invoice_id,
    }
