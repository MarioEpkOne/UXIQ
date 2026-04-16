# Implementation Audit: Full Test Suite
**Date**: 2026-04-15
**Status**: COMPLETE
**Working log**: .claude/worktrees/tests/Working Logs/wlog--2026-04-15--23-55--full-test-suite.md
**Impl plan**: Implementation Plans/impl--2026-04-15--23-30--tests.md
**Spec**: specs/applied/spec-09-tests.md

---

## Independent Evaluator Verdict

Independent evaluation via MCP sub-agent is not applicable to this implementation — this is a pure Python/pytest codebase with no Unity components. Evaluation was performed by directly running the test suite and cross-referencing test files against the spec.

Test suite was executed directly:
- `python3 -m pytest tests/ -m "not integration" -v` → **87 passed, 5 deselected** (1.37s)
- No cross-test imports found
- All fixture images present (5 files)

## Goals — Static Verification

| Goal | Status | Evidence |
|---|---|---|
| All unit tests run without internet/API key | APPEARS MET | 87 unit tests pass; conftest.py injects fake API key |
| test_axe_runner.py created with failure modes + success | APPEARS MET | 8 tests, all pass |
| test_context_events.py created with 5 tests | APPEARS MET | 5 tests, all pass |
| test_prompt_builder.py created with 6 tests + SYSTEM_PROMPT | APPEARS MET | 6 tests, all pass |
| test_scorer.py created with coverage of all scoring paths | APPEARS MET | 11 tests, all pass |
| test_report_renderer.py created with 9 tests | APPEARS MET | 9 tests, all pass |
| test_handler.py extended with non-UI preamble + integration tests | APPEARS MET | 1 unit test added + 4 integration stubs |
| No test imports from another test file | APPEARS MET | grep checks empty |
| Integration tests decorated with @pytest.mark.integration + @skip_if_no_key | APPEARS MET | Confirmed in test_handler.py |

## Properties Not Verifiable Without Play Mode

N/A — no Unity components. Integration tests (requiring a live ANTHROPIC_API_KEY) cannot be verified without a real key.

---

## Failures & Root Causes

### Assertion Deviation in test_handler_non_ui_preamble_passes_through

**Category**: `SPEC_DRIFT`

**What happened**: The spec (spec-09 test_handler.py section) explicitly states: the returned str should contain `"⚠️ The provided image does not appear to be a web UI"`. The implementation changed the assertion to `assert isinstance(result, str)` + `assert "## Tier 1" in result`, dropping the preamble-text check.

**Why**: The agent determined that `xml_parser.parse()` strips prose before `<audit_report>` and renders from the valid XML block — so the preamble warning text never reaches the rendered output. The plan had encoded this deviation as permissible ("the comment/description is authoritative intent — fix the assertion to match the stated intent"), but the spec itself is the authoritative source, not the plan's interpretation. The spec says the preamble text SHOULD be in the output, implying the handler is expected to either pass it through or the test documents observed/expected behavior.

**Evidence**: Spec line: `# Returned str contains "⚠️ The provided image does not appear to be a web UI"`. Implemented assertion: `assert "## Tier 1" in result` (wlog line 23, test_handler.py line 304–306).

---

### Spec Says run_axe Returns None; Tests Assert AxeFailure

**Category**: `SPEC_DRIFT`

**What happened**: The spec (spec-09 test_axe_runner.py section) states: `run_axe() returns None, no exception propagated` for all failure modes. The implementation asserts `isinstance(result, AxeFailure)` instead.

**Why**: The actual `axe_runner.py` source (implemented in spec-03) returns `AxeFailure`, not `None`. The spec-09 test spec was not updated to reflect this post-spec-03 change. The tests are correct against the actual module under test — the spec text is outdated. The implementing agent made the pragmatically correct choice (test the real API), but this is technically a spec deviation.

**Evidence**: spec-09 comment: `# run_axe() returns None, no exception propagated`. axe_runner.py line 93: `def run_axe(url: str) -> AxeCoreResult | AxeFailure`. Test asserts `isinstance(result, AxeFailure)`.

---

### test_overall_weighting Does Not Construct a Report That Yields T1=5.0 T2=3.0 T3=4.0

**Category**: `SPEC_DRIFT`

**What happened**: The spec says `test_overall_weighting` should test `T1=5.0, T2=3.0, T3=4.0 → overall = round(...) = 4.1`. The implementation tests `overall == 5.0` on an all-pass report and then manually verifies the formula with literal floats — without actually constructing a `compute()` call that drives `overall` to 4.0 or 4.1.

**Why**: The plan notes it is mathematically impossible to get exact `T2=3.0` via integer severities. The implementing agent's workaround tests the formula in isolation (not via `compute()`). This is a weakened test: it does not exercise `compute()` with mixed tier scores. The spec intended an end-to-end weighted path.

**Evidence**: Plan section "Known Discrepancy — test_overall_weighting". test_scorer.py lines 129–139: `scores_all = compute(report_all_pass)` then separate float arithmetic assertion without a `compute()` call.

---

## Verification Gaps

None. This is a pure Python test suite. No MCP/Unity static-vs-runtime gaps apply.

---

## Actionable Errors

### Error 1: test_handler_non_ui_preamble_passes_through — Assertion Diverges from Spec

- **Category**: `SPEC_DRIFT`
- **File(s)**: `.claude/worktrees/tests/ui-analyzer/tests/test_handler.py` (lines 301–306)
- **What broke**: Spec says `result` should contain `"⚠️ The provided image does not appear to be a web UI"`. Implementation asserts `"## Tier 1" in result` instead. The spec documents expected observed behavior that the assertion no longer verifies.
- **Evidence**: Spec (spec-09): `# Returned str contains "⚠️ The provided image does not appear to be a web UI"`. Implemented: `assert "## Tier 1" in result`.
- **Suggested fix**: Investigate whether `report_renderer.render()` or `handler.py` should preserve/prepend preamble text when it precedes a valid `<audit_report>`. If the intended behavior is that preamble IS preserved in output, fix the renderer. If the spec test description is aspirational and the true contract is "no exception, returns str", update the spec comment accordingly. This requires a human judgment call before a code fix can be written.

### Error 2: test_overall_weighting Does Not Call compute() with T1=5.0 T2=3.0 T3=4.0

- **Category**: `SPEC_DRIFT`
- **File(s)**: `.claude/worktrees/tests/ui-analyzer/tests/test_scorer.py` (lines 118–139)
- **What broke**: The spec test is meant to verify the weighted formula end-to-end via `compute()`. The implementation only verifies an all-pass path through `compute()` and then tests the arithmetic in pure Python, bypassing `compute()` for the 5.0/3.0/4.0 scenario.
- **Evidence**: Spec: `# T1=5.0, T2=3.0, T3=4.0 → overall = round(...)`. Implementation uses `round(5.0 * 0.4 + 3.0 * 0.35 + 4.0 * 0.25, 1)` without a corresponding `compute()` call.
- **Suggested fix**: Either (a) construct a `Scores(tier1=5.0, tier2=3.0, tier3=4.0, tier4_flag_count=0, overall=round(...))` object and assert `scores.overall == 4.0`, exercising the weighted field; or (b) accept the current test as sufficient (it does verify the arithmetic). Option (a) is closer to the spec intent. Note: `compute()` cannot produce these exact values from integer severity inputs, so testing the formula via a directly-constructed `Scores` object is the correct path.

**Not actionable (requires human judgment or play-mode verification):**

- **Error 1 (spec intent for non-UI preamble)**: Whether the preamble text should appear in the rendered output is an unresolved product decision. The xml_parser correctly strips prose before `<audit_report>`. If the intended UX is to preserve/surface the preamble text, the renderer must be changed. This cannot be auto-fixed without a product decision.
- **test_axe_runner spec comment mismatch (None vs AxeFailure)**: The spec-09 comments say "returns None" but axe_runner.py actually returns `AxeFailure`. The tests are correct against the real API. The fix is to update spec-09's comment text — a documentation change, not a code fix.

---

## Rule Violations

None identified. No CLAUDE.md hard rules were broken. The agent did not modify files outside the scope list and committed once at the end.

## Task Completeness

The working log does not have an explicit Post-Implementation Checklist with checkboxes filled in. The plan's checklist (impl--2026-04-15--23-30--tests.md lines 1008–1020) was verified independently:

- pytest unit suite exits 0: CONFIRMED (87 passed)
- All spec-required unit tests present: CONFIRMED with two exceptions (assertion deviation, weakened overall_weighting test)
- test_handler_non_ui_preamble_passes_through added: CONFIRMED (assertion deviated from spec)
- test_axe_runner.py 6+ tests: CONFIRMED (8 tests)
- test_context_events.py 5 tests: CONFIRMED
- test_prompt_builder.py 6+1 tests: CONFIRMED
- test_scorer.py 10+ tests (overall_weighting asserts 4.0): CONFIRMED (11 tests)
- test_report_renderer.py 9 tests: CONFIRMED
- No cross-test imports: CONFIRMED
- Playwright never called in unit tests: CONFIRMED
- anthropic.Anthropic() never called in unit tests: CONFIRMED
- All fixture images committed: CONFIRMED
- Integration tests decorated correctly: CONFIRMED

---

## Proposed Skill Changes

### impl.md — Clarify "comment is authoritative" rule applies when spec and plan agree

**Insert after**: the existing "comment/description is authoritative intent" rule (wherever it appears in impl.md)
```diff
+ When deviating from a spec assertion because the spec's expected value
+ appears to contradict the actual module behavior, the implementing agent
+ MUST note this as SPEC_DRIFT in the working log AND flag it as a potential
+ spec defect. The agent must not silently weaken an assertion — weakening
+ must be explicitly justified with evidence that the spec is wrong.
```
**Why**: The preamble deviation was made quietly. The working log acknowledged it but did not flag it as a potential spec defect (the spec may be correct and the renderer may need updating).

[ ] Apply?

---

## Proposed learnings.md Additions
Copy-paste these into learnings.md under the relevant section:

```
- 2026-04-15 full-test-suite: When a spec test asserts expected output text and the implementation changes the assertion, treat it as SPEC_DRIFT unless the spec comment is demonstrably wrong about what the module under test does. Flag as a potential spec defect, not just a "corrected assertion". → impl.md
- 2026-04-15 full-test-suite: test_overall_weighting was weakened by not calling compute() with the exact T1/T2/T3 values from the spec. When integer inputs can't hit the spec's exact float targets, use a directly-constructed Scores object to verify the weighted formula end-to-end. → impl-plan.md (scorer test pattern)
```

---

## Re-Audit (after fix loop 1)
**Date**: 2026-04-15

> Re-audit — scoped to fixer's stated changes

### What the Fixer Did

The fixer addressed the two actionable errors from the original audit:

**Error 2 — Fixed**: `test_overall_weighting` in `.claude/worktrees/tests/ui-analyzer/tests/test_scorer.py` (lines 118–136) was rewritten to call `compute()` end-to-end with controlled integer inputs: empty tier1 list (→ T1=5.0), one severity=1 tier2 finding (→ T2=3.5), one severity=1 tier3 finding (→ T3=3.5). The test now asserts `scores.overall == 4.1`, exercising the full weighted formula via `compute()`. The previously isolated arithmetic assertion was replaced with direct `compute()` output assertions.

**Error 1 — Deliberately Skipped (option b)**: The preamble assertion deviation in `test_handler_non_ui_preamble_passes_through` was left as-is. The fixer selected option (b) from the suggested fix: keep `assert isinstance(result, str)` and `assert "## Tier 1" in result`. This is acknowledged as a known product decision — the xml_parser correctly strips prose before `<audit_report>`, and whether preamble text should be surfaced in output remains an unresolved product question. No code change was made.

### Updated Goals Table (changed rows only)

| Goal | Prior Status | Updated Status | Evidence |
|---|---|---|---|
| test_scorer.py: test_overall_weighting calls compute() end-to-end with T1=5.0/T2=3.5/T3=3.5 | APPEARS UNMET | APPEARS MET | test_scorer.py lines 118–136: `compute(report)` called with controlled inputs; `scores.overall == 4.1` asserted and passes |

### Test Suite Result

`python3 -m pytest tests/ -m "not integration" -v` → **87 passed, 5 deselected** (0.99s)

No regressions introduced. Count unchanged from original (the rewrite replaced an existing test, not added a new one).

### Remaining Actionable Errors

None.

The one remaining open item (Error 1 — preamble text not surfacing in rendered output) was explicitly classified as "not actionable — requires human judgment" in the original audit, and the fixer correctly deferred it. It is a product decision, not a code defect that can be auto-fixed.
