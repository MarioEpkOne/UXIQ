"""Tests for verification_parser.apply_amendments()."""

from __future__ import annotations

from ui_analyzer.verification_parser import (
    AddFinding,
    CorrectFinding,
    RemoveFinding,
    VerificationResult,
    apply_amendments,
)
from ui_analyzer.xml_parser import (
    AuditReport,
    Tier1Finding,
    Tier2Finding,
    Tier3Finding,
    Tier4Finding,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_t1(criterion="1.4.3", element=".nav") -> Tier1Finding:
    return Tier1Finding(
        criterion=criterion, element=element, result="FAIL",
        estimated=False, observed="low contrast", required="4.5:1",
        recommendation="Fix it",
    )


def _make_t2(principle="proximity", element="Cards", severity=2) -> Tier2Finding:
    return Tier2Finding(
        principle=principle, severity=severity, element=element,
        issue="Gap too small", recommendation="Increase gap",
    )


def _make_report(**kwargs) -> AuditReport:
    defaults = dict(
        tier1_findings=[_make_t1()],
        tier2_findings=[_make_t2()],
        tier3_findings=[],
        tier4_findings=[],
    )
    defaults.update(kwargs)
    return AuditReport(**defaults)


# ---------------------------------------------------------------------------
# Test 1: add appends finding to correct tier
# ---------------------------------------------------------------------------

def test_add_appends_to_tier():
    """AddFinding appends the finding to the correct tier list."""
    report = _make_report(tier3_findings=[])
    new_t3 = Tier3Finding(
        principle="consistency", severity=1, element="Buttons",
        issue="Inconsistent style", recommendation="Standardize",
    )
    vr = VerificationResult(amendments=[AddFinding(tier="tier3", finding=new_t3, reason="missed")])
    amended = apply_amendments(report, vr)
    assert len(amended.tier3_findings) == 1
    assert amended.tier3_findings[0].principle == "consistency"


# ---------------------------------------------------------------------------
# Test 2: remove removes matching finding
# ---------------------------------------------------------------------------

def test_remove_removes_matching_finding():
    """RemoveFinding removes the first finding matching the match_key."""
    report = _make_report()
    # match_key for tier1 is "criterion|element"
    vr = VerificationResult(amendments=[
        RemoveFinding(tier="tier1", match_key="1.4.3|.nav", reason="not visible")
    ])
    amended = apply_amendments(report, vr)
    assert amended.tier1_findings == []


# ---------------------------------------------------------------------------
# Test 3: remove with non-matching match_key is silently skipped
# ---------------------------------------------------------------------------

def test_remove_nonexistent_match_key_skipped():
    """RemoveFinding with no matching key leaves tier unchanged."""
    report = _make_report()
    vr = VerificationResult(amendments=[
        RemoveFinding(tier="tier1", match_key="9.9.9|.nonexistent", reason="test")
    ])
    amended = apply_amendments(report, vr)
    assert len(amended.tier1_findings) == 1  # unchanged


# ---------------------------------------------------------------------------
# Test 4: correct updates specified field
# ---------------------------------------------------------------------------

def test_correct_updates_field():
    """CorrectFinding updates the named field on the matched finding."""
    report = _make_report()
    vr = VerificationResult(amendments=[
        CorrectFinding(tier="tier1", match_key="1.4.3|.nav", field="result", new_value="PASS", reason="wrong")
    ])
    amended = apply_amendments(report, vr)
    assert amended.tier1_findings[0].result == "PASS"


# ---------------------------------------------------------------------------
# Test 5: correct with unknown field is silently skipped
# ---------------------------------------------------------------------------

def test_correct_unknown_field_skipped():
    """CorrectFinding with a field that doesn't exist on the finding is silently skipped."""
    report = _make_report()
    vr = VerificationResult(amendments=[
        CorrectFinding(
            tier="tier1", match_key="1.4.3|.nav",
            field="nonexistent_field", new_value="foo", reason="test",
        )
    ])
    amended = apply_amendments(report, vr)
    # Finding unchanged (still has result FAIL)
    assert amended.tier1_findings[0].result == "FAIL"


# ---------------------------------------------------------------------------
# Test 6: removing all findings from a tier leaves empty list
# ---------------------------------------------------------------------------

def test_remove_all_findings_leaves_empty_list():
    """Removing all findings from a tier leaves an empty list, not None."""
    report = _make_report(tier2_findings=[_make_t2(), _make_t2(element="Header")])
    vr = VerificationResult(amendments=[
        RemoveFinding(tier="tier2", match_key="proximity|Cards", reason="test"),
        RemoveFinding(tier="tier2", match_key="proximity|Header", reason="test"),
    ])
    amended = apply_amendments(report, vr)
    assert amended.tier2_findings == []
    assert amended.tier2_findings is not None


# ---------------------------------------------------------------------------
# Test 7: apply_amendments does not mutate the original report
# ---------------------------------------------------------------------------

def test_apply_does_not_mutate_original():
    """apply_amendments returns a new AuditReport; the original is unchanged."""
    original = _make_report()
    vr = VerificationResult(amendments=[
        RemoveFinding(tier="tier1", match_key="1.4.3|.nav", reason="test")
    ])
    amended = apply_amendments(original, vr)
    assert len(original.tier1_findings) == 1  # original unchanged
    assert len(amended.tier1_findings) == 0


# ---------------------------------------------------------------------------
# Test 8: correct int field (severity) updates as int not str
# ---------------------------------------------------------------------------

def test_correct_int_field_preserves_type():
    """CorrectFinding on an int field (severity) stores the value as int."""
    report = _make_report()
    vr = VerificationResult(amendments=[
        CorrectFinding(tier="tier2", match_key="proximity|Cards", field="severity", new_value="3", reason="worse than thought")
    ])
    amended = apply_amendments(report, vr)
    assert amended.tier2_findings[0].severity == 3
    assert isinstance(amended.tier2_findings[0].severity, int)
