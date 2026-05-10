"""Gemini integration for Smart Match's fuzzy judgment step.

Implements the FuzzyJudge protocol from app.services.smart_match.

The model is asked to compare an incoming payment against up to 5 candidate
invoices and decide which one (if any) it most likely pays. It must return
JSON; we parse it defensively because LLMs occasionally wrap output in
markdown fences or add prose.
"""

from __future__ import annotations

import json
import logging
import re

from app.config import settings
from app.models.invoice import Invoice
from app.models.payment import Payment

log = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.5-flash"

PROMPT_TEMPLATE = """You are an Accounts Receivable matching assistant. Decide whether an incoming \
payment matches one of the candidate invoices. Be conservative - it is better to flag for human \
review than to confirm a wrong match.

INCOMING PAYMENT:
- payer_name:  "{payer_name}"
- payer_email: "{payer_email}"
- amount:      ${amount:.2f}

CANDIDATE INVOICES (up to 5):
{candidates_block}

Score on these signals (in order of weight):
1. Same business (consider entity suffixes like LLC/Inc/Corp as equivalent)
2. Email domain or local-part overlap
3. Amount equality (already pre-filtered to within +/-10%)
4. Customer name similarity

Return JSON only, no prose, no markdown fences:
{{
  "invoice_id": "<id of best candidate or null>",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<one sentence explanation, max 25 words>"
}}

Confidence guidance:
- >= 0.85 - clearly the same payer/invoice
- 0.60-0.85 - probably right but worth a human glance
- < 0.60 - inconclusive, prefer null

JSON:"""


def _format_candidates(invoices: list[Invoice]) -> str:
    lines = []
    for i in invoices:
        lines.append(
            f"- {i.invoice_id}: business='{i.business_name}', "
            f"customer='{i.customer_name}', email='{i.email}', amount=${i.amount:.2f}"
        )
    return "\n".join(lines)


def _parse_json_loose(raw: str) -> dict:
    """Extract a JSON object even if wrapped in ```json ...``` or surrounded by prose."""
    raw = raw.strip()
    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fence_match:
        raw = fence_match.group(1)
    # Find first {...} block
    brace_match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if brace_match:
        raw = brace_match.group(0)
    return json.loads(raw)


class GeminiFuzzyJudge:
    """Implements the smart_match.FuzzyJudge protocol."""

    def __init__(self, api_key: str | None = None, model_name: str = MODEL_NAME):
        import google.generativeai as genai  # lazy import keeps tests clean

        key = api_key or settings.gemini_api_key
        if not key:
            raise ValueError("GEMINI_API_KEY is not set")
        genai.configure(api_key=key)
        self._model = genai.GenerativeModel(model_name)

    def judge(self, payment: Payment, candidates: list[Invoice]) -> tuple[str | None, float, str]:
        if not candidates:
            return None, 0.0, "No candidates provided."

        prompt = PROMPT_TEMPLATE.format(
            payer_name=payment.payer_name,
            payer_email=payment.payer_email,
            amount=payment.amount,
            candidates_block=_format_candidates(candidates),
        )

        try:
            response = self._model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "response_mime_type": "application/json",
                    "max_output_tokens": 200,
                },
            )
            text = response.text or ""
        except Exception as e:
            log.warning("Gemini call failed: %s", e)
            raise  # smart_match catches and returns no_match gracefully

        try:
            data = _parse_json_loose(text)
        except (json.JSONDecodeError, ValueError) as e:
            log.warning("Could not parse Gemini JSON output: %s\nRaw: %s", e, text[:300])
            return None, 0.0, "AI returned an unparseable response."

        invoice_id = data.get("invoice_id")
        confidence = float(data.get("confidence", 0.0))
        reasoning = str(data.get("reasoning", "")).strip() or "AI returned no reasoning."

        # Guard: clamp confidence and validate id is in the candidate set
        confidence = max(0.0, min(1.0, confidence))
        if invoice_id is not None:
            valid_ids = {c.invoice_id for c in candidates}
            if invoice_id not in valid_ids:
                log.info("Gemini returned an unknown invoice_id: %s", invoice_id)
                return None, 0.0, f"AI suggested an invoice not in the candidate set."

        return invoice_id, confidence, reasoning


# Module-level singleton for the running app
_judge_singleton: GeminiFuzzyJudge | None = None


def get_judge() -> GeminiFuzzyJudge | None:
    """Returns a Gemini judge instance, or None if no API key is configured."""
    global _judge_singleton
    if _judge_singleton is None and settings.gemini_api_key:
        try:
            _judge_singleton = GeminiFuzzyJudge()
            log.info("Gemini fuzzy judge initialized")
        except Exception as e:
            log.warning("Could not initialize Gemini judge: %s", e)
            return None
    return _judge_singleton
