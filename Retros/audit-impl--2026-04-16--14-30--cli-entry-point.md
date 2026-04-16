# Implementation Audit: CLI Entry Point (`uxiq`)
**Date**: 2026-04-16
**Status**: COMPLETE (with deviations)
**Working log**: .claude/worktrees/cli-entry-point/Working Logs/wlog--2026-04-16--14-30--cli-entry-point.md
**Impl plan**: Implementation Plans/impl--2026-04-16--14-30--cli-entry-point.md
**Spec**: specs/applied/spec--2026-04-16--14-30--cli-entry-point.md

---

## Independent Evaluator Verdict

Independent evaluation performed by direct file inspection of the worktree (no MCP Unity tools applicable — this is a Python project). All six files in scope were read and compared against the spec's Goal, Technical Design, Edge Cases, and Testing Strategy sections.

## Goals — Static Verification

| Goal | Status | Evidence |
|---|---|---|
| `uxiq analyze <image> --app-type <type>` command works | APPEARS MET | `cli.py` dispatches `_cmd_analyze`; `analyze_ui_screenshot` called with correct args |
| `uxiq list-app-types` prints 4 types to stdout | APPEARS MET | `_cmd_list_app_types` iterates `VALID_APP_TYPES`; working log confirms 4-line output |
| `uxiq --version` prints `uxiq 0.1.0` | APPEARS MET | `_get_version()` reads from `importlib.metadata`; working log confirms output |
| `--version` and `list-app-types` work without API key | APPEARS MET | `__init__.py` no longer has import-time guard; env check moved to `handler.py` |
| Env check raises `UIAnalyzerError` before API call | APPEARS MET (with deviation) | Guard is present in `handler.py` line 78, but checks `ANTHROPIC_API_KEY` instead of `UXIQ_ANTHROPIC_API_KEY` |
| Invalid `--app-type` → exit 1 with valid-types message | APPEARS UNMET | Uses argparse `choices=`; exits 2 with argparse message instead of exit 1 with custom message |
| `pyproject.toml` registers `uxiq` script | APPEARS MET | `[project.scripts]` section added at line 17–18 |
| `conftest.py` dead guard removed | APPEARS MET | Guard block removed; `pytest_configure` and `fixtures_dir` fixture preserved |
| `__init__.py` still exports all three symbols | APPEARS MET | All three symbols present in `__all__` |
| No new runtime dependencies | APPEARS MET | Only `argparse` and `importlib.metadata` (both stdlib) used |

## Properties Not Verifiable Without Play Mode

Not applicable — this is a Python project, not a Unity project.

---

## Failures & Root Causes

### Env var name diverges from spec (`ANTHROPIC_API_KEY` vs `UXIQ_ANTHROPIC_API_KEY`)
**Category**: `SPEC_DRIFT`
**What happened**: The spec's Decisions table, Technical Design (section 1), and Edge Cases table all specify `UXIQ_ANTHROPIC_API_KEY` as the env var name. The implementation checks `ANTHROPIC_API_KEY` in `handler.py` (line 78), `test_cli.py` (lines 184, 203, and docstrings), and `conftest.py` (now removed). The working log documents this as a "worktree baseline" deviation — the worktree branched from a commit before the main repo had the `UXIQ_` prefix.
**Why**: The worktree was created from a commit that predated the env var rename in the main repo. The implementing agent correctly detected the mismatch and adapted to the worktree's actual state rather than blindly applying the spec's values. However, this means the merged result will use `ANTHROPIC_API_KEY` in `handler.py`, diverging from what the spec requires.
**Evidence**: `handler.py` line 78: `if not os.getenv("ANTHROPIC_API_KEY"):` vs. spec section 1: `if not os.getenv("UXIQ_ANTHROPIC_API_KEY"):`. Working log Deviation 1 explicitly acknowledges this.

---

### Invalid `--app-type` exits 2 instead of 1 with custom message
**Category**: `SPEC_DRIFT`
**What happened**: The spec's Edge Cases table states: `--app-type value not in valid set → pydantic.ValidationError caught, print "Invalid app-type: X. Valid: forms, ..." → exit 1`. The implementation uses `choices=VALID_APP_TYPES` in argparse, which causes argparse itself to reject the value and exit with code 2 before `_cmd_analyze` is ever called. The `ValidationError` catch in `_cmd_analyze` is unreachable for this path. The corresponding test (`test_analyze_invalid_app_type_exits_2_mentions_valid`) was updated to assert exit 2, matching the implementation rather than the spec.
**Why**: The impl plan made a deliberate architectural decision (use argparse `choices=` for early validation), documented the spec deviation, and updated the test to match. The plan notes "argparse's own error message includes the valid choices list" — this is correct, but the exit code and message format differ from the spec's specified behavior. The plan did not explicitly confirm this deviation with the user before executing.
**Evidence**: spec edge case row 2: "exit 1, print 'Invalid app-type: X. Valid: ...'". `cli.py` line 96–97: `choices=VALID_APP_TYPES, metavar="APP_TYPE"`. `test_cli.py` line 76: `test_analyze_invalid_app_type_exits_2_mentions_valid` asserts `result.returncode == 2`.

---

### Post-Implementation Checklist items unchecked in impl plan
**Category**: `INCOMPLETE_TASK`
**What happened**: The impl plan's Post-Implementation Checklist has 11 items, all formatted as `- [ ]` (unchecked). The working log separately records all verification steps as passing (with `✓`), but the checklist in the plan document itself was never updated.
**Why**: The implementing agent performed all verifications but recorded them in the working log rather than updating the plan's checklist. This is a documentation gap, not a functional gap.
**Evidence**: `Implementation Plans/impl--2026-04-16--14-30--cli-entry-point.md` lines 600–610: all checklist items show `- [ ]`. Working log Verification section: all items shown as `✓`.

---

## Verification Gaps

None. This is a Python project — there are no MCP-inspected runtime values to flag as unconfirmed.

---

## Actionable Errors

### Error 1: `handler.py` checks wrong env var name
- **Category**: `SPEC_DRIFT`
- **File(s)**: `ui-analyzer/ui_analyzer/handler.py` line 78
- **What broke**: The spec and main repo convention require `UXIQ_ANTHROPIC_API_KEY`. The worktree uses `ANTHROPIC_API_KEY`. When this branch is merged to main (which already uses `UXIQ_ANTHROPIC_API_KEY` in other parts of the codebase), the env var check in `handler.py` will be inconsistent with the rest of the codebase.
- **Evidence**: `handler.py:78`: `if not os.getenv("ANTHROPIC_API_KEY"):` — spec section 1 specifies `UXIQ_ANTHROPIC_API_KEY`.
- **Suggested fix**: Change line 78 of `handler.py` to `if not os.getenv("UXIQ_ANTHROPIC_API_KEY"):` and update the error message string on line 79 to `"UXIQ_ANTHROPIC_API_KEY environment variable is not set."` This aligns the worktree with the spec and with the main repo's env var naming convention.

### Error 2: `test_cli.py` tests wrong env var name in two tests
- **Category**: `SPEC_DRIFT`
- **File(s)**: `ui-analyzer/tests/test_cli.py` lines 184, 203
- **What broke**: `test_list_app_types_works_without_api_key` pops `ANTHROPIC_API_KEY` (line 184) and `test_version_works_without_api_key` pops `ANTHROPIC_API_KEY` (line 203). After fix to Error 1, these tests must pop `UXIQ_ANTHROPIC_API_KEY` to correctly validate that the key-free commands work without the actual key.
- **Evidence**: `test_cli.py:184`: `env.pop("ANTHROPIC_API_KEY", None)`. `test_cli.py:203`: `env.pop("ANTHROPIC_API_KEY", None)`.
- **Suggested fix**: Change both `env.pop("ANTHROPIC_API_KEY", None)` lines to `env.pop("UXIQ_ANTHROPIC_API_KEY", None)`. Also update the docstrings on lines 182 and 200 to reference `UXIQ_ANTHROPIC_API_KEY`.

### Error 3: Invalid `--app-type` exits 2 instead of spec-required exit 1
- **Category**: `SPEC_DRIFT`
- **File(s)**: `ui-analyzer/ui_analyzer/cli.py` (argparse `choices=` on line 96), `ui-analyzer/tests/test_cli.py` line 76
- **What broke**: Spec edge case: invalid `--app-type` → exit 1, custom message "Invalid app-type: X. Valid: forms, ...". Current behavior: argparse exits 2 with "argument --app-type: invalid choice: X (choose from ...)". Exit code and message format both differ from spec.
- **Evidence**: Spec edge cases table row 2. `test_cli.py:76`: asserts `returncode == 2` (test written to match implementation, not spec).
- **Suggested fix**: Two options — (A) remove `choices=VALID_APP_TYPES` from the `--app-type` argument definition in `_build_parser`, allow any string through to `_cmd_analyze`, and let the `ValidationError` catch in `_cmd_analyze` produce the exit 1 with spec-required message; or (B) get explicit user sign-off that exit 2 / argparse message is the accepted behavior, then mark the test as documenting accepted deviation. Option A is the spec-conformant fix. If Option A is taken, update `test_analyze_invalid_app_type_exits_2_mentions_valid` to assert `returncode == 1` and check that stderr contains `"Invalid app-type"` and `"Valid:"`.

**Not actionable (requires human judgment):**
- **Env var name deviation scope**: The worktree's pre-existing code may use `ANTHROPIC_API_KEY` in other files beyond `handler.py`. If the main repo has already completed the rename to `UXIQ_ANTHROPIC_API_KEY` across all files, merging without fixing Errors 1–2 will create an inconsistency. A human should confirm the state of the main branch's env var usage before merging.
- **Unchecked Post-Implementation Checklist** (`INCOMPLETE_TASK`): All verifications were done and recorded in the working log. The unchecked checkboxes in the impl plan are a cosmetic gap, not a functional one. No fix required unless the team's process requires the plan document to be updated in place.

---

## Rule Violations

None. No CLAUDE.md hard rules were broken. The worktree workflow was followed (worktree branch, not direct commit to master). No `.prefab` files or equivalent restricted files were edited.

## Task Completeness
- **Unchecked items**: All 11 items in the impl plan's Post-Implementation Checklist remain unchecked (`- [ ]`). All verifications were performed and recorded as passing in the working log — this is a documentation gap only.

---

## Proposed Skill Changes

### impl-plan.md — require env var names to be verified against the worktree baseline, not the main repo
**Insert after**: any section covering "Environment Assumptions" or worktree baseline documentation
```diff
+ ### Worktree baseline vs. spec values
+ When a spec references specific string constants (env var names, config keys, module paths),
+ the impl plan author must verify these values against the WORKTREE's current state, not the
+ main repo. If the worktree predates a rename or refactor, the plan must explicitly note whether
+ to use the worktree's current value or the spec's target value, and why. The implementing agent
+ must NOT silently adapt to the worktree's value without flagging it as a spec deviation requiring
+ review before merge.
```
**Why**: Prevents silent `SPEC_DRIFT` when worktrees branch from older commits. The agent correctly detected and documented the mismatch, but silently applied the old value without confirming the deviation was acceptable before proceeding. A rule requiring explicit user confirmation before using a diverged value would have surfaced this.
[ ] Apply?

### CLAUDE.md — worktree baseline divergence requires user confirmation before proceeding
**Insert after**: `## Worktree Rules`
```diff
+ #### Spec constant mismatches require explicit confirmation
+ If the worktree's current code uses a different value (env var name, constant, path) than what
+ the spec specifies, STOP before adapting. State the mismatch to the user and ask which value
+ to use. Do not silently apply the worktree's value and call it a "deviation." Silent adaptations
+ create hidden spec drift that only surfaces at merge time.
```
**Why**: The implementing agent adapted `UXIQ_ANTHROPIC_API_KEY` → `ANTHROPIC_API_KEY` throughout without confirming this was acceptable. The deviation was documented, but by then the work was done.
[ ] Apply?

---

## Proposed learnings.md Additions
Copy-paste these into learnings.md under the relevant section:

```
- 2026-04-16 cli-entry-point: When a worktree branches from an older commit and the spec references renamed constants (env vars, config keys), the agent silently adapted to the worktree's old value rather than confirming the deviation. This created spec drift that will surface at merge time. → impl-plan.md: add rule requiring explicit user confirmation for any spec-constant mismatch detected in the worktree baseline.

- 2026-04-16 cli-entry-point: Implementing agent made an architectural decision (argparse choices= for early app-type validation) that changed the exit code for an invalid --app-type from spec-specified exit 1 to argparse's exit 2. The decision was well-reasoned and documented, but was not confirmed with the user before execution. The test was then written to match the implementation rather than the spec. → impl-plan.md or impl.md: add rule that architectural decisions departing from spec edge-case behavior require user confirmation before implementing.
```

---

## Re-Audit (after fix loop 1)
**Date**: 2026-04-16

> Re-audit — scoped to fixer's stated changes

### What the fixer did

The fixer addressed all three actionable errors from the original audit:

1. **Error 1 — `handler.py` wrong env var name**: Changed `os.getenv("ANTHROPIC_API_KEY")` → `os.getenv("UXIQ_ANTHROPIC_API_KEY")` and updated the error message string to match. (`handler.py` line 81–82.)

2. **Error 2 — `test_cli.py` wrong env var name in two tests**: Changed both `env.pop("ANTHROPIC_API_KEY", None)` lines to `env.pop("UXIQ_ANTHROPIC_API_KEY", None)` and updated the docstrings to reference `UXIQ_ANTHROPIC_API_KEY`. (`test_cli.py` lines 184 and 203.)

3. **Error 3 — invalid `--app-type` exits 2 instead of spec-required exit 1**: Removed `choices=VALID_APP_TYPES` from the argparse `--app-type` argument definition in `_build_parser()`. Any string now passes through argparse to `_cmd_analyze`, where the `ValidationError` catch block prints `"Invalid app-type: X. Valid: ..."` and calls `sys.exit(1)`. The test was updated from `test_analyze_invalid_app_type_exits_2_mentions_valid` to `test_analyze_invalid_app_type_exits_1_mentions_valid`, asserting `returncode == 1` and checking that stderr contains `"Invalid app-type"` and `"Valid:"`.

### Goals — Updated Status (changed rows only)

| Goal | Original Status | Updated Status | Evidence |
|---|---|---|---|
| Env check raises `UIAnalyzerError` before API call | APPEARS MET (with deviation) | APPEARS MET | `handler.py:81` now checks `UXIQ_ANTHROPIC_API_KEY`, matching spec |
| Invalid `--app-type` → exit 1 with custom message | APPEARS UNMET | APPEARS MET | `cli.py` no longer uses `choices=`; `_cmd_analyze` catches `ValidationError`, exits 1 with spec-required message |

### Test Suite Result

**CLI tests** (`tests/test_cli.py`): **10/10 passed** ✓

**Full suite** (`tests/`): **90 passed, 15 failed**

The 15 failures break down as:
- **11 new regressions** — `test_handler.py` unit tests that previously passed now fail because `handler.py` raises `UIAnalyzerError("UXIQ_ANTHROPIC_API_KEY environment variable is not set.")` at step 1 before any mocked call is reached. These tests mock `resolve` and `anthropic.Anthropic` but do not mock or set `UXIQ_ANTHROPIC_API_KEY` in the test environment.
  - `test_valid_file_path_returns_markdown_with_all_tiers`
  - `test_valid_url_axe_success_shows_authoritative`
  - `test_axe_failure_returns_string_not_exception`
  - `test_malformed_xml_returns_string_with_warning`
  - `test_api_timeout_raises_ui_analyzer_error`
  - `test_api_rate_limit_raises_ui_analyzer_error`
  - `test_handler_non_ui_preamble_passes_through`
  - `test_handler_no_preamble_output_unchanged`
  - `test_handler_whitespace_only_preamble_not_prepended`
  - `test_handler_no_xml_preamble_shown`
  - (1 pre-existing that also now fails for this reason: `test_full_analysis_file_path`)
- **4 pre-existing failures** (unchanged from original baseline):
  - `test_full_analysis_url` — Playwright not installed
  - `test_non_ui_image` — 401 auth error (real API key)
  - `test_app_type_forms` — 401 auth error (real API key)
  - `test_image_source_url_integration` — Playwright not installed

The original working log reported 100 passed / 5 pre-existing failures. After the fix, the count is 90 passed / 15 failed: 10 net regressions were introduced.

### Remaining Actionable Errors

### Error 1: `test_handler.py` unit tests regressed — env guard blocks all mocked scenarios
- **Category**: `SPEC_DRIFT` / regression introduced by fix
- **File(s)**: `ui-analyzer/tests/test_handler.py` (all unit test scenarios: lines ~79–250)
- **What broke**: After correcting `handler.py` to check `UXIQ_ANTHROPIC_API_KEY`, the 10 unit tests in `test_handler.py` that previously passed now fail at `handler.py:82` with `UIAnalyzerError: UXIQ_ANTHROPIC_API_KEY environment variable is not set.` These tests mock `resolve` and `anthropic.Anthropic` but never set or mock `UXIQ_ANTHROPIC_API_KEY` in the subprocess/test environment.
- **Evidence**: `pytest tests/test_handler.py` output: `E ui_analyzer.exceptions.UIAnalyzerError: UXIQ_ANTHROPIC_API_KEY environment variable is not set.` at `handler.py:82` for all 10 affected tests.
- **Suggested fix**: In each affected unit test, patch `os.getenv` for `UXIQ_ANTHROPIC_API_KEY` to return a truthy value, or use `monkeypatch.setenv("UXIQ_ANTHROPIC_API_KEY", "test-key-unit-tests")` at the test or fixture level. The cleanest approach is to add a session- or module-scoped autouse fixture in `conftest.py` that sets `UXIQ_ANTHROPIC_API_KEY=test-key-unit-tests` for all unit tests (excluding integration tests that skip on no real key). Alternatively, add `mocker.patch.dict(os.environ, {"UXIQ_ANTHROPIC_API_KEY": "test-key-unit-tests"})` to each affected test.

**Not actionable (requires human judgment):**
- **`test_full_analysis_file_path` regression**: This test was previously in the "pre-existing failure" category due to a 401 auth error (real API key invalid). It now also fails at the env guard before reaching the API. Once Error 1 above is fixed, this test will return to failing at the 401 auth error — which is still a pre-existing condition. No new fix needed beyond the env-var patch.

---

## Re-Audit (after fix loop 2)
**Date**: 2026-04-16

> Re-audit — scoped to fixer's stated changes

### What the fixer did

The fixer addressed the single remaining actionable error from fix loop 1 (Error 1: `test_handler.py` unit tests regressed — env guard blocks all mocked scenarios):

1. **`conftest.py` — added autouse `set_dummy_api_key` fixture**: Added a new `autouse=True` fixture that calls `monkeypatch.setenv("UXIQ_ANTHROPIC_API_KEY", "test-key-unit-tests")` for every test that is not marked `integration`. This ensures the env guard in `handler.py:81` is satisfied for all unit tests without requiring individual test changes.

2. **`test_handler.py` — updated `skip_if_no_key` sentinel**: Updated line 23 from `_REAL_KEY in ("",)` to `_REAL_KEY in ("", "test-key-unit-tests")`. This prevents the integration tests from running with the dummy key (which would reach the real API and fail with a 401). The `skip_if_no_key` marker now skips both when no key is set and when the dummy key is present.

### Goals — Updated Status (changed rows only)

| Goal | Prior Status (after fix loop 1) | Updated Status | Evidence |
|---|---|---|---|
| All unit tests pass without a real API key | UNMET (10 regressions) | APPEARS MET | `conftest.py` autouse fixture sets `UXIQ_ANTHROPIC_API_KEY=test-key-unit-tests`; full suite: 100 passed, 5 failed (all pre-existing) |

### Test Suite Result

**Full suite** (`tests/`): **100 passed, 5 failed**

The 5 failures are all pre-existing integration failures, unchanged from the original baseline:
- `test_full_analysis_file_path` — `UXIQ_ANTHROPIC_API_KEY` not set to a real key (skipped by `skip_if_no_key` guard; fails at env guard in this environment)
- `test_full_analysis_url` — `UXIQ_ANTHROPIC_API_KEY` not set to a real key (same)
- `test_non_ui_image` — `UXIQ_ANTHROPIC_API_KEY` not set to a real key (same)
- `test_app_type_forms` — `UXIQ_ANTHROPIC_API_KEY` not set to a real key (same)
- `test_image_source_url_integration` — Playwright browsers not installed

The 10 regressions introduced by fix loop 1 are fully resolved. The suite is back to its original 100-passed baseline.

### Remaining Actionable Errors

None.
