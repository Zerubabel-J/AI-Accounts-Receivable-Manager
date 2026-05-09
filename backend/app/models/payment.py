from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class PaymentSource(str, Enum):
    STRIPE = "stripe"
    MANUAL = "manual"


class MatchStatus(str, Enum):
    CONFIRMED = "confirmed"
    NEEDS_REVIEW = "needs_review"
    NO_MATCH = "no_match"


class MatchMethod(str, Enum):
    EXACT_EMAIL = "exact_email"
    EXACT_BUSINESS = "exact_business"
    FUZZY_AI = "fuzzy_ai"
    NONE = "none"


class Payment(BaseModel):
    payment_id: str
    source: PaymentSource = PaymentSource.STRIPE
    payer_name: str = ""
    payer_email: str
    amount: float
    received_at: datetime
    matched_invoice_id: str | None = None
    match_confidence: float = 0.0
    match_reasoning: str = ""
    match_status: MatchStatus = MatchStatus.NO_MATCH
    reviewed_by_user: bool = False


class MatchResult(BaseModel):
    """Output of the Smart Match engine."""

    invoice_id: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    status: Literal["confirmed", "needs_review", "no_match"]
    reasoning: str
    method: Literal["exact_email", "exact_business", "fuzzy_ai", "none"]
