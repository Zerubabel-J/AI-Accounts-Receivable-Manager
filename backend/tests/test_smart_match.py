"""Smart Match engine tests - the demo lives or dies on this file.

Each test corresponds to a row in BUILD_SPEC.md section 3 (test cases).
The Gemini call is replaced with a FakeJudge so tests are deterministic and offline.
"""

from datetime import date, datetime, timedelta

import pytest  # noqa: F401  -- imported for the test runner discovery

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import MatchStatus, Payment, PaymentSource
from app.services.smart_match import smart_match


# ---------- Test doubles ----------


class FakeJudge:
    """Stand-in for the real Gemini-backed judge."""

    def __init__(
        self,
        invoice_id: str | None = None,
        confidence: float = 0.9,
        reasoning: str = "Fake judge says match.",
        raise_exc: bool = False,
    ):
        self.invoice_id = invoice_id
        self.confidence = confidence
        self.reasoning = reasoning
        self.raise_exc = raise_exc
        self.calls: list[tuple[Payment, list[Invoice]]] = []

    def judge(self, payment, candidates):
        self.calls.append((payment, candidates))
        if self.raise_exc:
            raise RuntimeError("LLM is down")
        return self.invoice_id, self.confidence, self.reasoning


# ---------- Fixtures ----------


def make_invoice(
    invoice_id: str = "INV-0001",
    customer_name: str = "Sarah Chen",
    business_name: str = "Acme Corp",
    email: str = "sarah@acmecorp.com",
    amount: float = 1000.0,
    status: InvoiceStatus = InvoiceStatus.SENT,
    phone: str = "555-0101",
) -> Invoice:
    today = date.today()
    return Invoice(
        invoice_id=invoice_id,
        customer_name=customer_name,
        business_name=business_name,
        email=email,
        phone=phone,
        amount=amount,
        issued_date=today - timedelta(days=10),
        due_date=today + timedelta(days=20),
        status=status,
    )


def make_payment(
    payment_id: str = "PAY-0001",
    payer_name: str = "Sarah Chen",
    payer_email: str = "sarah@acmecorp.com",
    amount: float = 1000.0,
) -> Payment:
    return Payment(
        payment_id=payment_id,
        source=PaymentSource.STRIPE,
        payer_name=payer_name,
        payer_email=payer_email,
        amount=amount,
        received_at=datetime.now(),
        match_status=MatchStatus.NO_MATCH,
    )


# ---------- Cases ----------


def test_case_1_exact_email_and_amount_confirms():
    invoice = make_invoice(amount=1000.0)
    payment = make_payment(amount=1000.0)

    result = smart_match(payment, [invoice])

    assert result.status == "confirmed"
    assert result.method == "exact_email"
    assert result.invoice_id == "INV-0001"
    assert result.confidence == 1.0


def test_case_2_amount_within_1pct_tolerance_confirms():
    invoice = make_invoice(amount=1000.0)
    payment = make_payment(amount=1005.0)  # 0.5% off

    result = smart_match(payment, [invoice])

    assert result.status == "confirmed"
    assert result.method == "exact_email"


def test_case_3_amount_20pct_off_needs_review():
    invoice = make_invoice(amount=1000.0)
    payment = make_payment(amount=800.0)  # 20% off (partial?)

    result = smart_match(payment, [invoice])

    assert result.status == "needs_review"
    assert "amount mismatch" in result.reasoning.lower() or "partial" in result.reasoning.lower() or "under" in result.reasoning.lower()


def test_case_4_business_name_with_llc_suffix_confirms():
    invoice = make_invoice(
        email="finance@bigco.com",  # different email path
        business_name="Acme Corp",
        amount=2400.0,
    )
    payment = make_payment(
        payer_email="ap@somewhere.com",
        payer_name="Acme Corp LLC",  # has LLC suffix
        amount=2400.0,
    )

    result = smart_match(payment, [invoice])

    assert result.status == "confirmed"
    assert result.method == "exact_business"


def test_case_5_fuzzy_ai_high_confidence_confirms():
    invoice = make_invoice(
        email="finance@bigco.com",
        business_name="Bluewave Solutions",
        amount=4800.0,
    )
    payment = make_payment(
        payer_email="ap@unknown.com",
        payer_name="Bluewav Sol",
        amount=4800.0,
    )

    judge = FakeJudge(invoice_id="INV-0001", confidence=0.92, reasoning="Strong fuzzy match.")
    result = smart_match(payment, [invoice], judge=judge)

    assert result.status == "confirmed"
    assert result.method == "fuzzy_ai"
    assert result.confidence == 0.92
    assert len(judge.calls) == 1


def test_case_6_fuzzy_ai_medium_confidence_needs_review():
    invoice = make_invoice(
        email="finance@bigco.com", business_name="Polaris Studio", amount=3200.0
    )
    payment = make_payment(
        payer_email="ap@unknown.com", payer_name="Polar Studios", amount=3200.0
    )

    judge = FakeJudge(invoice_id="INV-0001", confidence=0.7, reasoning="Maybe.")
    result = smart_match(payment, [invoice], judge=judge)

    assert result.status == "needs_review"
    assert result.method == "fuzzy_ai"
    assert result.confidence == 0.7


def test_case_7_fuzzy_ai_low_confidence_no_match():
    invoice = make_invoice(
        email="finance@bigco.com", business_name="Vertex Labs", amount=950.0
    )
    payment = make_payment(
        payer_email="random@gmail.com", payer_name="J Smith", amount=950.0
    )

    judge = FakeJudge(invoice_id=None, confidence=0.3, reasoning="No real connection.")
    result = smart_match(payment, [invoice], judge=judge)

    assert result.status == "no_match"
    assert result.invoice_id is None


def test_case_8_invoice_already_paid_needs_review():
    invoice = make_invoice(amount=1000.0, status=InvoiceStatus.PAID)
    payment = make_payment(amount=1000.0)

    result = smart_match(payment, [invoice])

    assert result.status == "needs_review"
    assert "already" in result.reasoning.lower() and "paid" in result.reasoning.lower()


def test_case_9_judge_raises_falls_back_gracefully():
    invoice = make_invoice(
        email="finance@bigco.com", business_name="Aurora Systems", amount=1250.0
    )
    payment = make_payment(
        payer_email="ap@unknown.com", payer_name="Aurora Sys", amount=1250.0
    )

    judge = FakeJudge(raise_exc=True)
    result = smart_match(payment, [invoice], judge=judge)

    assert result.status == "no_match"
    assert "ai judge" in result.reasoning.lower() or "error" in result.reasoning.lower()


def test_case_10_two_invoices_same_email_disambiguated_by_amount():
    inv_a = make_invoice(invoice_id="INV-A", amount=500.0, email="bob@vendor.com")
    inv_b = make_invoice(invoice_id="INV-B", amount=2400.0, email="bob@vendor.com")
    payment = make_payment(payer_email="bob@vendor.com", amount=2400.0)

    # Multiple email matches -> falls into fuzzy step. Provide a judge that picks B.
    judge = FakeJudge(invoice_id="INV-B", confidence=0.95, reasoning="Amount disambiguates to INV-B.")
    result = smart_match(payment, [inv_a, inv_b], judge=judge)

    assert result.status == "confirmed"
    assert result.invoice_id == "INV-B"


# ---------- Bonus: edge guards ----------


def test_no_open_invoices_returns_no_match():
    payment = make_payment()
    result = smart_match(payment, [])
    assert result.status == "no_match"
    assert result.invoice_id is None


def test_already_matched_payment_short_circuits():
    invoice = make_invoice()
    payment = make_payment()
    payment.matched_invoice_id = invoice.invoice_id  # already linked

    result = smart_match(payment, [invoice])
    assert result.status == "needs_review"
    assert "already" in result.reasoning.lower()
