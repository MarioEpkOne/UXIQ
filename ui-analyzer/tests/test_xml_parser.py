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


# ---------------------------------------------------------------------------
# test_parse_attributed_audit_report_tag (Bug 1 regression test)
# ---------------------------------------------------------------------------

def test_parse_attributed_audit_report_tag():
    """<audit_report version="1"> (attributed) → parses correctly, no warnings, findings populated."""
    xml = """
<audit_report version="1">
  <confidence level="high"></confidence>
  <inventory>Nav bar, hero button</inventory>
  <structure_observation>2-column layout</structure_observation>
  <tier1_findings>
    <finding criterion="1.4.3" element=".nav-link" result="FAIL" estimated="false">
      <observed>contrast ratio 2.8:1</observed>
      <required>4.5:1 for normal text</required>
      <recommendation>Change to #374151</recommendation>
    </finding>
  </tier1_findings>
  <tier2_findings/>
  <tier3_findings/>
  <tier4_findings/>
</audit_report>
"""
    report = parse(xml)
    assert isinstance(report, AuditReport)
    assert len(report.tier1_findings) == 1
    assert report.tier1_findings[0].criterion == "1.4.3"
    assert report.parse_warnings == []


def test_parse_attributed_audit_report_with_prose():
    """Prose + attributed <audit_report ...> → preamble ignored, findings parsed correctly."""
    prose = "Here is my detailed analysis:\n\n"
    xml = """<audit_report version="1">
  <confidence level="medium"></confidence>
  <inventory>A button</inventory>
  <structure_observation>simple</structure_observation>
  <tier1_findings/>
  <tier2_findings/>
  <tier3_findings/>
  <tier4_findings/>
</audit_report>"""
    report = parse(prose + xml)
    assert isinstance(report, AuditReport)
    assert report.inventory == "A button"
    assert report.parse_warnings == []
