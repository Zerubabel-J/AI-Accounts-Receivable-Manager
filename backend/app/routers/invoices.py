import logging
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.integrations.gemini import get_extractor
from app.integrations.sheets import get_store
from app.models.invoice import Invoice, InvoiceCreate, InvoiceStatus, InvoiceUpdate

log = logging.getLogger(__name__)

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


class NLInvoiceRequest(BaseModel):
    text: str


class NLInvoiceResponse(BaseModel):
    invoice: Invoice
    extracted: dict
    reasoning: str


@router.post("/from-nl", response_model=NLInvoiceResponse)
def create_invoice_from_natural_language(req: NLInvoiceRequest) -> NLInvoiceResponse:
    """Parse a free-form sentence into a new invoice using Gemini.

    Example input:  "Create an invoice for $2,000 for Acme Corp for the May SEO project, due in 30 days"
    """
    extractor = get_extractor()
    if extractor is None:
        raise HTTPException(503, "Gemini is not configured on this server")

    today = date.today()
    try:
        parsed = extractor.extract(req.text, today_iso=today.isoformat())
    except Exception as e:
        log.exception("NL invoice extraction failed")
        raise HTTPException(502, f"Could not parse input: {type(e).__name__}") from e

    business_name = (parsed.get("business_name") or "").strip()
    amount = parsed.get("amount")
    if not business_name or not isinstance(amount, (int, float)) or amount <= 0:
        raise HTTPException(400, "Could not extract a valid business name and amount from the input.")

    # Parse due date safely; fall back to today + 30 days
    due_str = parsed.get("due_date") or ""
    try:
        due = date.fromisoformat(due_str)
    except (ValueError, TypeError):
        due = today + timedelta(days=30)
    if due < today:
        due = today + timedelta(days=30)

    customer_name = (parsed.get("customer_name") or business_name).strip()
    email = (parsed.get("email") or "").strip().lower()
    if not email:
        # Synthesize a reasonable placeholder so the row is valid; user can edit later
        slug = "".join(c.lower() for c in business_name if c.isalnum()) or "client"
        email = f"billing@{slug}.example.com"

    store = get_store()
    next_id = f"INV-{len(store.list_invoices()) + 1:04d}"
    invoice = Invoice(
        invoice_id=next_id,
        customer_name=customer_name,
        business_name=business_name,
        email=email,
        phone="",
        amount=float(amount),
        issued_date=today,
        due_date=due,
        status=InvoiceStatus.SENT,
    )
    store.upsert_invoice(invoice)
    store.log_activity(
        invoice.invoice_id,
        "created_from_nl",
        actor="agent",
        details=f"Parsed from: {req.text[:120]}",
    )

    reasoning = (
        f"Created {invoice.invoice_id}: ${invoice.amount:,.2f} to {business_name} "
        f"({parsed.get('description', 'no description')}), due {due.isoformat()}."
    )
    return NLInvoiceResponse(invoice=invoice, extracted=parsed, reasoning=reasoning)
