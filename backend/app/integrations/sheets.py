"""Google Sheets data layer.

Two implementations, same Protocol:
    - InMemoryStore:     for local dev, tests, and the seed.py script
    - GoogleSheetsStore: real backend talking to Google Sheets

Backend choice is driven by env: if GOOGLE_SHEETS_ID is empty -> InMemoryStore.

Auth: the credentials file is auto-detected.
    - service_account JSON  -> direct service-account auth (no browser)
    - OAuth client JSON     -> InstalledAppFlow with token cached to GOOGLE_TOKEN_PATH
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

from app.config import settings
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import MatchStatus, Payment, PaymentSource

log = logging.getLogger(__name__)


# ---------- Protocol ----------


class Store(Protocol):
    def list_invoices(self, status: InvoiceStatus | None = None) -> list[Invoice]: ...
    def get_invoice(self, invoice_id: str) -> Invoice | None: ...
    def upsert_invoice(self, invoice: Invoice) -> Invoice: ...
    def upsert_invoices(self, invoices: list[Invoice]) -> None: ...  # bulk variant

    def list_payments(self) -> list[Payment]: ...
    def get_payment(self, payment_id: str) -> Payment | None: ...
    def upsert_payment(self, payment: Payment) -> Payment: ...
    def upsert_payments(self, payments: list[Payment]) -> None: ...  # bulk variant

    def log_activity(
        self, invoice_id: str, action: str, actor: str, details: str = ""
    ) -> None: ...


# ---------- In-memory implementation ----------


class InMemoryStore:
    """Process-local dict-backed store. Lost on restart. Used for tests and demo without creds."""

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

    def upsert_invoices(self, invoices: list[Invoice]) -> None:
        for inv in invoices:
            self._invoices[inv.invoice_id] = inv

    def list_payments(self) -> list[Payment]:
        return sorted(self._payments.values(), key=lambda p: p.received_at, reverse=True)

    def get_payment(self, payment_id: str) -> Payment | None:
        return self._payments.get(payment_id)

    def upsert_payment(self, payment: Payment) -> Payment:
        self._payments[payment.payment_id] = payment
        return payment

    def upsert_payments(self, payments: list[Payment]) -> None:
        for p in payments:
            self._payments[p.payment_id] = p

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

    def reset(self) -> None:
        self._invoices.clear()
        self._payments.clear()
        self._activity.clear()


# ---------- Google Sheets schema ----------

INVOICES_TAB = "invoices"
PAYMENTS_TAB = "payments"
ACTIVITY_TAB = "activity"

INVOICE_HEADERS = [
    "invoice_id",
    "customer_name",
    "business_name",
    "email",
    "phone",
    "amount",
    "issued_date",
    "due_date",
    "status",
    "risk_score",
    "risk_reason",
    "reminder_count",
    "last_reminder_at",
    "paid_at",
    "matched_payment_id",
]

PAYMENT_HEADERS = [
    "payment_id",
    "source",
    "payer_name",
    "payer_email",
    "amount",
    "received_at",
    "matched_invoice_id",
    "match_confidence",
    "match_reasoning",
    "match_status",
    "reviewed_by_user",
]

ACTIVITY_HEADERS = ["timestamp", "invoice_id", "action", "actor", "details"]

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# ---------- Google Sheets implementation ----------


def _detect_creds_kind(credentials_path: str) -> str:
    """Returns 'service_account' or 'oauth_client' by peeking at the JSON."""
    import json

    with open(credentials_path) as f:
        data = json.load(f)
    if data.get("type") == "service_account":
        return "service_account"
    if "installed" in data or "web" in data:
        return "oauth_client"
    raise ValueError(
        f"Unrecognized credentials file at {credentials_path}. "
        "Expected a service_account JSON or an OAuth client JSON."
    )


def _get_creds(credentials_path: str, token_path: str) -> Any:
    """Auto-detect creds kind and return a usable Credentials object."""
    kind = _detect_creds_kind(credentials_path)

    if kind == "service_account":
        from google.oauth2.service_account import Credentials as SA_Credentials

        log.info("Using service-account auth for Google Sheets")
        return SA_Credentials.from_service_account_file(credentials_path, scopes=SHEETS_SCOPES)

    # OAuth user-credential flow with cached token
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    log.info("Using OAuth user-credential auth for Google Sheets")
    creds = None
    token_file = Path(token_path)
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SHEETS_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SHEETS_SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json())

    return creds


class GoogleSheetsStore:
    """Talks to Google Sheets via the v4 API.

    The first request triggers the OAuth browser flow if no token is cached;
    subsequent calls use the cached token from GOOGLE_TOKEN_PATH.
    """

    def __init__(self, sheet_id: str, credentials_path: str, token_path: str):
        from googleapiclient.discovery import build

        self.sheet_id = sheet_id
        creds = _get_creds(credentials_path, token_path)
        self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        self._values = self._service.spreadsheets().values()
        self._ensure_tabs()

        # In-memory cache. Loaded once on startup; mutations write through.
        self._inv_cache: dict[str, Invoice] | None = None
        self._pay_cache: dict[str, Payment] | None = None

    # ----- internal helpers -----

    def _ensure_tabs(self) -> None:
        """Create missing tabs and write headers when blank."""
        meta = self._service.spreadsheets().get(spreadsheetId=self.sheet_id).execute()
        existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
        missing = [t for t in (INVOICES_TAB, PAYMENTS_TAB, ACTIVITY_TAB) if t not in existing]
        if missing:
            self._service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": t}}} for t in missing]},
            ).execute()

        for tab, headers in (
            (INVOICES_TAB, INVOICE_HEADERS),
            (PAYMENTS_TAB, PAYMENT_HEADERS),
            (ACTIVITY_TAB, ACTIVITY_HEADERS),
        ):
            current = self._values.get(spreadsheetId=self.sheet_id, range=f"{tab}!1:1").execute()
            if not current.get("values"):
                self._values.update(
                    spreadsheetId=self.sheet_id,
                    range=f"{tab}!A1",
                    valueInputOption="RAW",
                    body={"values": [headers]},
                ).execute()

    def _read_rows(self, tab: str) -> list[dict]:
        """Read everything below the header row as a list of dicts."""
        result = self._values.get(spreadsheetId=self.sheet_id, range=f"{tab}!A1:Z").execute()
        rows = result.get("values", [])
        if not rows:
            return []
        headers = rows[0]
        out = []
        for raw in rows[1:]:
            padded = raw + [""] * (len(headers) - len(raw))
            out.append(dict(zip(headers, padded)))
        return out

    def _write_all(self, tab: str, headers: list[str], records: list[dict]) -> None:
        """Replace the tab contents with header + serialized records."""
        body = [headers]
        for r in records:
            body.append([_serialize(r.get(h)) for h in headers])
        self._values.update(
            spreadsheetId=self.sheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            body={"values": body},
        ).execute()

    def _append_row(self, tab: str, headers: list[str], record: dict) -> None:
        row = [_serialize(record.get(h)) for h in headers]
        self._values.append(
            spreadsheetId=self.sheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

    # ----- Cache helpers -----

    def _load_invoice_cache(self) -> dict[str, Invoice]:
        if self._inv_cache is None:
            rows = self._read_rows(INVOICES_TAB)
            self._inv_cache = {
                r["invoice_id"]: _row_to_invoice(r) for r in rows if r.get("invoice_id")
            }
        return self._inv_cache

    def _load_payment_cache(self) -> dict[str, Payment]:
        if self._pay_cache is None:
            rows = self._read_rows(PAYMENTS_TAB)
            self._pay_cache = {
                r["payment_id"]: _row_to_payment(r) for r in rows if r.get("payment_id")
            }
        return self._pay_cache

    def _flush_invoices(self) -> None:
        cache = self._load_invoice_cache()
        records = [_invoice_to_row(i) for i in cache.values()]
        self._write_all(INVOICES_TAB, INVOICE_HEADERS, records)

    def _flush_payments(self) -> None:
        cache = self._load_payment_cache()
        records = [_payment_to_row(p) for p in cache.values()]
        self._write_all(PAYMENTS_TAB, PAYMENT_HEADERS, records)

    # ----- Invoice ops -----

    def list_invoices(self, status: InvoiceStatus | None = None) -> list[Invoice]:
        invoices = list(self._load_invoice_cache().values())
        if status:
            invoices = [i for i in invoices if i.status == status]
        return sorted(invoices, key=lambda i: i.due_date)

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        return self._load_invoice_cache().get(invoice_id)

    def upsert_invoice(self, invoice: Invoice) -> Invoice:
        cache = self._load_invoice_cache()
        cache[invoice.invoice_id] = invoice
        self._flush_invoices()
        return invoice

    def upsert_invoices(self, invoices: list[Invoice]) -> None:
        cache = self._load_invoice_cache()
        for inv in invoices:
            cache[inv.invoice_id] = inv
        self._flush_invoices()

    # ----- Payment ops -----

    def list_payments(self) -> list[Payment]:
        return sorted(
            self._load_payment_cache().values(),
            key=lambda p: p.received_at,
            reverse=True,
        )

    def get_payment(self, payment_id: str) -> Payment | None:
        return self._load_payment_cache().get(payment_id)

    def upsert_payment(self, payment: Payment) -> Payment:
        cache = self._load_payment_cache()
        cache[payment.payment_id] = payment
        self._flush_payments()
        return payment

    def upsert_payments(self, payments: list[Payment]) -> None:
        cache = self._load_payment_cache()
        for p in payments:
            cache[p.payment_id] = p
        self._flush_payments()

    # ----- Activity (fire-and-forget; uses append which is a single API call) -----

    def log_activity(self, invoice_id: str, action: str, actor: str, details: str = "") -> None:
        try:
            self._append_row(
                ACTIVITY_TAB,
                ACTIVITY_HEADERS,
                {
                    "timestamp": datetime.now().isoformat(),
                    "invoice_id": invoice_id,
                    "action": action,
                    "actor": actor,
                    "details": details,
                },
            )
        except Exception as e:
            # Activity log is best-effort; never block a user action on it
            log.warning("Activity log write failed: %s", e)


# ---------- Serializers ----------


def _serialize(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v)


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s.split("T")[0])
    except ValueError:
        return None


def _parse_datetime(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _parse_float(s: str, default: float = 0.0) -> float:
    try:
        return float(s) if s else default
    except (ValueError, TypeError):
        return default


def _parse_int(s: str, default: int = 0) -> int:
    try:
        return int(float(s)) if s else default
    except (ValueError, TypeError):
        return default


def _parse_bool(s: str) -> bool:
    return str(s).strip().upper() in ("TRUE", "1", "YES")


def _invoice_to_row(inv: Invoice) -> dict[str, Any]:
    return {
        "invoice_id": inv.invoice_id,
        "customer_name": inv.customer_name,
        "business_name": inv.business_name,
        "email": inv.email,
        "phone": inv.phone,
        "amount": inv.amount,
        "issued_date": inv.issued_date,
        "due_date": inv.due_date,
        "status": inv.status.value,
        "risk_score": inv.risk_score,
        "risk_reason": inv.risk_reason,
        "reminder_count": inv.reminder_count,
        "last_reminder_at": inv.last_reminder_at,
        "paid_at": inv.paid_at,
        "matched_payment_id": inv.matched_payment_id,
    }


def _row_to_invoice(r: dict) -> Invoice:
    return Invoice(
        invoice_id=r.get("invoice_id", ""),
        customer_name=r.get("customer_name", ""),
        business_name=r.get("business_name", ""),
        email=r.get("email", ""),
        phone=r.get("phone", ""),
        amount=_parse_float(r.get("amount", "0")),
        issued_date=_parse_date(r.get("issued_date", "")) or date.today(),
        due_date=_parse_date(r.get("due_date", "")) or date.today(),
        status=InvoiceStatus(r.get("status", "sent")),
        risk_score=_parse_int(r.get("risk_score", "0")),
        risk_reason=r.get("risk_reason", ""),
        reminder_count=_parse_int(r.get("reminder_count", "0")),
        last_reminder_at=_parse_datetime(r.get("last_reminder_at", "")),
        paid_at=_parse_datetime(r.get("paid_at", "")),
        matched_payment_id=r.get("matched_payment_id") or None,
    )


def _payment_to_row(p: Payment) -> dict[str, Any]:
    return {
        "payment_id": p.payment_id,
        "source": p.source.value,
        "payer_name": p.payer_name,
        "payer_email": p.payer_email,
        "amount": p.amount,
        "received_at": p.received_at,
        "matched_invoice_id": p.matched_invoice_id,
        "match_confidence": p.match_confidence,
        "match_reasoning": p.match_reasoning,
        "match_status": p.match_status.value,
        "reviewed_by_user": p.reviewed_by_user,
    }


def _row_to_payment(r: dict) -> Payment:
    return Payment(
        payment_id=r.get("payment_id", ""),
        source=PaymentSource(r.get("source", "stripe")),
        payer_name=r.get("payer_name", ""),
        payer_email=r.get("payer_email", ""),
        amount=_parse_float(r.get("amount", "0")),
        received_at=_parse_datetime(r.get("received_at", "")) or datetime.now(),
        matched_invoice_id=r.get("matched_invoice_id") or None,
        match_confidence=_parse_float(r.get("match_confidence", "0")),
        match_reasoning=r.get("match_reasoning", ""),
        match_status=MatchStatus(r.get("match_status", "no_match")),
        reviewed_by_user=_parse_bool(r.get("reviewed_by_user", "")),
    )


# ---------- Factory ----------

_singleton: Store | None = None


def get_store() -> Store:
    """Module-level singleton selecting the right backend based on env."""
    global _singleton
    if _singleton is None:
        if settings.google_sheets_id:
            log.info("Using GoogleSheetsStore (sheet_id=%s)", settings.google_sheets_id)
            _singleton = GoogleSheetsStore(
                sheet_id=settings.google_sheets_id,
                credentials_path=settings.google_credentials_path,
                token_path=settings.google_token_path,
            )
        else:
            log.info("Using InMemoryStore (no GOOGLE_SHEETS_ID configured)")
            _singleton = InMemoryStore()
    return _singleton


def _reset_for_tests() -> None:
    """Test helper - clears the singleton."""
    global _singleton
    _singleton = None
