import logging
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
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
    email: str | None = None  # provided on retry after a 'needs_email' response


class NLInvoiceResponse(BaseModel):
    invoice: Invoice
    extracted: dict
    reasoning: str


class NLInvoiceNeedsMore(BaseModel):
    needs: str  # which field is missing, e.g. "email"
    extracted: dict
    message: str


@router.post(
    "/from-nl",
    responses={
        200: {"model": NLInvoiceResponse},
        422: {"model": NLInvoiceNeedsMore},
    },
)
def create_invoice_from_natural_language(req: NLInvoiceRequest):
    """Parse a free-form sentence into a new invoice using Gemini.

    Returns:
        200 + NLInvoiceResponse on success
        422 + NLInvoiceNeedsMore when the request is missing the client email
              (user retries with the email filled in)
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

    # Email resolution: explicit override > Gemini-extracted > ask user
    explicit_email = (req.email or "").strip().lower()
    extracted_email = (parsed.get("email") or "").strip().lower()
    email = explicit_email or extracted_email
    if not email:
        # Tell the UI to ask for it. We return the partial extraction so the user
        # can see what Gemini already understood while they type the email.
        return JSONResponse(
            status_code=422,
            content={
                "needs": "email",
                "extracted": parsed,
                "message": (
                    f"What's the client email for {business_name}? "
                    "I'll need it to bill them and to match payments later."
                ),
            },
        )

    # Parse due date safely; fall back to today + 30 days
    due_str = parsed.get("due_date") or ""
    try:
        due = date.fromisoformat(due_str)
    except (ValueError, TypeError):
        due = today + timedelta(days=30)
    if due < today:
        due = today + timedelta(days=30)

    customer_name = (parsed.get("customer_name") or business_name).strip()

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
