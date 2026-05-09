from fastapi import APIRouter, HTTPException

from app.integrations.sheets import get_store
from app.models.payment import Payment

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
