"""Smart Match - the core engine.

Given an incoming Payment and a list of open Invoices, decide:
  - confirmed:    high confidence, auto-mark paid
  - needs_review: medium confidence, surface for human approval
  - no_match:     low confidence, draft outreach

Cascade:
  1. Exact email match    -> confirmed (if amount within tolerance)
  2. Exact business match -> confirmed (if amount within tolerance)
  3. Fuzzy AI judgment    -> confirmed | needs_review | no_match by score
  4. Reconciliation safeguards run on every candidate before returning confirmed:
        - amount within +/-1%
        - invoice not already paid
        - payment not already matched
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import MatchResult, Payment

log = logging.getLogger(__name__)

# Tolerances - tunable later
EXACT_AMOUNT_TOLERANCE = 0.01  # +/-1%
WIDE_AMOUNT_TOLERANCE = 0.10   # +/-10% for fuzzy candidates
CONFIRM_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.60

_BUSINESS_SUFFIX_RE = re.compile(
    r"\s*(?:llc|inc|corp|corporation|co|company|ltd|limited|gmbh|llp)\.?$",
    flags=re.IGNORECASE,
)


# ---------- Fuzzy judge protocol (so tests can swap in a fake) ----------


class FuzzyJudge(Protocol):
    """Wraps the LLM call. Returns (matched_invoice_id, confidence, reasoning)."""

    def judge(
        self, payment: Payment, candidates: list[Invoice]
    ) -> tuple[str | None, float, str]: ...


# ---------- Helpers ----------


def normalize_business(name: str) -> str:
    """Lowercase, strip trailing entity-suffix tokens (LLC/Inc/Corp/etc), collapse whitespace.

    Handles stacked suffixes ("Acme Corp LLC") by stripping iteratively.
    """
    if not name:
        return ""
    cleaned = name.strip().lower()
    while True:
        new = _BUSINESS_SUFFIX_RE.sub("", cleaned).strip()
        if new == cleaned:
            break
        cleaned = new
    return re.sub(r"\s+", " ", cleaned).strip()


def amounts_match(payment_amount: float, invoice_amount: float, tolerance: float) -> bool:
    if invoice_amount <= 0:
        return False
    return abs(payment_amount - invoice_amount) / invoice_amount <= tolerance


def _is_already_matched(payment: Payment, invoices: list[Invoice]) -> Invoice | None:
    """Return the invoice this payment is already linked to, if any."""
    if not payment.matched_invoice_id:
        return None
    return next((i for i in invoices if i.invoice_id == payment.matched_invoice_id), None)


# ---------- The engine ----------


def smart_match(
    payment: Payment,
    open_invoices: list[Invoice],
    judge: FuzzyJudge | None = None,
) -> MatchResult:
    """Match a payment to one of the candidate invoices."""

    # Reconciliation safeguard 0: payment is already matched -> short-circuit
    already = _is_already_matched(payment, open_invoices)
    if already:
        return MatchResult(
            invoice_id=already.invoice_id,
            confidence=payment.match_confidence or 1.0,
            status="needs_review",
            reasoning="Payment is already linked to an invoice. Surfaced for verification.",
            method="none",
        )

    payer_email = (payment.payer_email or "").strip().lower()

    # ---- Step 1: exact email match ----
    email_matches = [i for i in open_invoices if i.email.strip().lower() == payer_email]
    if len(email_matches) == 1:
        inv = email_matches[0]
        guard = _reconcile_guard(payment, inv, prelim_method="exact_email")
        if guard:
            return guard
        return MatchResult(
            invoice_id=inv.invoice_id,
            confidence=1.0,
            status="confirmed",
            reasoning=f"Exact email match ({inv.email}) and amount within tolerance.",
            method="exact_email",
        )
    elif len(email_matches) > 1:
        # Multiple invoices for same email -> fall through to fuzzy with these as candidates
        return _fuzzy_step(payment, email_matches, judge)

    # ---- Step 2: exact normalized business name ----
    payer_business_norm = normalize_business(payment.payer_name)
    if payer_business_norm:
        business_matches = [
            i for i in open_invoices if normalize_business(i.business_name) == payer_business_norm
        ]
        if len(business_matches) == 1:
            inv = business_matches[0]
            guard = _reconcile_guard(payment, inv, prelim_method="exact_business")
            if guard:
                return guard
            return MatchResult(
                invoice_id=inv.invoice_id,
                confidence=0.95,
                status="confirmed",
                reasoning=(
                    f"Business name '{payment.payer_name}' matches '{inv.business_name}' "
                    f"after normalization; amount within tolerance."
                ),
                method="exact_business",
            )
        elif len(business_matches) > 1:
            return _fuzzy_step(payment, business_matches, judge)

    # ---- Step 3: fuzzy AI judgment over amount-similar invoices ----
    candidates = [
        i
        for i in open_invoices
        if amounts_match(payment.amount, i.amount, WIDE_AMOUNT_TOLERANCE)
    ][:5]
    return _fuzzy_step(payment, candidates, judge)


def _fuzzy_step(
    payment: Payment, candidates: list[Invoice], judge: FuzzyJudge | None
) -> MatchResult:
    """Ask the LLM to pick (or refuse to pick) from the candidate list."""
    if not candidates:
        return MatchResult(
            invoice_id=None,
            confidence=0.0,
            status="no_match",
            reasoning="No invoices with similar amount or matching identifiers.",
            method="none",
        )

    if judge is None:
        # No judge available -> surface for review with the candidate list
        return MatchResult(
            invoice_id=candidates[0].invoice_id,
            confidence=0.5,
            status="needs_review",
            reasoning=(
                "Heuristic matchers were inconclusive and no AI judge configured. "
                f"Best candidate by amount: {candidates[0].invoice_id}."
            ),
            method="fuzzy_ai",
        )

    try:
        invoice_id, confidence, reasoning = judge.judge(payment, candidates)
    except Exception as e:  # defensive - LLM client can throw
        log.exception("Fuzzy judge failed")
        return MatchResult(
            invoice_id=None,
            confidence=0.0,
            status="no_match",
            reasoning=f"AI judge error; defaulting to no match. ({type(e).__name__})",
            method="none",
        )

    if invoice_id is None:
        return MatchResult(
            invoice_id=None,
            confidence=confidence,
            status="no_match",
            reasoning=reasoning or "AI judge found no plausible match.",
            method="none",
        )

    matched = next((i for i in candidates if i.invoice_id == invoice_id), None)
    if matched is None:
        return MatchResult(
            invoice_id=None,
            confidence=0.0,
            status="no_match",
            reasoning="AI judge returned an invoice ID not in the candidate set.",
            method="none",
        )

    if confidence >= CONFIRM_THRESHOLD:
        guard = _reconcile_guard(payment, matched, prelim_method="fuzzy_ai")
        if guard:
            # Downgrade to needs_review with the AI's reasoning preserved
            return MatchResult(
                invoice_id=matched.invoice_id,
                confidence=confidence,
                status="needs_review",
                reasoning=f"{reasoning} | Reconciliation flag: {guard.reasoning}",
                method="fuzzy_ai",
            )
        return MatchResult(
            invoice_id=matched.invoice_id,
            confidence=confidence,
            status="confirmed",
            reasoning=reasoning,
            method="fuzzy_ai",
        )
    elif confidence >= REVIEW_THRESHOLD:
        return MatchResult(
            invoice_id=matched.invoice_id,
            confidence=confidence,
            status="needs_review",
            reasoning=reasoning,
            method="fuzzy_ai",
        )
    else:
        return MatchResult(
            invoice_id=None,
            confidence=confidence,
            status="no_match",
            reasoning=reasoning,
            method="none",
        )


def _reconcile_guard(payment: Payment, invoice: Invoice, prelim_method: str) -> MatchResult | None:
    """Run reconciliation safeguards. Return a downgraded MatchResult on flag, else None."""
    if invoice.status == InvoiceStatus.PAID:
        return MatchResult(
            invoice_id=invoice.invoice_id,
            confidence=0.7,
            status="needs_review",
            reasoning=(
                f"Invoice {invoice.invoice_id} is already marked paid - possible duplicate payment."
            ),
            method=prelim_method,  # type: ignore[arg-type]
        )

    if not amounts_match(payment.amount, invoice.amount, EXACT_AMOUNT_TOLERANCE):
        # Treat as partial / overpayment - surface for review
        diff = payment.amount - invoice.amount
        sign = "over" if diff > 0 else "under"
        return MatchResult(
            invoice_id=invoice.invoice_id,
            confidence=0.7,
            status="needs_review",
            reasoning=(
                f"Amount mismatch on otherwise-strong identifier match: payment {payment.amount:.2f} "
                f"vs invoice {invoice.amount:.2f} ({sign} by {abs(diff):.2f})."
            ),
            method=prelim_method,  # type: ignore[arg-type]
        )

    return None
