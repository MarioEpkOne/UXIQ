"""xml_parser.py — Parse Claude's XML audit response into typed dataclasses.

Soft-failure contract: parse() never raises on any input.
Missing tiers produce empty lists plus a warning in parse_warnings.
Completely unparseable input produces a fully-empty AuditReport.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Tier1Finding:
    criterion: str       # e.g. "1.4.3"
    element: str         # CSS selector or description
    result: str          # "PASS" or "FAIL"
    estimated: bool      # True if Claude estimated (not axe-core authoritative)
    observed: str        # What Claude observed
    required: str        # What the threshold requires
    recommendation: str  # What to change


@dataclass
class Tier2Finding:
    principle: str            # Gestalt/CRAP principle name
    severity: int             # 1, 2, or 3
    element: str              # Element name + location
    issue: str                # Description of the problem
    recommendation: str
    nielsen_tag: int | None = None


@dataclass
class Tier3Finding:
    principle: str            # criterion id (e.g. "consistency")
    severity: int
    element: str
    issue: str
    recommendation: str
    nielsen_tag: int | None = None


@dataclass
class Tier4Finding:
    pattern: str              # Domain pattern id
    element: str
    issue: str
    recommendation: str


@dataclass
class AuditReport:
    confidence_level: str = "unknown"
    confidence_reason: str = ""
    inventory: str = ""
    structure_observation: str = ""
    tier1_findings: list[Tier1Finding] = field(default_factory=list)
    tier2_findings: list[Tier2Finding] = field(default_factory=list)
    tier3_findings: list[Tier3Finding] = field(default_factory=list)
    tier4_findings: list[Tier4Finding] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _text(el: ET.Element, tag: str) -> str:
    """Return stripped text of a child element, or '' if absent/empty."""
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _int_or_none(el: ET.Element, tag: str) -> int | None:
    """Return int value of a child element, or None if absent/unparseable."""
    child = el.find(tag)
    if child is None or not child.text:
        return None
    try:
        return int(child.text.strip())
    except ValueError:
        return None


def _severity(el: ET.Element, attr: str = "severity") -> int:
    """Return severity int from an attribute, defaulting to 1 on failure."""
    raw = el.get(attr, "")
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 1


# ---------------------------------------------------------------------------
# Per-tier parsers
# ---------------------------------------------------------------------------

def _parse_tier1(root: ET.Element, report: AuditReport) -> None:
    """Extract Tier 1 (WCAG accessibility) findings from <tier1_findings>."""
    container = root.find("tier1_findings")
    if container is None:
        report.parse_warnings.append("Missing <tier1_findings> block in <audit_report>")
        return
    for finding_el in container.findall("finding"):
        try:
            criterion = finding_el.get("criterion", "")
            element = finding_el.get("element", "")
            result = finding_el.get("result", "")
            estimated_raw = finding_el.get("estimated", "false").lower()
            estimated = estimated_raw == "true"
            observed = _text(finding_el, "observed")
            required = _text(finding_el, "required")
            recommendation = _text(finding_el, "recommendation")
            if not criterion or not element or not result:
                report.parse_warnings.append(
                    f"Tier 1 finding missing required attribute "
                    f"(criterion={criterion!r}, element={element!r}, result={result!r}) — skipped"
                )
                continue
            report.tier1_findings.append(
                Tier1Finding(
                    criterion=criterion,
                    element=element,
                    result=result,
                    estimated=estimated,
                    observed=observed,
                    required=required,
                    recommendation=recommendation,
                )
            )
        except Exception as exc:
            report.parse_warnings.append(f"Tier 1 finding parse error: {exc} — skipped")


def _parse_tier2(root: ET.Element, report: AuditReport) -> None:
    """Extract Tier 2 (Gestalt/CRAP visual structure) findings from <tier2_findings>."""
    container = root.find("tier2_findings")
    if container is None:
        report.parse_warnings.append("Missing <tier2_findings> block in <audit_report>")
        return
    for finding_el in container.findall("finding"):
        try:
            principle = finding_el.get("principle", "")
            element = finding_el.get("element", "")
            severity = _severity(finding_el)
            issue = _text(finding_el, "issue")
            recommendation = _text(finding_el, "recommendation")
            nielsen_tag = _int_or_none(finding_el, "nielsen_tag")
            if not principle or not element:
                report.parse_warnings.append(
                    f"Tier 2 finding missing required attribute "
                    f"(principle={principle!r}, element={element!r}) — skipped"
                )
                continue
            report.tier2_findings.append(
                Tier2Finding(
                    principle=principle,
                    element=element,
                    severity=severity,
                    issue=issue,
                    recommendation=recommendation,
                    nielsen_tag=nielsen_tag,
                )
            )
        except Exception as exc:
            report.parse_warnings.append(f"Tier 2 finding parse error: {exc} — skipped")


def _parse_tier3(root: ET.Element, report: AuditReport) -> None:
    """Extract Tier 3 (usability & affordance) findings from <tier3_findings>."""
    container = root.find("tier3_findings")
    if container is None:
        report.parse_warnings.append("Missing <tier3_findings> block in <audit_report>")
        return
    for finding_el in container.findall("finding"):
        try:
            principle = finding_el.get("principle", "")
            element = finding_el.get("element", "")
            severity = _severity(finding_el)
            issue = _text(finding_el, "issue")
            recommendation = _text(finding_el, "recommendation")
            nielsen_tag = _int_or_none(finding_el, "nielsen_tag")
            if not principle or not element:
                report.parse_warnings.append(
                    f"Tier 3 finding missing required attribute "
                    f"(principle={principle!r}, element={element!r}) — skipped"
                )
                continue
            report.tier3_findings.append(
                Tier3Finding(
                    principle=principle,
                    element=element,
                    severity=severity,
                    issue=issue,
                    recommendation=recommendation,
                    nielsen_tag=nielsen_tag,
                )
            )
        except Exception as exc:
            report.parse_warnings.append(f"Tier 3 finding parse error: {exc} — skipped")


def _parse_tier4(root: ET.Element, report: AuditReport) -> None:
    """Extract Tier 4 (domain pattern) findings from <tier4_findings>."""
    container = root.find("tier4_findings")
    if container is None:
        report.parse_warnings.append("Missing <tier4_findings> block in <audit_report>")
        return
    for finding_el in container.findall("finding"):
        try:
            pattern = finding_el.get("pattern", "")
            element = finding_el.get("element", "")
            issue = _text(finding_el, "issue")
            recommendation = _text(finding_el, "recommendation")
            if not pattern or not element:
                report.parse_warnings.append(
                    f"Tier 4 finding missing required attribute "
                    f"(pattern={pattern!r}, element={element!r}) — skipped"
                )
                continue
            report.tier4_findings.append(
                Tier4Finding(
                    pattern=pattern,
                    element=element,
                    issue=issue,
                    recommendation=recommendation,
                )
            )
        except Exception as exc:
            report.parse_warnings.append(f"Tier 4 finding parse error: {exc} — skipped")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(response_text: str) -> AuditReport:
    """Parse Claude's XML audit response into an AuditReport.

    Never raises. On any malformed input, returns a partially or fully empty
    AuditReport with warnings in parse_warnings.

    Args:
        response_text: The full text of Claude's response, which may contain
                       prose before/after the <audit_report> block.

    Returns:
        AuditReport — always. Never None, never raises.
    """
    report = AuditReport()

    # Step 1: Find <audit_report> boundaries using str.find()
    # This handles Claude prepending prose before the XML block.
    start = response_text.find("<audit_report>")
    end = response_text.find("</audit_report>")

    if start == -1 or end == -1:
        report.parse_warnings.append("No <audit_report> block found in response")
        return report

    xml_slice = response_text[start : end + len("</audit_report>")]

    # Step 2: Sanitize bare & that Claude may emit in free-text content.
    # Replaces & not already part of a valid XML entity with &amp;.
    xml_slice = re.sub(
        r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)",
        "&amp;",
        xml_slice,
    )

    # Step 3: Parse the extracted slice with ElementTree
    try:
        root = ET.fromstring(xml_slice)
    except ET.ParseError as exc:
        report.parse_warnings.append(f"XML parse error: {exc}")
        return report

    # Step 3: Extract top-level scalar fields
    try:
        confidence_el = root.find("confidence")
        if confidence_el is not None:
            report.confidence_level = confidence_el.get("level", "unknown")
            report.confidence_reason = (confidence_el.text or "").strip()
    except Exception as exc:
        report.parse_warnings.append(f"Failed to parse confidence: {exc}")

    try:
        report.inventory = _text(root, "inventory")
    except Exception as exc:
        report.parse_warnings.append(f"Failed to parse inventory: {exc}")

    try:
        report.structure_observation = _text(root, "structure_observation")
    except Exception as exc:
        report.parse_warnings.append(f"Failed to parse structure_observation: {exc}")

    # Step 4: Extract per-tier findings (each wrapped in try/except at the tier level)
    try:
        _parse_tier1(root, report)
    except Exception as exc:
        report.parse_warnings.append(f"Tier 1 block parse error: {exc}")

    try:
        _parse_tier2(root, report)
    except Exception as exc:
        report.parse_warnings.append(f"Tier 2 block parse error: {exc}")

    try:
        _parse_tier3(root, report)
    except Exception as exc:
        report.parse_warnings.append(f"Tier 3 block parse error: {exc}")

    try:
        _parse_tier4(root, report)
    except Exception as exc:
        report.parse_warnings.append(f"Tier 4 block parse error: {exc}")

    return report
