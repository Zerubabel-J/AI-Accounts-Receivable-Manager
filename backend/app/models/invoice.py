from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class InvoiceStatus(str, Enum):
    SENT = "sent"
    OVERDUE = "overdue"
    PAID = "paid"
    AT_RISK = "at_risk"


class Invoice(BaseModel):
    invoice_id: str
    customer_name: str
    business_name: str = ""
    email: str
    phone: str = ""
    amount: float
    issued_date: date
    due_date: date
    status: InvoiceStatus = InvoiceStatus.SENT
    risk_score: int = 0
    risk_reason: str = ""
    reminder_count: int = 0
    last_reminder_at: datetime | None = None
    paid_at: datetime | None = None
    matched_payment_id: str | None = None


class InvoiceCreate(BaseModel):
    customer_name: str
    business_name: str = ""
    email: EmailStr
    phone: str = ""
    amount: float = Field(gt=0)
    issued_date: date
    due_date: date


class InvoiceUpdate(BaseModel):
    status: InvoiceStatus | None = None
    risk_score: int | None = None
    risk_reason: str | None = None
    reminder_count: int | None = None
    last_reminder_at: datetime | None = None
    paid_at: datetime | None = None
    matched_payment_id: str | None = None
