"""verification_parser.py — Parse verifier XML into amendment operations and apply them.

Soft-failure contract: parse() never raises on any input.
apply_amendments() never raises on any input.

match_key uniqueness: for <remove> and <correct> operations, if multiple findings
share the same match_key, only the first matching finding is amended.

match_key construction:
  - Tier 1: "{criterion}|{element}"
  - Tier 2/3: "{principle}|{element}"
  - Tier 4: "{pattern}|{element}"
"""

from __future__ import annotations

import copy
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Literal

from ui_analyzer.xml_parser import (
    AuditReport,
    Tier1Finding,
    Tier2Finding,
    Tier3Finding,
    Tier4Finding,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Amendment dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AddFinding:
    tier: Literal["tier1", "tier2", "tier3", "tier4"]
    finding: Tier1Finding | Tier2Finding | Tier3Finding | Tier4Finding
    reason: str


@dataclass
class RemoveFinding:
    tier: Literal["tier1", "tier2", "tier3", "tier4"]
    match_key: str   # criterion|element (t1), principle|element (t2/3), pattern|element (t4)
    reason: str


@dataclass
class CorrectFinding:
    tier: Literal["tier1", "tier2", "tier3", "tier4"]
    match_key: str
    field: str       # e.g. "result", "severity", "recommendation"
    new_value: str
    reason: str


@dataclass
class VerificationResult:
    amendments: list[AddFinding | RemoveFinding | CorrectFinding] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Private helpers — match key construction
# ---------------------------------------------------------------------------

def _t1_key(f: Tier1Finding) -> str:
    return f"{f.criterion}|{f.element}"


def _t2_key(f: Tier2Finding) -> str:
    return f"{f.principle}|{f.element}"


def _t3_key(f: Tier3Finding) -> str:
    return f"{f.principle}|{f.element}"


def _t4_key(f: Tier4Finding) -> str:
    return f"{f.pattern}|{f.element}"


def _text(el: ET.Element, tag: str) -> str:
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _bool_attr(el: ET.Element, attr: str) -> bool:
    return el.get(attr, "false").lower() == "true"


def _int_attr(el: ET.Element, attr: str, default: int = 1) -> int:
    raw = el.get(attr, "")
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Private helpers — per-tier amendment parsers
# ---------------------------------------------------------------------------

def _parse_tier1_amendments(
    container: ET.Element,
    result: VerificationResult,
) -> None:
    for op in container:
        tag = op.tag
        try:
            if tag == "add":
                criterion = op.get("criterion", "")
                element = op.get("element", "")
                result_val = op.get("result", "FAIL")
                estimated = _bool_attr(op, "estimated")
                observed = _text(op, "observed")
                required = _text(op, "required")
                recommendation = _text(op, "recommendation")
                reason = _text(op, "reason")
                finding = Tier1Finding(
                    criterion=criterion,
                    element=element,
                    result=result_val,
                    estimated=estimated,
                    observed=observed,
                    required=required,
                    recommendation=recommendation,
                )
                result.amendments.append(AddFinding(tier="tier1", finding=finding, reason=reason))
            elif tag == "remove":
                criterion = op.get("criterion", "")
                element = op.get("element", "")
                reason = _text(op, "reason")
                match_key = f"{criterion}|{element}"
                result.amendments.append(RemoveFinding(tier="tier1", match_key=match_key, reason=reason))
            elif tag == "correct":
                criterion = op.get("criterion", "")
                element = op.get("element", "")
                field_name = op.get("field", "")
                new_value = op.get("new_value", "")
                reason = _text(op, "reason")
                match_key = f"{criterion}|{element}"
                result.amendments.append(CorrectFinding(
                    tier="tier1", match_key=match_key,
                    field=field_name, new_value=new_value, reason=reason,
                ))
        except Exception as exc:
            result.parse_warnings.append(f"Tier 1 amendment parse error ({tag}): {exc} — skipped")


def _parse_tier23_amendments(
    tier: Literal["tier2", "tier3"],
    container: ET.Element,
    result: VerificationResult,
    finding_cls: type,
) -> None:
    for op in container:
        tag = op.tag
        try:
            if tag == "add":
                principle = op.get("principle", "")
                element = op.get("element", "")
                severity = _int_attr(op, "severity", default=1)
                issue = _text(op, "issue")
                recommendation = _text(op, "recommendation")
                reason = _text(op, "reason")
                finding = finding_cls(
                    principle=principle,
                    severity=severity,
                    element=element,
                    issue=issue,
                    recommendation=recommendation,
                )
                result.amendments.append(AddFinding(tier=tier, finding=finding, reason=reason))
            elif tag == "remove":
                principle = op.get("principle", "")
                element = op.get("element", "")
                reason = _text(op, "reason")
                match_key = f"{principle}|{element}"
                result.amendments.append(RemoveFinding(tier=tier, match_key=match_key, reason=reason))
            elif tag == "correct":
                principle = op.get("principle", "")
                element = op.get("element", "")
                field_name = op.get("field", "")
                new_value = op.get("new_value", "")
                reason = _text(op, "reason")
                match_key = f"{principle}|{element}"
                result.amendments.append(CorrectFinding(
                    tier=tier, match_key=match_key,
                    field=field_name, new_value=new_value, reason=reason,
                ))
        except Exception as exc:
            result.parse_warnings.append(f"{tier} amendment parse error ({tag}): {exc} — skipped")


def _parse_tier4_amendments(
    container: ET.Element,
    result: VerificationResult,
) -> None:
    for op in container:
        tag = op.tag
        try:
            if tag == "add":
                pattern = op.get("pattern", "")
                element = op.get("element", "")
                issue = _text(op, "issue")
                recommendation = _text(op, "recommendation")
                reason = _text(op, "reason")
                finding = Tier4Finding(
                    pattern=pattern,
                    element=element,
                    issue=issue,
                    recommendation=recommendation,
                )
                result.amendments.append(AddFinding(tier="tier4", finding=finding, reason=reason))
            elif tag == "remove":
                pattern = op.get("pattern", "")
                element = op.get("element", "")
                reason = _text(op, "reason")
                match_key = f"{pattern}|{element}"
                result.amendments.append(RemoveFinding(tier="tier4", match_key=match_key, reason=reason))
            elif tag == "correct":
                pattern = op.get("pattern", "")
                element = op.get("element", "")
                field_name = op.get("field", "")
                new_value = op.get("new_value", "")
                reason = _text(op, "reason")
                match_key = f"{pattern}|{element}"
                result.amendments.append(CorrectFinding(
                    tier="tier4", match_key=match_key,
                    field=field_name, new_value=new_value, reason=reason,
                ))
        except Exception as exc:
            result.parse_warnings.append(f"Tier 4 amendment parse error ({tag}): {exc} — skipped")


# ---------------------------------------------------------------------------
# Public API — parse
# ---------------------------------------------------------------------------

def parse(response_text: str) -> VerificationResult:
    """Parse a verifier response into a VerificationResult.

    Never raises. Returns empty amendments + parse_warnings on failure.
    """
    result = VerificationResult()

    # Locate <verification_report> block
    start = response_text.find("<verification_report>")
    end = response_text.find("</verification_report>")

    if start == -1 or end == -1:
        result.parse_warnings.append("No <verification_report> block found in verifier response")
        return result

    xml_slice = response_text[start: end + len("</verification_report>")]

    # Sanitize bare &
    xml_slice = re.sub(
        r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)",
        "&amp;",
        xml_slice,
    )

    try:
        root = ET.fromstring(xml_slice)
    except ET.ParseError as exc:
        result.parse_warnings.append(f"Verification XML parse error: {exc}")
        return result

    # Parse each tier's amendments block
    try:
        t1 = root.find("tier1_amendments")
        if t1 is not None:
            _parse_tier1_amendments(t1, result)
    except Exception as exc:
        result.parse_warnings.append(f"Tier 1 amendments block error: {exc}")

    try:
        t2 = root.find("tier2_amendments")
        if t2 is not None:
            _parse_tier23_amendments("tier2", t2, result, Tier2Finding)
    except Exception as exc:
        result.parse_warnings.append(f"Tier 2 amendments block error: {exc}")

    try:
        t3 = root.find("tier3_amendments")
        if t3 is not None:
            _parse_tier23_amendments("tier3", t3, result, Tier3Finding)
    except Exception as exc:
        result.parse_warnings.append(f"Tier 3 amendments block error: {exc}")

    try:
        t4 = root.find("tier4_amendments")
        if t4 is not None:
            _parse_tier4_amendments(t4, result)
    except Exception as exc:
        result.parse_warnings.append(f"Tier 4 amendments block error: {exc}")

    return result


# ---------------------------------------------------------------------------
# Public API — apply_amendments
# ---------------------------------------------------------------------------

def apply_amendments(report: AuditReport, result: VerificationResult) -> AuditReport:
    """Apply all amendments in result to a deep copy of report. Never raises.

    match_key uniqueness: if multiple findings share the same match_key, only
    the first match is amended for <remove> and <correct> operations.
    """
    # Work on a deep copy so the original is unchanged
    amended = copy.deepcopy(report)

    # Propagate parse warnings from verification into the report
    amended.parse_warnings.extend(result.parse_warnings)

    tier_map: dict[str, list] = {
        "tier1": amended.tier1_findings,
        "tier2": amended.tier2_findings,
        "tier3": amended.tier3_findings,
        "tier4": amended.tier4_findings,
    }

    key_fns: dict[str, callable] = {
        "tier1": _t1_key,
        "tier2": _t2_key,
        "tier3": _t3_key,
        "tier4": _t4_key,
    }

    for amendment in result.amendments:
        try:
            findings = tier_map[amendment.tier]
            key_fn = key_fns[amendment.tier]

            if isinstance(amendment, AddFinding):
                findings.append(amendment.finding)

            elif isinstance(amendment, RemoveFinding):
                idx = next(
                    (i for i, f in enumerate(findings) if key_fn(f) == amendment.match_key),
                    None,
                )
                if idx is None:
                    logger.debug(
                        "RemoveFinding: no %s finding with match_key %r — skipped",
                        amendment.tier, amendment.match_key,
                    )
                else:
                    findings.pop(idx)

            elif isinstance(amendment, CorrectFinding):
                idx = next(
                    (i for i, f in enumerate(findings) if key_fn(f) == amendment.match_key),
                    None,
                )
                if idx is None:
                    logger.debug(
                        "CorrectFinding: no %s finding with match_key %r — skipped",
                        amendment.tier, amendment.match_key,
                    )
                else:
                    f = findings[idx]
                    if not hasattr(f, amendment.field):
                        logger.debug(
                            "CorrectFinding: field %r does not exist on %s finding — skipped",
                            amendment.field, amendment.tier,
                        )
                    else:
                        # Preserve type: int fields stay int
                        existing = getattr(f, amendment.field)
                        if isinstance(existing, int):
                            try:
                                setattr(f, amendment.field, int(amendment.new_value))
                            except (ValueError, TypeError):
                                setattr(f, amendment.field, amendment.new_value)
                        elif isinstance(existing, bool):
                            setattr(f, amendment.field, amendment.new_value.lower() == "true")
                        else:
                            setattr(f, amendment.field, amendment.new_value)

        except Exception as exc:
            logger.debug("Amendment application error: %s — skipped", exc)

    return amended
