"""Tests for ui_analyzer.verification_parser — parse() and apply_amendments()."""

from __future__ import annotations

import pytest
from ui_analyzer.verification_parser import (
    AddFinding,
    CorrectFinding,
    RemoveFinding,
    VerificationResult,
    apply_amendments,
    parse,
)
from ui_analyzer.xml_parser import AuditReport, Tier1Finding, Tier2Finding, Tier3Finding, Tier4Finding


# ---------------------------------------------------------------------------
# Fixture XML
# ---------------------------------------------------------------------------

FULL_VERIFICATION_XML = """
<verification_report>
  <assessment>Minor corrections applied</assessment>
  <tier1_amendments>
    <add criterion="1.4.3" element=".hero-text" result="FAIL" estimated="false">
      <observed>contrast ratio 2.1:1</observed>
      <required>4.5:1 for normal text</required>
      <recommendation>Change text color to #374151</recommendation>
      <reason>Element is visible in screenshot but was omitted from primary findings</reason>
    </add>
    <remove criterion="2.5.8" element=".modal-close-btn">
      <reason>No modal close button is visible in this screenshot</reason>
    </remove>
    <correct criterion="1.4.1" element=".status-badge" field="result" new_value="PASS">
      <reason>Badge uses both color and icon</reason>
    </correct>
  </tier1_amendments>
  <tier2_amendments>
    <add principle="alignment" severity="2" element="Filter bar">
      <issue>Filter chips misaligned with table column headers by 8px</issue>
      <recommendation>Align filter chips to table left edge</recommendation>
      <reason>Missed by primary agent</reason>
    </add>
  </tier2_amendments>
  <tier4_amendments>
    <remove pattern="metric_hierarchy" element="KPI cards">
      <reason>KPI cards are visually dominant; finding does not hold for this screenshot</reason>
    </remove>
  </tier4_amendments>
</verification_report>
"""

EMPTY_VERIFICATION_XML = "<verification_report><assessment>Report verified. No amendments required.</assessment></verification_report>"

ASSESSMENT_ONLY_XML = "<verification_report><assessment>Report verified. No amendments required.</assessment></verification_report>"


# ---------------------------------------------------------------------------
# Test 1: Full verification report with all amendment types
# ---------------------------------------------------------------------------

def test_parse_full_verification_report():
    """Valid verification_report with add/remove/correct across tiers → correct VerificationResult."""
    result = parse(FULL_VERIFICATION_XML)
    assert isinstance(result, VerificationResult)
    assert len(result.amendments) == 5
    assert result.parse_warnings == []


# ---------------------------------------------------------------------------
# Test 2: tier1 <add> parsed correctly
# ---------------------------------------------------------------------------

def test_parse_tier1_add():
    """<add> in tier1_amendments → AddFinding with Tier1Finding."""
    result = parse(FULL_VERIFICATION_XML)
    add_ops = [a for a in result.amendments if isinstance(a, AddFinding) and a.tier == "tier1"]
    assert len(add_ops) == 1
    a = add_ops[0]
    assert isinstance(a.finding, Tier1Finding)
    assert a.finding.criterion == "1.4.3"
    assert a.finding.element == ".hero-text"
    assert a.finding.result == "FAIL"
    assert a.finding.estimated is False
    assert "omitted" in a.reason


# ---------------------------------------------------------------------------
# Test 3: tier1 <remove> match_key
# ---------------------------------------------------------------------------

def test_parse_tier1_remove_match_key():
    """<remove> in tier1_amendments → RemoveFinding with match_key = 'criterion|element'."""
    result = parse(FULL_VERIFICATION_XML)
    removes = [a for a in result.amendments if isinstance(a, RemoveFinding) and a.tier == "tier1"]
    assert len(removes) == 1
    assert removes[0].match_key == "2.5.8|.modal-close-btn"


# ---------------------------------------------------------------------------
# Test 4: tier1 <correct> field and new_value
# ---------------------------------------------------------------------------

def test_parse_tier1_correct():
    """<correct> in tier1_amendments → CorrectFinding with field and new_value."""
    result = parse(FULL_VERIFICATION_XML)
    corrects = [a for a in result.amendments if isinstance(a, CorrectFinding) and a.tier == "tier1"]
    assert len(corrects) == 1
    c = corrects[0]
    assert c.field == "result"
    assert c.new_value == "PASS"
    assert c.match_key == "1.4.1|.status-badge"


# ---------------------------------------------------------------------------
# Test 5: tier2 <add>
# ---------------------------------------------------------------------------

def test_parse_tier2_add():
    """<add> in tier2_amendments → AddFinding with Tier2Finding."""
    result = parse(FULL_VERIFICATION_XML)
    add_ops = [a for a in result.amendments if isinstance(a, AddFinding) and a.tier == "tier2"]
    assert len(add_ops) == 1
    a = add_ops[0]
    assert isinstance(a.finding, Tier2Finding)
    assert a.finding.principle == "alignment"
    assert a.finding.severity == 2
    assert a.finding.element == "Filter bar"


# ---------------------------------------------------------------------------
# Test 6: tier4 <remove> match_key
# ---------------------------------------------------------------------------

def test_parse_tier4_remove_match_key():
    """<remove> in tier4_amendments → RemoveFinding with match_key = 'pattern|element'."""
    result = parse(FULL_VERIFICATION_XML)
    removes = [a for a in result.amendments if isinstance(a, RemoveFinding) and a.tier == "tier4"]
    assert len(removes) == 1
    assert removes[0].match_key == "metric_hierarchy|KPI cards"


# ---------------------------------------------------------------------------
# Test 7: empty verification report
# ---------------------------------------------------------------------------

def test_parse_empty_verification_report():
    """Empty <verification_report> → VerificationResult(amendments=[], parse_warnings=[])."""
    result = parse(EMPTY_VERIFICATION_XML)
    assert result.amendments == []
    assert result.parse_warnings == []


# ---------------------------------------------------------------------------
# Test 8: missing <verification_report> block
# ---------------------------------------------------------------------------

def test_parse_missing_block():
    """No <verification_report> tag → parse_warnings populated, no crash."""
    result = parse("The primary report looks fine.")
    assert result.amendments == []
    assert len(result.parse_warnings) >= 1
    assert "verification_report" in result.parse_warnings[0].lower()


# ---------------------------------------------------------------------------
# Test 9: malformed XML
# ---------------------------------------------------------------------------

def test_parse_malformed_xml():
    """Malformed XML inside <verification_report> → parse_warnings populated, amendments empty."""
    result = parse("<verification_report><tier1_amendments><unclosed>")
    assert result.amendments == []
    assert len(result.parse_warnings) >= 1


# ---------------------------------------------------------------------------
# Test 10: assessment-only response
# ---------------------------------------------------------------------------

def test_parse_assessment_only():
    """Assessment-only response → no amendments, no warnings."""
    result = parse(ASSESSMENT_ONLY_XML)
    assert result.amendments == []
    assert result.parse_warnings == []


# ---------------------------------------------------------------------------
# Test 11: never raises — parametrized
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_input", [
    "",
    "not xml at all",
    "<verification_report><unclosed>",
    "   \n\t  ",
    "<verification_report></verification_report>",
])
def test_parse_never_raises(bad_input):
    """parse() must not raise on any input."""
    result = parse(bad_input)
    assert isinstance(result, VerificationResult)


# ---------------------------------------------------------------------------
# Test 12: tier3 <add>
# ---------------------------------------------------------------------------

def test_parse_tier3_add():
    """<add> in tier3_amendments → AddFinding with Tier3Finding."""
    xml = """
<verification_report>
  <tier3_amendments>
    <add principle="consistency" severity="1" element="Button labels">
      <issue>Inconsistent capitalization</issue>
      <recommendation>Use sentence case throughout</recommendation>
      <reason>Missed in primary pass</reason>
    </add>
  </tier3_amendments>
</verification_report>
"""
    result = parse(xml)
    add_ops = [a for a in result.amendments if isinstance(a, AddFinding) and a.tier == "tier3"]
    assert len(add_ops) == 1
    assert isinstance(add_ops[0].finding, Tier3Finding)
    assert add_ops[0].finding.principle == "consistency"


# ---------------------------------------------------------------------------
# Test 13: multiple amendments in one tier
# ---------------------------------------------------------------------------

def test_parse_multiple_amendments_same_tier():
    """Multiple <add> operations in one tier → all parsed in order."""
    xml = """
<verification_report>
  <tier2_amendments>
    <add principle="proximity" severity="1" element="Cards">
      <issue>Gap too small</issue>
      <recommendation>Increase gap</recommendation>
      <reason>First miss</reason>
    </add>
    <add principle="repetition" severity="2" element="Buttons">
      <issue>Inconsistent style</issue>
      <recommendation>Standardize</recommendation>
      <reason>Second miss</reason>
    </add>
  </tier2_amendments>
</verification_report>
"""
    result = parse(xml)
    tier2_adds = [a for a in result.amendments if isinstance(a, AddFinding) and a.tier == "tier2"]
    assert len(tier2_adds) == 2
    assert tier2_adds[0].finding.principle == "proximity"
    assert tier2_adds[1].finding.principle == "repetition"


# ---------------------------------------------------------------------------
# Test 14: prose before <verification_report>
# ---------------------------------------------------------------------------

def test_parse_prose_before_block():
    """Prose before <verification_report> tag is ignored; amendments parsed correctly."""
    xml_with_prose = "Let me review the report carefully.\n\n" + FULL_VERIFICATION_XML
    result = parse(xml_with_prose)
    assert len(result.amendments) == 5
    assert result.parse_warnings == []


# ---------------------------------------------------------------------------
# Test 15: attributed <verification_report> tag
# ---------------------------------------------------------------------------

def test_parse_attributed_verification_report_tag():
    """<verification_report version="2"> (attributed) → no warnings, amendments parsed."""
    xml = """
<verification_report version="2">
  <assessment>Minor corrections applied</assessment>
  <tier2_amendments>
    <add principle="proximity" severity="1" element="Cards">
      <issue>Gap too small</issue>
      <recommendation>Increase gap</recommendation>
      <reason>Missed in primary pass</reason>
    </add>
  </tier2_amendments>
</verification_report>
"""
    result = parse(xml)
    assert result.parse_warnings == []
    assert len(result.amendments) == 1


# ---------------------------------------------------------------------------
# Test 16: verifier populates inventory inside <verification_report>
# ---------------------------------------------------------------------------

def test_parse_verification_report_with_inventory():
    """<inventory> inside <verification_report> populates VerificationResult.inventory."""
    xml = """
<verification_report>
  <assessment>Inventory was missing; populated now.</assessment>
  <inventory>Nav bar, hero CTA, 3 metric cards, sidebar</inventory>
  <structure_observation>2-column grid layout</structure_observation>
</verification_report>
"""
    result = parse(xml)
    assert result.inventory == "Nav bar, hero CTA, 3 metric cards, sidebar"
    assert result.structure_observation == "2-column grid layout"
    assert result.parse_warnings == []


# ---------------------------------------------------------------------------
# Test 17: apply_amendments propagates inventory onto AuditReport
# ---------------------------------------------------------------------------

def test_apply_amendments_propagates_inventory():
    """apply_amendments() with VerificationResult.inventory='X' overwrites AuditReport.inventory."""
    report = AuditReport(inventory="", structure_observation="")
    result = VerificationResult(
        inventory="Nav bar, hero CTA",
        structure_observation="2-column grid",
    )
    amended = apply_amendments(report, result)
    assert amended.inventory == "Nav bar, hero CTA"
    assert amended.structure_observation == "2-column grid"


# ---------------------------------------------------------------------------
# Test 18: apply_amendments does not overwrite when VerificationResult fields are None
# ---------------------------------------------------------------------------

def test_apply_amendments_does_not_overwrite_inventory_when_none():
    """apply_amendments() with VerificationResult.inventory=None leaves AuditReport.inventory unchanged."""
    report = AuditReport(inventory="Original inventory", structure_observation="Original SO")
    result = VerificationResult()  # inventory=None, structure_observation=None
    amended = apply_amendments(report, result)
    assert amended.inventory == "Original inventory"
    assert amended.structure_observation == "Original SO"
