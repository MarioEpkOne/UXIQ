"""verifier.py — Stage 9.5: run a second Claude call to verify and amend the primary audit.

Soft-failure contract: run_verification() never raises. All errors produce a
parse_warning on the returned AuditReport.
"""

from __future__ import annotations

import copy
import logging

import anthropic

from ui_analyzer.prompts import VERIFIER_PROMPT
from ui_analyzer.verification_parser import VerificationResult, apply_amendments, parse
from ui_analyzer.xml_parser import AuditReport

logger = logging.getLogger(__name__)

MAX_TOKENS = 4096
VERIFIER_TIMEOUT_S = 180


def run_verification(
    client: anthropic.Anthropic,
    system: list[dict],
    user_content: list[dict],
    primary_raw_text: str,
    audit_report: AuditReport,
    model: str = "claude-sonnet-4-6",
) -> tuple[AuditReport, anthropic.types.Usage | None]:
    """Run the verifier call and return the amended AuditReport and token usage.

    Args:
        client: Configured Anthropic client (shared with primary call).
        system: The system prompt list with cache_control already applied.
        user_content: The primary user content list with cache_control applied.
        primary_raw_text: The full raw text output from the primary Claude call.
        audit_report: The AuditReport parsed from primary_raw_text.
        model: Full model ID to use. Defaults to claude-sonnet-4-6. Always
            passed explicitly by handler.py so the verifier uses the same model
            as the primary call.

    Returns:
        (AuditReport, Usage | None) — always. If verification fails, returns a copy
        of audit_report with a parse_warning appended, and None for usage.
    """
    try:
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            timeout=VERIFIER_TIMEOUT_S,
            system=system,
            messages=[
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": primary_raw_text},
                {"role": "user", "content": [{"type": "text", "text": VERIFIER_PROMPT}]},
            ],
        )
    except anthropic.APITimeoutError as exc:
        logger.warning("Verifier call timed out: %s — skipping verification", exc)
        result = copy.deepcopy(audit_report)
        result.parse_warnings.append("Verification skipped: API timeout")
        return result, None
    except anthropic.RateLimitError as exc:
        logger.warning("Verifier call rate-limited: %s — skipping verification", exc)
        result = copy.deepcopy(audit_report)
        result.parse_warnings.append("Verification skipped: API rate limit")
        return result, None
    except Exception as exc:
        logger.warning("Verifier call failed unexpectedly: %s — skipping verification", exc)
        result = copy.deepcopy(audit_report)
        result.parse_warnings.append(f"Verification skipped: unexpected error ({exc})")
        return result, None

    verifier_raw = response.content[0].text
    verification_result: VerificationResult = parse(verifier_raw)
    return apply_amendments(audit_report, verification_result), response.usage
