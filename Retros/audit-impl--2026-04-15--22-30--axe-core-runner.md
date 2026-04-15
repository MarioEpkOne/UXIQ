# Implementation Audit: axe-core Runner
**Date**: 2026-04-15
**Status**: INCOMPLETE — one BLOCKER found
**Working log**: Working Logs/wlog--2026-04-15--22-30--axe-core-runner.md
**Impl plan**: Implementation Plans/impl--2026-04-15--22-30--axe-core-runner.md — MISSING (not present in `Implementation Plans/`)
**Spec**: specs/applied/spec--2026-04-15--18-30--axe-core-runner.md

---

## Independent Evaluator Verdict

Independent evaluation performed directly — this is a Python module, not a Unity scene. Sub-agent MCP tooling is not applicable. All verification was done by reading the implementation source and executing the module under Python 3.12.3 / Playwright 1.58.0.

All import, dataclass, constant, and parsing behaviors were verified via Python execution. One blocker was found: `page.evaluate()` in Playwright's Python API does not accept a `timeout` keyword argument. The spec itself contains this defect; the implementation faithfully reproduced it. At runtime, every call to `run_axe()` that reaches the evaluation step will raise a `TypeError`, which is caught by the inner `except Exception` block and mapped to `AxeFailure(reason="axe-core timed out")`. axe-core never actually runs.

## Goals — Static Verification

| Goal | Status | Evidence |
|---|---|---|
| Module exists and is importable | APPEARS MET | `python3 -c "from ui_analyzer.axe_runner import run_axe, AxeCoreResult, AxeFailure, AxeViolation, AxeCriterionResult; print('OK')"` → `OK` |
| All five public names exported | APPEARS MET | Import check confirmed all five names present |
| `run_axe` is synchronous, not async | APPEARS MET | `inspect.iscoroutinefunction(run_axe)` → `False` |
| Signature is `(url: str) -> AxeCoreResult \| AxeFailure` | APPEARS MET | `inspect.signature(run_axe)` confirmed |
| `AxeCoreResult.source` default is exact fixed string | APPEARS MET | `AxeCoreResult().source == 'axe-core — authoritative, do not re-estimate'` → `True` |
| axe-core CDN URL pinned to 4.9.1 | APPEARS MET | `AXE_CDN_URL` confirmed `cdnjs.cloudflare.com/.../4.9.1/axe.min.js` |
| `AXE_TIMEOUT_MS` is `10_000` | APPEARS MET | `AXE_TIMEOUT_MS == 10000` confirmed |
| `page.goto()` uses `timeout=30_000, wait_until="networkidle"` | APPEARS MET | Line 108 in axe_runner.py |
| WCAG `runOnly` tags are `wcag2a`, `wcag2aa`, `wcag21aa` | APPEARS MET | Lines 128–130 in axe_runner.py |
| All failure paths return `AxeFailure` (no exceptions propagated) | APPEARS MET (static) | All exception handlers return `AxeFailure`; outer catch handles remainder |
| `UIAnalyzerError` not imported or raised | APPEARS MET | Only appears in docstring/comments — confirmed by grep |
| `image_source` not imported | APPEARS MET | Only appears in module docstring comment — confirmed by grep |
| `incomplete` / `inapplicable` sections ignored | APPEARS MET | `_parse_axe_result` only reads `violations` and `passes` |
| Missing criteria omitted from findings (no placeholder) | APPEARS MET | Verified with empty-output test |
| Criteria in `passes` produce `AxeCriterionResult(result="PASS")` | APPEARS MET | Verified with passes-only test |
| Violations produce `AxeCriterionResult(result="FAIL")` with violations list | APPEARS MET | Verified with violation test |
| `AxeViolation.result` is always `"FAIL"` (hard-coded) | APPEARS MET | Hard-coded in `AxeViolation` constructor call at line 188 |
| Contrast ratio extracted from `nodes[].any[].data.contrastRatio` | APPEARS MET | `_extract_contrast()` confirmed; test shows `ratio=2.5, required_ratio=4.5` |
| Size extracted from `nodes[].any[].data.width/height/minSize` | APPEARS MET | `_extract_size()` confirmed; test shows `size_px='18x18', required_px='24x24'` |
| Browser launched and closed per `run_axe()` call | APPEARS MET | `sync_playwright()` context manager + `browser.close()` in each code path |
| `logger = logging.getLogger(__name__)` used, no `print()` | APPEARS MET | Confirmed; `print(` not found in source |
| **`axe.run()` timeout enforcement** | **APPEARS UNMET — BLOCKER** | `page.evaluate()` in Playwright Python 1.58.0 does NOT accept a `timeout` kwarg. Calling it with `timeout=AXE_TIMEOUT_MS` raises `TypeError`, caught by inner `except Exception`, returns `AxeFailure(reason="axe-core timed out")` — axe never runs. |

## Properties Not Verifiable Without Runtime

- Whether axe-core actually runs and returns results for a live URL (requires network + browser)
- Whether CDN injection succeeds against a live page (requires network)
- End-to-end behavior of page load timeout path (requires a slow/nonresponsive server)

---

## Failures & Root Causes

### page.evaluate() receives unsupported timeout kwarg — axe never executes

**Category**: `SPEC_DRIFT` (implementation faithfully reproduced a spec defect), `INCOMPLETE_TASK` (functional behavior never achievable as written)

**What happened**: The spec's Execution Sequence code block calls `page.evaluate(..., timeout=AXE_TIMEOUT_MS)`. The Playwright Python API's `Page.evaluate()` method signature is `(self, expression: str, arg: Optional[Any] = None)` — it does not accept a `timeout` parameter. The implementation copied this call verbatim. At runtime, every execution that reaches the `page.evaluate()` call raises `TypeError: evaluate() got an unexpected keyword argument 'timeout'`. This exception is caught by the `except Exception as e:` block in step 3, which maps it to `AxeFailure(reason="axe-core timed out")`. axe-core never actually executes.

**Why**: The spec author used the Playwright JavaScript API as a reference (where `page.evaluate()` does accept a timeout option object), but the Python API uses a different call pattern. The implementer reproduced the spec call without checking the Python API signature. The post-implementation checklist did not include a verification that `page.evaluate()` accepts the specified kwargs.

**Evidence**:
- `Page.evaluate` signature: `(self, expression: str, arg: Optional[Any] = None)` — confirmed via `inspect.signature(Page.evaluate)` on Playwright 1.58.0
- Spec line 157: `timeout=AXE_TIMEOUT_MS,` passed as kwarg to `page.evaluate()`
- Implementation line 133–134: `page.evaluate(..., timeout=AXE_TIMEOUT_MS,)` — same defect
- The `except Exception as e:` at line 135 catches the `TypeError` and returns `AxeFailure(reason="axe-core timed out")` — masking the defect as a "timeout" rather than a code error

### Implementation plan missing from repository

**Category**: `INCOMPLETE_TASK`

**What happened**: The working log references `Implementation Plans/impl--2026-04-15--22-30--axe-core-runner.md` as the impl plan, but this file does not exist in the `Implementation Plans/` directory.

**Why**: Unknown — the file may not have been created, or may have been created in the wrong repo/location.

**Evidence**: `ls "/mnt/c/Users/Epkone/UXIQ-spec-03/Implementation Plans/"` returns only `impl--2026-04-15--17-00--project-bootstrap.md`.

---

## Verification Gaps

None. This is a Python module — all verification was done via static analysis and Python execution. No STATIC_VS_RUNTIME_GAP category applies (there are no layout-computed values). The one unverifiable path (actual axe run against a live URL) is expected and noted above.

---

## Actionable Errors

### Error 1: page.evaluate() called with unsupported timeout kwarg — axe never runs
- **Category**: `SPEC_DRIFT`
- **File(s)**: `/mnt/c/Users/Epkone/UXIQ-spec-03/ui-analyzer/ui_analyzer/axe_runner.py` line 124–134; `/mnt/c/Users/Epkone/UXIQ/specs/applied/spec--2026-04-15--18-30--axe-core-runner.md` lines 151–158
- **What broke**: `page.evaluate()` in Playwright Python does not accept a `timeout` keyword argument. Every `run_axe()` call that reaches the evaluation step raises `TypeError`, which is silently caught and returned as `AxeFailure(reason="axe-core timed out")`. axe-core is never executed.
- **Evidence**: `inspect.signature(Page.evaluate)` → `(self, expression: str, arg: Optional[Any] = None)`. No `timeout` parameter exists. Confirmed on Playwright 1.58.0 (the installed version).
- **Suggested fix**: Remove `timeout=AXE_TIMEOUT_MS` from the `page.evaluate()` call. To enforce the 10-second axe timeout, wrap the JavaScript expression in a `Promise.race` with a `setTimeout` rejection, e.g.:
  ```javascript
  async () => {
      const timeout = new Promise((_, reject) =>
          setTimeout(() => reject(new Error('axe timeout')), 10000)
      );
      return await Promise.race([
          axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } }),
          timeout
      ]);
  }
  ```
  Alternatively, call `page.set_default_timeout(AXE_TIMEOUT_MS)` before the evaluate call (but note this affects all page operations in scope). The JS Promise.race approach is preferred as it is scoped to this call only.

### Error 2: Spec itself contains the page.evaluate timeout defect
- **Category**: `SPEC_DRIFT`
- **File(s)**: `/mnt/c/Users/Epkone/UXIQ/specs/applied/spec--2026-04-15--18-30--axe-core-runner.md` lines 151–158
- **What broke**: The spec's Execution Sequence code example shows `page.evaluate(..., timeout=AXE_TIMEOUT_MS)`, which is not valid Playwright Python API. Any future implementer following this spec will reproduce the same defect.
- **Evidence**: Playwright Python `Page.evaluate` signature has no `timeout` parameter.
- **Suggested fix**: Update the spec's Execution Sequence code block to use the JavaScript `Promise.race` timeout pattern (as described in Error 1) and add a note: "Note: Playwright Python's `page.evaluate()` does not accept a `timeout` kwarg. Enforce the 10s timeout inside the JavaScript expression using `Promise.race`."

**Not actionable (requires human judgment or play-mode verification):**
- Whether CDN injection succeeds for a live URL (requires network access and a real browser launch)
- Whether the `networkidle` wait strategy is appropriate for all target pages (spec decision, not an implementation defect)
- Missing impl plan (`impl--2026-04-15--22-30--axe-core-runner.md`) — cannot be reconstructed automatically; requires human to determine if it was created and misplaced or never created

## Rule Violations

None. The module does not import `UIAnalyzerError`, does not raise it, does not import `image_source`, and does not use `print()`. All CLAUDE.md invariants checked against this module are satisfied.

## Task Completeness

- **Unchecked items**: None — all checklist items are marked checked in the working log.
- **Note**: The checklist item "`axe.run()` timeout/exception returns `AxeFailure(reason="axe-core timed out")`" is checked as passing, which is technically correct — a timeout/exception does return that reason. However, the checklist did not verify that `page.evaluate()` accepts the `timeout` kwarg in the first place. The defect is in the code reaching that path via a code error (TypeError) rather than a real timeout.

---

## Proposed Skill Changes

### impl.md — Verify Playwright API signatures before reproducing spec code examples

**Insert after**: the "Read before writing" or API validation section (or add as a new "External API Verification" rule)

```diff
+ #### Playwright Python API Verification
+ Before reproducing any Playwright API call from a spec's code example:
+ 1. Confirm the method signature via `inspect.signature()` or the official Python docs.
+ 2. The Playwright JavaScript and Python APIs differ for many methods — do not assume kwargs
+    available in JS are available in Python (e.g., `page.evaluate()` has no `timeout` kwarg in Python).
+ 3. For any method that enforces a timeout in JS via an options object, check whether the Python
+    API exposes that option, and if not, implement the timeout inside the JavaScript expression
+    using `Promise.race` with `setTimeout`.
```

**Why**: Prevents the evaluator reproducing a JS-API-shaped call in a Python context, which causes silent TypeError at runtime.

[ ] Apply?

### learnings.md — Add Playwright JS vs Python API divergence pattern

**Insert at bottom**:

```diff
+ ## Playwright Python API differs from JavaScript API — verify signatures
+ **Phase affected**: impl, spec
+ **What happened**: The spec showed `page.evaluate(..., timeout=AXE_TIMEOUT_MS)` based on the
+   Playwright JS API. Python's `Page.evaluate()` does not accept a `timeout` kwarg. The implementation
+   reproduced this verbatim; every `run_axe()` call silently returned `AxeFailure` due to `TypeError`
+   being caught by the outer exception handler.
+ **Suggestion**: Add a rule to impl.md: before reproducing any Playwright API call from a spec code
+   example, verify the Python signature. JS and Python APIs diverge on options objects — timeouts
+   that are kwargs in JS must be implemented inside the JavaScript expression via `Promise.race` in Python.
```

[ ] Apply?

---

## Proposed learnings.md Additions

Copy-paste these into `learnings.md` under a new or existing "Playwright" section:

```
- 2026-04-15 axe-core-runner: Playwright Python's page.evaluate() has no `timeout` kwarg (unlike the JS API). A spec code example with `page.evaluate(..., timeout=X)` will raise TypeError at runtime, silently caught and returned as AxeFailure. Enforce timeout inside JS via Promise.race. → update impl.md to add Playwright API signature verification rule.
```

---

## Re-Audit (after fix loop 1)
**Date**: 2026-04-15

> Re-audit — scoped to fixer's stated changes

### What the Fixer Did

No fixer log was found at `Working Logs/fixer-log--2026-04-15--22-30--axe-core-runner.md` — only the bootstrap fixer log exists (`fixer-log--2026-04-15--17-00--project-bootstrap.md`). The fix was verified by direct inspection of the implementation file.

The blocker from the original audit (Error 1) was resolved directly in `ui-analyzer/ui_analyzer/axe_runner.py`:

1. **Removed `timeout=AXE_TIMEOUT_MS` kwarg from `page.evaluate()`** — the Python `Page.evaluate(self, expression, arg=None)` API does not accept a `timeout` parameter; passing it raised `TypeError` at runtime, preventing axe-core from ever executing.
2. **Moved timeout enforcement into the JavaScript expression** — the JS `Promise.race` with `setTimeout(() => reject(...), 10000)` pattern was already present in the JS string but was previously accompanied by the invalid kwarg. The kwarg was removed; the JS-side timeout now correctly enforces the 10-second limit within the expression.
3. **Added `browser.close()` before each early-return path** — the original implementation only called `browser.close()` on the happy path. The fix adds explicit `browser.close()` calls before returning `AxeFailure` in the page-load-timeout path (line 111) and the script-injection-failure path (line 119). The evaluation-timeout path and the normal success path both already called `browser.close()` (lines 144 and 147). Total `browser.close()` calls: 4.

### Updated Goals Table (changed rows only)

| Goal | Previous Status | New Status | Evidence |
|---|---|---|---|
| `axe.run()` timeout enforcement | APPEARS UNMET — BLOCKER | APPEARS MET | `page.evaluate()` call at lines 124–139 contains no `timeout=` kwarg; JS `Promise.race` with `setTimeout(10000)` enforces the limit inside the expression. `inspect.signature(Page.evaluate)` confirms `(self, expression, arg=None)` — no TypeError raised. |

All other goals remain APPEARS MET as confirmed in the original audit.

### Test Suite Result

`python3 -m pytest` (run from `ui-analyzer/`) collected 0 items — no test files exist yet (per spec, tests are covered by Spec 09, which has not been implemented). No regressions detectable via automated tests at this time.

Manual verification performed:
- Module imports cleanly: `python3 -c "from ui_analyzer.axe_runner import run_axe, AxeCoreResult, AxeFailure, AxeViolation, AxeCriterionResult; print('OK')"` → `OK`
- `_parse_axe_result` logic verified against empty output, violation input, and passes-only input — all correct
- `AXE_TIMEOUT_MS == 10_000`, `AXE_CDN_URL` pinned to `4.9.1`, `AxeCoreResult().source` exact string — all confirmed
- No `import UIAnalyzerError` or `raise UIAnalyzerError` anywhere in source
- No `print()` statements
- `logger = logging.getLogger(__name__)` present

### Remaining Actionable Errors

**Error 2 from original audit is still open:**

### Error 2: Spec itself contains the page.evaluate timeout defect
- **Category**: `SPEC_DRIFT`
- **File(s)**: `/mnt/c/Users/Epkone/UXIQ/specs/applied/spec--2026-04-15--18-30--axe-core-runner.md` lines 151–158
- **What broke**: The spec's Execution Sequence code block shows `page.evaluate(..., timeout=AXE_TIMEOUT_MS)`, which is invalid Playwright Python API. Any future implementer who follows this spec verbatim will reproduce the same TypeError defect.
- **Evidence**: Playwright Python `Page.evaluate` signature: `(self, expression: str, arg: Optional[Any] = None)` — no `timeout` parameter exists.
- **Suggested fix**: Update the spec's Execution Sequence code block to remove `timeout=AXE_TIMEOUT_MS` from the `page.evaluate()` call, and add a note: "Note: Playwright Python's `page.evaluate()` does not accept a `timeout` kwarg. The 10-second axe timeout is enforced inside the JavaScript expression using `Promise.race` with `setTimeout`."

**Not actionable (carried forward from original audit):**
- Whether CDN injection succeeds for a live URL (requires network access and a real browser launch)
- Whether the `networkidle` wait strategy is appropriate for all target pages (spec decision, not a defect)
- Missing impl plan (`impl--2026-04-15--22-30--axe-core-runner.md`) — cannot be reconstructed automatically
