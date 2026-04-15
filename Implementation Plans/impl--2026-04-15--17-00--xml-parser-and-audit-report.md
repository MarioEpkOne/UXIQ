# Implementation Plan: XML Parser & AuditReport Dataclass

## Header

- **Spec**: specs/applied/spec--2026-04-15--17-00--xml-parser-and-audit-report.md
- **Worktree**: /mnt/c/Users/Epkone/UXIQ-spec-06 (branch: spec-06-xml-parser-and-audit-report)
- **Scope — files in play** (agent must not touch files not listed here):
  - `ui-analyzer/ui_analyzer/xml_parser.py` — new file (the entire implementation)
  - `ui-analyzer/tests/conftest.py` — new file (required for test isolation)
  - `ui-analyzer/tests/test_xml_parser.py` — new file (all parser tests from spec-09)
- **Reading list** (read these in order before starting, nothing else):
  1. `/mnt/c/Users/Epkone/UXIQ/ui-analyzer/ui_analyzer/__init__.py`
  2. `/mnt/c/Users/Epkone/UXIQ/ui-analyzer/ui_analyzer/exceptions.py`
  3. `/mnt/c/Users/Epkone/UXIQ/ui-analyzer/pyproject.toml`

## Environment Assumptions Verified

The following packages were confirmed installed in the active environment on 2026-04-15:

- `pytest` 9.0.3 — confirmed via `pip show pytest`
- `pytest-asyncio` 1.3.0 — confirmed via `pip show pytest-asyncio`
- `pyproject.toml` has `asyncio_mode = "auto"` and `testpaths = ["tests"]`

No `hypothesis` or other exotic test deps are used. All parser tests are synchronous. `pytest-mock` is declared in `pyproject.toml` dev extras but is not needed for `test_xml_parser.py` — that file uses only `pytest` parametrize.

---

## Steps

### Step 1: Create `ui-analyzer/ui_analyzer/xml_parser.py`

**File**: `ui-analyzer/ui_analyzer/xml_parser.py` (relative to worktree root `/mnt/c/Users/Epkone/UXIQ-spec-06`)
**Action**: Create new file — this is the entire implementation.

**Full file content**:

```python
"""xml_parser.py — Parse Claude's XML audit response into typed dataclasses.

Soft-failure contract: parse() never raises on any input.
Missing tiers produce empty lists plus a warning in parse_warnings.
Completely unparseable input produces a fully-empty AuditReport.
"""

from __future__ import annotations

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

    # Step 2: Parse the extracted slice with ElementTree
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
```

**What it does**: Implements the full `xml_parser` module:
- Five dataclasses: `Tier1Finding`, `Tier2Finding`, `Tier3Finding`, `Tier4Finding`, `AuditReport`
- Two private helpers: `_text()` and `_int_or_none()` as spec'd, plus `_severity()` for the attribute defaulting pattern
- Four per-tier private parsers: `_parse_tier1` through `_parse_tier4`, each adding a warning when the container element is absent
- `parse()`: extracts XML slice with `str.find()`, parses with `ET.fromstring()`, delegates to per-tier parsers — never raises on any input

**Constraints enforced**:
- Only `xml.etree.ElementTree` (stdlib) used — no lxml
- `parse()` wraps every operation in try/except — never raises
- `Tier3Finding` uses `principle` (not `criterion`) — same shape as `Tier2Finding`
- `severity` defaults to `1` when unparseable (see `_severity()`)
- Missing tier container adds a warning, leaving the list empty

**Verification**: After writing the file, run:
```bash
cd /mnt/c/Users/Epkone/UXIQ-spec-06/ui-analyzer
ANTHROPIC_API_KEY=test python -c "from ui_analyzer.xml_parser import parse, AuditReport; r = parse(''); print('OK:', r)"
```
Expected: prints `OK: AuditReport(...)` with no exception.

---

### Step 2: Create `ui-analyzer/tests/` directory and `conftest.py`

**File**: `ui-analyzer/tests/conftest.py`
**Action**: Create new file (and create the `tests/` directory first).

**What to run first**:
```bash
mkdir -p /mnt/c/Users/Epkone/UXIQ-spec-06/ui-analyzer/tests/fixtures
touch /mnt/c/Users/Epkone/UXIQ-spec-06/ui-analyzer/tests/__init__.py
```

**Full file content for `conftest.py`**:
```python
import os
import pytest

# IMPORTANT: ui_analyzer/__init__.py raises UIAnalyzerError at import time
# if ANTHROPIC_API_KEY is unset. Set a fake key before any ui_analyzer import
# so that unit tests (which mock the API) can import the package.
# This must happen before pytest collects test modules.
if not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "test-key-unit-tests"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as requiring a real ANTHROPIC_API_KEY"
    )


@pytest.fixture
def fixtures_dir():
    return os.path.join(os.path.dirname(__file__), "fixtures")
```

**What it does**: Sets the fake API key before any `ui_analyzer` import occurs during pytest collection, preventing `UIAnalyzerError` from being raised. Registers the `integration` marker to suppress pytest warnings.

**Verification**: `cd ui-analyzer && pytest tests/ --collect-only 2>&1 | head -20` shows test collection without `UIAnalyzerError`.

---

### Step 3: Create `ui-analyzer/tests/test_xml_parser.py`

**File**: `ui-analyzer/tests/test_xml_parser.py`
**Action**: Create new file.

**Full file content**:
```python
"""Tests for ui_analyzer.xml_parser — soft-failure XML parsing."""

import pytest
from ui_analyzer.xml_parser import (
    AuditReport,
    Tier1Finding,
    Tier2Finding,
    Tier3Finding,
    Tier4Finding,
    parse,
)

# ---------------------------------------------------------------------------
# Fixture XML
# ---------------------------------------------------------------------------

FULL_REPORT_XML = """
<audit_report>
  <confidence level="high"></confidence>
  <inventory>Nav bar, hero button, 3 metric cards</inventory>
  <structure_observation>2-column layout, blue primary color</structure_observation>
  <tier1_findings>
    <finding criterion="1.4.3" element=".nav-link" result="FAIL" estimated="false">
      <observed>contrast ratio 2.8:1</observed>
      <required>4.5:1 for normal text</required>
      <recommendation>Change to #374151</recommendation>
    </finding>
    <finding criterion="1.4.1" element="status indicator" result="PASS" estimated="false">
      <observed>color + icon used</observed>
      <required>not sole indicator</required>
      <recommendation>none</recommendation>
    </finding>
  </tier1_findings>
  <tier2_findings>
    <finding principle="proximity" severity="2" element="Metric cards">
      <issue>4px gap too small</issue>
      <recommendation>Increase to 24px</recommendation>
      <nielsen_tag>4</nielsen_tag>
    </finding>
  </tier2_findings>
  <tier3_findings>
    <finding principle="visual_hierarchy" severity="1" element="CTA button">
      <issue>Not dominant enough</issue>
      <recommendation>Increase size</recommendation>
      <nielsen_tag>8</nielsen_tag>
    </finding>
  </tier3_findings>
  <tier4_findings>
    <finding pattern="data_ink_ratio" element="Sidebar">
      <issue>Icon-only nav</issue>
      <recommendation>Add labels</recommendation>
    </finding>
  </tier4_findings>
</audit_report>
"""

FULL_REPORT_XML_WITH_PROSE = (
    "Here is my analysis of the UI:\n\n" + FULL_REPORT_XML + "\n\nEnd of report."
)

MISSING_TIER2_XML = FULL_REPORT_XML.replace(
    """  <tier2_findings>
    <finding principle="proximity" severity="2" element="Metric cards">
      <issue>4px gap too small</issue>
      <recommendation>Increase to 24px</recommendation>
      <nielsen_tag>4</nielsen_tag>
    </finding>
  </tier2_findings>""",
    "",
)

ESTIMATED_TRUE_XML = """
<audit_report>
  <confidence level="medium"></confidence>
  <inventory>A button</inventory>
  <structure_observation>simple</structure_observation>
  <tier1_findings>
    <finding criterion="1.4.3" element=".btn" result="FAIL" estimated="true">
      <observed>low contrast</observed>
      <required>4.5:1</required>
      <recommendation>darken text</recommendation>
    </finding>
    <finding criterion="2.1.1" element=".link" result="PASS" estimated="false">
      <observed>keyboard accessible</observed>
      <required>focusable</required>
      <recommendation>none</recommendation>
    </finding>
  </tier1_findings>
  <tier2_findings/>
  <tier3_findings/>
  <tier4_findings/>
</audit_report>
"""

MISSING_NIELSEN_TAG_XML = """
<audit_report>
  <confidence level="low"></confidence>
  <inventory>form</inventory>
  <structure_observation>single column</structure_observation>
  <tier1_findings/>
  <tier2_findings>
    <finding principle="alignment" severity="1" element="Labels">
      <issue>Labels misaligned</issue>
      <recommendation>Left-align all</recommendation>
    </finding>
  </tier2_findings>
  <tier3_findings/>
  <tier4_findings/>
</audit_report>
"""


# ---------------------------------------------------------------------------
# test_xml_parser_full_response
# ---------------------------------------------------------------------------

def test_xml_parser_full_response():
    """Well-formed full <audit_report> → all 4 lists populated correctly."""
    report = parse(FULL_REPORT_XML)

    assert isinstance(report, AuditReport)
    assert len(report.tier1_findings) == 2
    assert len(report.tier2_findings) == 1
    assert len(report.tier3_findings) == 1
    assert len(report.tier4_findings) == 1

    t1 = report.tier1_findings[0]
    assert t1.criterion == "1.4.3"
    assert t1.element == ".nav-link"
    assert t1.result == "FAIL"
    assert t1.estimated is False

    t2 = report.tier2_findings[0]
    assert t2.severity == 2
    assert t2.nielsen_tag == 4
    assert t2.principle == "proximity"

    t4 = report.tier4_findings[0]
    assert t4.pattern == "data_ink_ratio"

    assert report.parse_warnings == []


def test_xml_parser_full_response_confidence():
    """Confidence level is correctly extracted from the <confidence> element."""
    report = parse(FULL_REPORT_XML)
    assert report.confidence_level == "high"


def test_xml_parser_full_response_inventory():
    """Inventory text is extracted."""
    report = parse(FULL_REPORT_XML)
    assert report.inventory == "Nav bar, hero button, 3 metric cards"


def test_xml_parser_full_response_structure_observation():
    """Structure observation is extracted."""
    report = parse(FULL_REPORT_XML)
    assert report.structure_observation == "2-column layout, blue primary color"


def test_xml_parser_with_surrounding_prose():
    """parse() handles prose before and after <audit_report>."""
    report = parse(FULL_REPORT_XML_WITH_PROSE)
    assert len(report.tier1_findings) == 2
    assert report.parse_warnings == []


# ---------------------------------------------------------------------------
# test_xml_parser_missing_tier
# ---------------------------------------------------------------------------

def test_xml_parser_missing_tier2():
    """Missing <tier2_findings> → tier2_findings==[], warning added, others populated."""
    report = parse(MISSING_TIER2_XML)

    assert report.tier2_findings == []
    assert len(report.parse_warnings) == 1
    assert "tier2_findings" in report.parse_warnings[0].lower()

    # Other tiers still populated
    assert len(report.tier1_findings) == 2
    assert len(report.tier3_findings) == 1
    assert len(report.tier4_findings) == 1


# ---------------------------------------------------------------------------
# test_xml_parser_no_audit_report_tag
# ---------------------------------------------------------------------------

def test_xml_parser_no_audit_report_tag():
    """No <audit_report> tag → all lists empty, warning added."""
    report = parse("just prose, no XML tags")

    assert report.tier1_findings == []
    assert report.tier2_findings == []
    assert report.tier3_findings == []
    assert report.tier4_findings == []
    assert len(report.parse_warnings) == 1
    assert "No <audit_report>" in report.parse_warnings[0]


def test_xml_parser_empty_string():
    """Empty string → all lists empty, warning added."""
    report = parse("")
    assert report.tier1_findings == []
    assert len(report.parse_warnings) >= 1


# ---------------------------------------------------------------------------
# test_xml_parser_malformed_xml
# ---------------------------------------------------------------------------

def test_xml_parser_malformed_xml():
    """Malformed XML → all lists empty, parse_warnings non-empty, no exception."""
    report = parse("<audit_report><unclosed>")

    assert report.tier1_findings == []
    assert report.tier2_findings == []
    assert report.tier3_findings == []
    assert report.tier4_findings == []
    assert len(report.parse_warnings) >= 1


# ---------------------------------------------------------------------------
# test_xml_parser_never_raises
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_input", [
    "",
    "not xml at all",
    "<audit_report><unclosed>",
    "   \n\t  ",
    "<audit_report></audit_report>",
    "random bytes \x00\xff as string",
    "<audit_report><tier1_findings><finding></finding></tier1_findings></audit_report>",
])
def test_xml_parser_never_raises(bad_input):
    """parse() must not raise on any input."""
    result = parse(bad_input)
    assert isinstance(result, AuditReport)


# ---------------------------------------------------------------------------
# test_tier1_estimated_flag
# ---------------------------------------------------------------------------

def test_tier1_estimated_true():
    """estimated='true' attribute → Tier1Finding.estimated == True."""
    report = parse(ESTIMATED_TRUE_XML)
    assert len(report.tier1_findings) >= 1
    estimated_findings = [f for f in report.tier1_findings if f.estimated is True]
    assert len(estimated_findings) == 1
    assert estimated_findings[0].criterion == "1.4.3"


def test_tier1_estimated_false():
    """estimated='false' attribute → Tier1Finding.estimated == False."""
    report = parse(ESTIMATED_TRUE_XML)
    not_estimated = [f for f in report.tier1_findings if f.estimated is False]
    assert len(not_estimated) == 1
    assert not_estimated[0].criterion == "2.1.1"


# ---------------------------------------------------------------------------
# test_missing_nielsen_tag
# ---------------------------------------------------------------------------

def test_missing_nielsen_tag_is_none():
    """Missing <nielsen_tag> element → nielsen_tag == None."""
    report = parse(MISSING_NIELSEN_TAG_XML)
    assert len(report.tier2_findings) == 1
    assert report.tier2_findings[0].nielsen_tag is None


# ---------------------------------------------------------------------------
# test_severity_default
# ---------------------------------------------------------------------------

def test_severity_default_when_missing():
    """Missing severity attribute → defaults to 1."""
    xml = """
<audit_report>
  <confidence level="low"></confidence>
  <inventory/>
  <structure_observation/>
  <tier1_findings/>
  <tier2_findings>
    <finding principle="contrast" element="Header">
      <issue>Too light</issue>
      <recommendation>Darken</recommendation>
    </finding>
  </tier2_findings>
  <tier3_findings/>
  <tier4_findings/>
</audit_report>
"""
    report = parse(xml)
    assert len(report.tier2_findings) == 1
    assert report.tier2_findings[0].severity == 1


def test_severity_default_when_unparseable():
    """Unparseable severity attribute → defaults to 1, no raise."""
    xml = """
<audit_report>
  <confidence level="low"></confidence>
  <inventory/>
  <structure_observation/>
  <tier1_findings/>
  <tier2_findings>
    <finding principle="contrast" severity="notanumber" element="Header">
      <issue>Too light</issue>
      <recommendation>Darken</recommendation>
    </finding>
  </tier2_findings>
  <tier3_findings/>
  <tier4_findings/>
</audit_report>
"""
    report = parse(xml)
    assert len(report.tier2_findings) == 1
    assert report.tier2_findings[0].severity == 1


# ---------------------------------------------------------------------------
# test_extra_tags_silently_ignored
# ---------------------------------------------------------------------------

def test_extra_tags_silently_ignored():
    """Extra tags Claude invented are silently ignored."""
    xml = """
<audit_report>
  <confidence level="high"></confidence>
  <inventory>test</inventory>
  <structure_observation>test</structure_observation>
  <claude_invented_tag>some value</claude_invented_tag>
  <tier1_findings/>
  <tier2_findings/>
  <tier3_findings/>
  <tier4_findings/>
</audit_report>
"""
    report = parse(xml)
    # No crash, no warning about the extra tag
    assert isinstance(report, AuditReport)


# ---------------------------------------------------------------------------
# test_finding_missing_required_attribute_skipped
# ---------------------------------------------------------------------------

def test_tier1_finding_missing_criterion_skipped():
    """Tier 1 finding missing required 'criterion' attribute is skipped with warning."""
    xml = """
<audit_report>
  <confidence level="medium"></confidence>
  <inventory/>
  <structure_observation/>
  <tier1_findings>
    <finding element=".btn" result="FAIL" estimated="false">
      <observed>low contrast</observed>
      <required>4.5:1</required>
      <recommendation>fix it</recommendation>
    </finding>
  </tier1_findings>
  <tier2_findings/>
  <tier3_findings/>
  <tier4_findings/>
</audit_report>
"""
    report = parse(xml)
    assert report.tier1_findings == []
    assert len(report.parse_warnings) >= 1


def test_tier3_finding_uses_principle_attribute():
    """Tier3Finding uses 'principle' attribute name (same shape as Tier2)."""
    report = parse(FULL_REPORT_XML)
    assert len(report.tier3_findings) == 1
    t3 = report.tier3_findings[0]
    assert hasattr(t3, "principle")
    assert t3.principle == "visual_hierarchy"
    assert not hasattr(t3, "criterion")
```

**What it does**: Implements all test cases required by spec-09 for `xml_parser.py`:
- `test_xml_parser_full_response` — well-formed all-tier XML populated correctly
- `test_xml_parser_missing_tier2` — missing tier adds warning, others still populated
- `test_xml_parser_no_audit_report_tag` — no tag → all empty + "No <audit_report>" warning
- `test_xml_parser_malformed_xml` — malformed XML → all empty, no raise
- `test_xml_parser_never_raises` — parametrized over 7 pathological inputs
- `test_tier1_estimated_true` / `test_tier1_estimated_false` — flag parsing
- `test_missing_nielsen_tag_is_none` — optional attribute is None when absent
- Plus additional tests for edge cases from the Edge Cases table (severity default, extra tags ignored, missing required attributes skipped, Tier3 uses `principle`)

**Verification**: Run `cd ui-analyzer && pytest tests/test_xml_parser.py -v`
Expected: All tests pass. No errors or failures.

---

### Step 4: Run the full test suite

**Action**:
```bash
cd /mnt/c/Users/Epkone/UXIQ-spec-06/ui-analyzer
ANTHROPIC_API_KEY=test pytest tests/test_xml_parser.py -v
```

**Expected output**: All tests collected and passing. Zero failures. Zero errors.

If any test fails, diagnose and fix `xml_parser.py` (not the tests) before proceeding to Step 5.

---

### Step 5: Commit

**Action**: Stage and commit from the worktree root.

```bash
cd /mnt/c/Users/Epkone/UXIQ-spec-06
git add ui-analyzer/ui_analyzer/xml_parser.py
git add ui-analyzer/tests/conftest.py
git add ui-analyzer/tests/test_xml_parser.py
git add ui-analyzer/tests/__init__.py
git commit -m "feat: implement xml_parser and AuditReport dataclasses

Adds xml_parser.py with:
- Tier1/2/3/4Finding and AuditReport dataclasses
- parse() function using stdlib xml.etree.ElementTree
- Soft-failure contract: never raises, accumulates warnings
- All four tier parsers with missing-block detection

Adds tests/conftest.py (fake API key for unit test isolation)
and tests/test_xml_parser.py covering all spec-09 assertions
for this module."
```

**Verification**: `git log --oneline -3` shows the new commit on branch `spec-06-xml-parser-and-audit-report`. `git status` shows clean working tree.

---

## Post-Implementation Checklist

- [ ] `ui-analyzer/ui_analyzer/xml_parser.py` created in worktree
- [ ] `ui-analyzer/tests/conftest.py` created in worktree
- [ ] `ui-analyzer/tests/test_xml_parser.py` created in worktree
- [ ] `parse("")` returns `AuditReport()` without raising (Step 1 verification)
- [ ] `parse(FULL_REPORT_XML)` returns all 4 lists populated, `parse_warnings == []`
- [ ] `parse(MISSING_TIER2_XML)` returns `tier2_findings == []` with exactly 1 warning
- [ ] `parse("just prose")` returns all empty, warning contains "No <audit_report>"
- [ ] `parse("<audit_report><unclosed>")` returns all empty, no exception
- [ ] All `test_xml_parser_never_raises` parametrize variants pass
- [ ] `estimated="true"` → `Tier1Finding.estimated is True`
- [ ] `estimated="false"` → `Tier1Finding.estimated is False`
- [ ] Missing `<nielsen_tag>` → `nielsen_tag is None`
- [ ] Missing `severity` attribute → defaults to `1`
- [ ] Unparseable `severity` attribute → defaults to `1`, no raise
- [ ] `Tier3Finding` has `principle` attribute (not `criterion`)
- [ ] All 4 tiers each add a warning when their container is absent
- [ ] `pytest tests/test_xml_parser.py -v` exits 0 (Step 4)
- [ ] Commit created on branch `spec-06-xml-parser-and-audit-report` (Step 5)
- [ ] Only `xml.etree.ElementTree` (stdlib) used — no lxml import anywhere

## Verification Approach

Run `pytest tests/test_xml_parser.py -v` from inside `ui-analyzer/` with `ANTHROPIC_API_KEY=test` set in the environment. All tests must exit 0. If any test fails, fix `xml_parser.py` only — do not modify the tests.

```bash
cd /mnt/c/Users/Epkone/UXIQ-spec-06/ui-analyzer
ANTHROPIC_API_KEY=test pytest tests/test_xml_parser.py -v
```

## Commit Message (draft)

```
feat: implement xml_parser and AuditReport dataclasses

Adds xml_parser.py with:
- Tier1/2/3/4Finding and AuditReport dataclasses
- parse() function using stdlib xml.etree.ElementTree
- Soft-failure contract: never raises, accumulates warnings
- All four tier parsers with missing-block detection

Adds tests/conftest.py (fake API key for unit test isolation)
and tests/test_xml_parser.py covering all spec-09 assertions
for this module.
```
