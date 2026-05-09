from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from app.integrations.sheets import get_store
from app.models.invoice import Invoice, InvoiceCreate, InvoiceStatus, InvoiceUpdate

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=list[Invoice])
def list_invoices(status: InvoiceStatus | None = None) -> list[Invoice]:
    return get_store().list_invoices(status=status)


@router.get("/{invoice_id}", response_model=Invoice)
def get_invoice(invoice_id: str) -> Invoice:
    inv = get_store().get_invoice(invoice_id)
    if inv is None:
        raise HTTPException(404, "Invoice not found")
    return inv


@router.post("", response_model=Invoice, status_code=201)
def create_invoice(data: InvoiceCreate) -> Invoice:
    store = get_store()
    next_id = f"INV-{len(store.list_invoices()) + 1:04d}"
    today = date.today()
    inv = Invoice(
        invoice_id=next_id,
        customer_name=data.customer_name,
        business_name=data.business_name,
        email=data.email,
        phone=data.phone,
        amount=data.amount,
        issued_date=data.issued_date,
        due_date=data.due_date,
        status=InvoiceStatus.SENT if data.due_date >= today else InvoiceStatus.OVERDUE,
    )
    store.upsert_invoice(inv)
    store.log_activity(inv.invoice_id, "created", actor="user")
    return inv


@router.patch("/{invoice_id}", response_model=Invoice)
def update_invoice(invoice_id: str, patch: InvoiceUpdate) -> Invoice:
    store = get_store()
    inv = store.get_invoice(invoice_id)
    if inv is None:
        raise HTTPException(404, "Invoice not found")
    update_data = patch.model_dump(exclude_unset=True)
    updated = inv.model_copy(update=update_data)
    store.upsert_invoice(updated)
    return updated
