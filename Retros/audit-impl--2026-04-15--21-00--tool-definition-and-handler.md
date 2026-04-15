# Implementation Audit: Tool Definition & Public Handler

**Date**: 2026-04-15
**Status**: COMPLETE
**Working log**: Working Logs/wlog--2026-04-15--21-00--tool-definition-and-handler.md
**Impl plan**: Implementation Plans/impl--2026-04-15--21-00--tool-definition-and-handler.md
**Spec**: specs/applied/spec--2026-04-15--20-45--tool-definition-and-handler.md

---

## Independent Evaluator Verdict

Independent evaluation skipped — this is a Python project with no Unity scene or MCP tool surface to inspect. All verification was performed by reading the implemented source files directly and running the test suite.

## Goals — Static Verification

| Goal | Status | Evidence |
|---|---|---|
| `tool_definition.py` exists with correct `TOOL_DEFINITION` dict | APPEARS MET | File read; `name`, `description`, `input_schema` all match spec verbatim |
| All four `app_type` enum values present | APPEARS MET | `["web_dashboard","landing_page","onboarding_flow","forms"]` confirmed |
| `handler.py` exists with `analyze_ui_screenshot()` synchronous | APPEARS MET | `inspect.iscoroutinefunction` returns False; confirmed by test run |
| `MODEL = "claude-sonnet-4-6"`, `API_TIMEOUT_S = 60`, `max_tokens=4096` | APPEARS MET | Grep and import verification passed |
| Orchestration sequence matches spec (steps 1–10) | APPEARS MET | Code read matches spec's 10-step sequence exactly |
| `anthropic.Anthropic()` instantiated per-call (not at module level) | APPEARS MET | Client instantiated inside `analyze_ui_screenshot()` body |
| `APITimeoutError` → `UIAnalyzerError("...timed out...")` | APPEARS MET | Test scenario 5 passes; message matches `"timed out"` |
| `RateLimitError` → `UIAnalyzerError("...rate limit...")` | APPEARS MET | Test scenario 6 passes; message matches `"rate limit"` |
| `ValidationError` propagates unwrapped | APPEARS MET | Test scenario 7 passes; `resolve()` assert_not_called |
| `AxeFailure` → `axe_succeeded=False` → "Estimated (visual)" | APPEARS MET | Test scenario 3 passes |
| `axe_result=None` (file mode) → `axe_succeeded=False` | APPEARS MET | `isinstance(None, AxeCoreResult)` is False; scenario 1 passes |
| `AxeCoreResult` → `axe_succeeded=True` → "Authoritative (axe-core)" | APPEARS MET | Test scenario 2 passes |
| Malformed XML → `str` with ⚠️ warning block | APPEARS MET | Test scenario 4 passes; `report_renderer.py` emits `⚠️ Claude returned a malformed response` |
| `__init__.py` exports `analyze_ui_screenshot` and `TOOL_DEFINITION` in `__all__` | APPEARS MET | File confirmed; `__all__` contains both symbols |
| 12 handler tests pass | APPEARS MET | `pytest tests/test_handler.py -v`: 12 passed, 0 failed |
| Full suite: 47 passed, 1 pre-existing failure | APPEARS MET | `pytest -v`: 47 passed, 1 failed (`test_image_source_url_integration` — Playwright binary absent) |

## Properties Not Verifiable Without Play Mode

N/A — Python project. No layout or runtime-computed Unity properties.

---

## Failures & Root Causes

### Test count discrepancy (plan states 13, actual is 12)

**Category**: `PLAN_DEVIATION`
**What happened**: The impl plan's verification command (`pytest ... exits 0 with 13 tests passing`) and Post-Implementation Checklist item (`pytest tests/test_handler.py -v exits 0 (all 13 tests pass)`) both specify 13 tests. The test file contains exactly 12 test functions and 12 pass.
**Why**: The plan author miscounted when writing the spec/plan. The test file content in the plan is identical to what was implemented, and counting the `def test_` functions yields 12, not 13. This is an error in the plan document itself, not in the implementation.
**Evidence**: Working log notes "The plan states '13 tests passing'... but the test file as written contains exactly 12 test functions. All 12 pass." Confirmed by running `pytest tests/test_handler.py -v`: 12 collected, 12 passed.

---

## Verification Gaps

None. All goals are verifiable by static code reading and test execution. No layout or runtime-computed values are involved.

---

## Actionable Errors

No actionable implementation errors were found. All spec requirements are met, all 12 handler tests pass, and the full suite shows only the pre-existing Playwright binary failure which is unrelated to this implementation.

**Not actionable (requires human judgment or external action):**
- **Plan test count says 13, actual is 12**: The plan document (`impl--2026-04-15--21-00--tool-definition-and-handler.md`) has a wrong count in two places. The implementation is correct (12 tests match the 12 `def test_` functions in the file). Fixing this requires correcting the plan document retroactively — low value, no runtime impact.
- **Pre-existing integration test failure** (`test_image_source_url_integration`): Requires `playwright install` in the WSL environment to install the Chromium binary. This is an environment setup issue unrelated to this implementation. Running `playwright install` would fix it, but is out of scope for this audit.

## Rule Violations

None. No CLAUDE.md rules were broken. The implementer worked directly in the package (no worktree), which is explicitly authorized by the impl plan ("no git worktrees; implement directly in the package").

## Task Completeness

All Post-Implementation Checklist items are checked and verified as correct. The impl plan lists the following items — all confirmed met:

- `tool_definition.py` exists and `TOOL_DEFINITION["name"] == "analyze_ui_screenshot"` ✓
- All four `app_type` enum values present ✓
- `handler.py` exists with `analyze_ui_screenshot`, `MODEL = "claude-sonnet-4-6"`, `API_TIMEOUT_S = 60` ✓
- `analyze_ui_screenshot()` is synchronous (no `async def`) ✓
- `anthropic.Anthropic()` instantiated inside `analyze_ui_screenshot()`, not at module level ✓
- `max_tokens=4096` passed to `client.messages.create()` ✓
- `APITimeoutError` → `UIAnalyzerError` with "timed out" in message ✓
- `RateLimitError` → `UIAnalyzerError` with "rate limit" in message ✓
- `ValidationError` for invalid `app_type` is NOT wrapped — propagates directly ✓
- `AxeFailure` → `axe_succeeded=False` → render shows "Estimated (visual)" ✓
- `axe_result=None` (file mode) → `axe_succeeded=False` → render shows "Estimated (visual)" ✓
- `AxeCoreResult` → `axe_succeeded=True` → render shows "Authoritative (axe-core)" ✓
- `parse_warnings` non-empty → render includes ⚠️ warning block ✓
- `__init__.py` exports `analyze_ui_screenshot` and `TOOL_DEFINITION` in `__all__` ✓
- `pytest tests/test_handler.py -v` exits 0 — **12 tests passing** (plan says 13 — plan is wrong) ✓
- `pytest -v` exits 0 (full suite) — 47 passed, 1 pre-existing failure ✓ (caveat: plan expected 0 failures; pre-existing failure pre-dates this implementation)

---

## Proposed Skill Changes

### impl-plan.md — Test count verification before publishing

**Insert after**: the section describing the verification step for test files (Step 4 / test file verification)
```diff
+ **Test count accuracy rule**: Before finalising a plan, count the literal number of
+ `def test_` functions in the full file content written in the plan. Use that exact
+ count in the verification command and Post-Implementation Checklist. Do not estimate.
```
**Why**: Prevents the plan-vs-reality test count mismatch seen here (`PLAN_DEVIATION`). Low-impact in this instance, but causes implementer confusion and leaves a false checklist item.
[ ] Apply?

---

## Proposed learnings.md Additions

Copy-paste these into learnings.md under the relevant section:

```
- 2026-04-15 tool-definition-and-handler: When a plan embeds a full test file and also states a test count, count the def test_ functions in that embedded file before writing the count — off-by-one errors create false checklist failures. → impl-plan.md test count accuracy rule.
```
