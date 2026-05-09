"""Google Sheets data layer.

Two implementations, same Protocol:
    - InMemoryStore: for local dev, tests, and the seed.py script
    - GoogleSheetsStore: for production, talks to the real Sheets API

The choice is driven by env: if GOOGLE_SHEETS_ID is empty, we use InMemoryStore.
This lets us build everything without credentials, then flip to real Sheets later.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Protocol

from app.config import settings
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment

log = logging.getLogger(__name__)


# ---------- Protocol ----------


class Store(Protocol):
    # Invoices
    def list_invoices(self, status: InvoiceStatus | None = None) -> list[Invoice]: ...
    def get_invoice(self, invoice_id: str) -> Invoice | None: ...
    def upsert_invoice(self, invoice: Invoice) -> Invoice: ...

    # Payments
    def list_payments(self) -> list[Payment]: ...
    def get_payment(self, payment_id: str) -> Payment | None: ...
    def upsert_payment(self, payment: Payment) -> Payment: ...

    # Activity log (append-only)
    def log_activity(
        self, invoice_id: str, action: str, actor: str, details: str = ""
    ) -> None: ...


# ---------- In-memory implementation ----------


class InMemoryStore:
    """Process-local dict-backed store. Lost on restart. Perfect for dev/test."""

    def __init__(self) -> None:
        self._invoices: dict[str, Invoice] = {}
        self._payments: dict[str, Payment] = {}
        self._activity: list[dict] = []

    def list_invoices(self, status: InvoiceStatus | None = None) -> list[Invoice]:
        items = list(self._invoices.values())
        if status:
            items = [i for i in items if i.status == status]
        return sorted(items, key=lambda i: i.due_date)

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        return self._invoices.get(invoice_id)

    def upsert_invoice(self, invoice: Invoice) -> Invoice:
        self._invoices[invoice.invoice_id] = invoice
        return invoice

    def list_payments(self) -> list[Payment]:
        return sorted(self._payments.values(), key=lambda p: p.received_at, reverse=True)

    def get_payment(self, payment_id: str) -> Payment | None:
        return self._payments.get(payment_id)

    def upsert_payment(self, payment: Payment) -> Payment:
        self._payments[payment.payment_id] = payment
        return payment

    def log_activity(self, invoice_id: str, action: str, actor: str, details: str = "") -> None:
        self._activity.append(
            {
                "timestamp": datetime.now().isoformat(),
                "invoice_id": invoice_id,
                "action": action,
                "actor": actor,
                "details": details,
            }
        )

    # Useful for tests
    def reset(self) -> None:
        self._invoices.clear()
        self._payments.clear()
        self._activity.clear()


# ---------- Google Sheets implementation (stub for now; wired up in deploy phase) ----------


class GoogleSheetsStore:
    """Real Google Sheets backend. Implemented later when we have credentials.

    Kept as a class with the same Protocol surface so we can swap it in without
    touching any caller. For Phase 2 we develop entirely against InMemoryStore.
    """

    def __init__(self, sheet_id: str, credentials_path: str) -> None:
        self.sheet_id = sheet_id
        self.credentials_path = credentials_path
        # Real implementation lands in the deploy phase - see BUILD_SPEC.md
        log.warning("GoogleSheetsStore is a stub - using in-memory fallback")
        self._fallback = InMemoryStore()

    def list_invoices(self, status: InvoiceStatus | None = None) -> list[Invoice]:
        return self._fallback.list_invoices(status)

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        return self._fallback.get_invoice(invoice_id)

    def upsert_invoice(self, invoice: Invoice) -> Invoice:
        return self._fallback.upsert_invoice(invoice)

    def list_payments(self) -> list[Payment]:
        return self._fallback.list_payments()

    def get_payment(self, payment_id: str) -> Payment | None:
        return self._fallback.get_payment(payment_id)

    def upsert_payment(self, payment: Payment) -> Payment:
        return self._fallback.upsert_payment(payment)

    def log_activity(self, invoice_id: str, action: str, actor: str, details: str = "") -> None:
        return self._fallback.log_activity(invoice_id, action, actor, details)


# ---------- Factory ----------

_singleton: Store | None = None


def get_store() -> Store:
    """Module-level singleton. Real apps would use FastAPI Depends; this is fine for one user."""
    global _singleton
    if _singleton is None:
        if settings.google_sheets_id:
            _singleton = GoogleSheetsStore(
                sheet_id=settings.google_sheets_id,
                credentials_path=settings.google_credentials_path,
            )
        else:
            log.info("Using InMemoryStore (no GOOGLE_SHEETS_ID configured)")
            _singleton = InMemoryStore()
    return _singleton


def _reset_for_tests() -> None:
    """Test helper - clears the singleton."""
    global _singleton
    _singleton = None


def _today() -> date:
    return date.today()
