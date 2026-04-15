# Implementation Audit: Context Events & Prompt Assembly
**Date**: 2026-04-15
**Status**: INCOMPLETE
**Working log**: Working Logs/wlog--2026-04-15--23-10--context-events-and-prompt-assembly.md
**Impl plan**: Implementation Plans/impl--2026-04-15--22-57--context-events-and-prompt-assembly.md
**Spec**: specs/spec-05-context-events-and-prompt-assembly.md

---

## Independent Evaluator Verdict

Independent evaluation skipped — this is a pure-Python project with no Unity/MCP state. Static code inspection was used in place of MCP verification. All three created files were read and executed against the spec's success criteria directly via Python.

## Goals — Static Verification

| Goal | Status | Evidence |
|---|---|---|
| `context_events.py`: ContextEvent dataclass, event_to_xml(), thread_to_prompt() | APPEARS MET | File matches spec exactly; all assertions pass |
| `prompts.py`: SYSTEM_PROMPT constant with phase markers and no-scoring instruction | APPEARS MET | File matches spec verbatim; assertions pass |
| `prompt_builder.py`: build_thread() with correct canonical ordering | APPEARS PARTIALLY MET | Ordering correct for AxeCoreResult and AxeFailure branches; FAILS for axe_result=None, source_type="url" branch |
| event_to_xml() with dict data → YAML body in XML tags | APPEARS MET | Verified via direct execution |
| event_to_xml() with str data → verbatim injection | APPEARS MET | Verified via direct execution |
| thread_to_prompt() ends with "What is the complete audit report?" | APPEARS MET | Verified via direct execution |
| build_thread() with AxeCoreResult → events[1].type == "axe_core_result" | APPEARS MET | Verified via direct execution |
| build_thread() with axe_result=None, source_type="url" → events[1].type == "axe_unavailable" | APPEARS UNMET | events[1].type == "rubric_tier1" — axe block omitted entirely |
| build_thread() with axe_result=None, source_type="file" → events[1].type == "rubric_tier1" | APPEARS MET | Verified via direct execution |
| analysis_request block contains viewport_width and viewport_height | APPEARS MET | Verified via direct execution |
| SYSTEM_PROMPT contains no rubric content | APPEARS MET | No TIER or WCAG criterion IDs found |

## Properties Not Verifiable Without Play Mode

None — this is a pure-Python project. All properties are statically verifiable.

---

## Failures & Root Causes

### Spec Success Criterion: axe_result=None, source_type="url" → axe_unavailable

**Category**: `SPEC_DRIFT`

**What happened**: The spec's Success Criteria section (line 257) states: `build_thread() with axe_result=None, source_type="url" → events[1].type == "axe_unavailable"`. The implementation and impl plan treat `axe_result=None` as always meaning file mode (omit axe block entirely), regardless of `source_type`. When called with `axe_result=None, source_type="url"`, the implementation produces `events[1].type == "rubric_tier1"`.

**Why**: The impl plan's Step 4 verification scripts only test three branches: `AxeCoreResult`, `AxeFailure(reason=...)`, and `axe_result=None` (called "file mode"). The plan did not implement or test the fourth combination: `axe_result=None, source_type="url"`. The implementing agent followed the plan faithfully, but the plan itself missed this spec requirement. The spec's "axe block logic" section describes `None` as file mode unconditionally, while the Success Criteria section adds a fourth branch (`None + url`) that the logic section never handles — a spec internal inconsistency that the impl plan propagated instead of flagging.

**Evidence**:
- Spec line 257: `build_thread() with axe_result=None, source_type="url" → events[1].type == "axe_unavailable"`
- Spec "axe block logic" section (lines 194–207): treats `None` as unconditional file mode omission
- Direct execution result: `build_thread('web_dashboard', 'url', 'https://example.com', 1280, 800, None)` → `['analysis_request', 'rubric_tier1', 'rubric_tier2', 'rubric_tier3', 'rubric_tier4', 'output_schema']`
- `events[1].type == 'rubric_tier1'` (not `'axe_unavailable'`)

---

## Verification Gaps

None. The working log states 19/19 checklist items verified. Those 19 items do not cover the `axe_result=None, source_type="url"` case because the impl plan's checklist did not include it. This gap is in the plan's checklist design, not in the agent's verification execution.

---

## Actionable Errors

Structured list of errors that a fixer agent can act on.

### Error 1: build_thread() mishandles axe_result=None with source_type="url"
- **Category**: `SPEC_DRIFT`
- **File(s)**: `ui-analyzer/ui_analyzer/prompt_builder.py`
- **What broke**: The spec requires that when `axe_result=None` AND `source_type="url"`, the function injects an `axe_unavailable` event (because axe was attempted but produced no result). The current implementation always omits the axe block when `axe_result is None`, regardless of `source_type`. This means a URL-mode analysis where axe returned None silently skips telling Claude it is in estimated mode.
- **Evidence**: Direct execution: `build_thread('web_dashboard', 'url', 'https://example.com', 1280, 800, None)` → `events[1].type == 'rubric_tier1'`. Spec line 257 requires `events[1].type == 'axe_unavailable'`.
- **Suggested fix**: In `prompt_builder.py`, change the axe block conditional to also handle `axe_result=None, source_type="url"`. The corrected logic should be:
  ```python
  if isinstance(axe_result, AxeCoreResult):
      events.append(ContextEvent(type="axe_core_result", data=axe_result))
  elif isinstance(axe_result, AxeFailure):
      events.append(ContextEvent(type="axe_unavailable", data={
          "reason": axe_result.reason,
          "tier1_mode": "estimated",
          "instruction": (
              "You do not have authoritative WCAG data. Base all Tier 1 findings on "
              "visual estimation only. Mark every Tier 1 finding as ESTIMATED and "
              "recommend manual verification."
          ),
      }))
  elif axe_result is None and source_type == "url":
      events.append(ContextEvent(type="axe_unavailable", data={
          "reason": "axe-core returned no result",
          "tier1_mode": "estimated",
          "instruction": (
              "You do not have authoritative WCAG data. Base all Tier 1 findings on "
              "visual estimation only. Mark every Tier 1 finding as ESTIMATED and "
              "recommend manual verification."
          ),
      }))
  # If axe_result is None and source_type == "file": omit axe block entirely
  ```

**Not actionable (requires human judgment or play-mode verification):**
- The spec has an internal inconsistency between the "axe block logic" section (which describes `None` as unconditional file-mode omission) and the Success Criteria section (which adds a `None + url` branch). The fix above resolves this by making the Success Criteria authoritative. If the spec author intended `None` to only ever come from file mode, the Success Criteria line (spec line 257) should be deleted instead. A human must decide which interpretation is correct before the fixer applies the change.

## Rule Violations

None. The implementing agent followed all CLAUDE.md rules. No files outside the scope list were touched. The working log's deviation claim ("None") is accurate.

## Task Completeness

- **Unchecked items**: None — the working log reports 19/19 checklist items verified [x]. However, the impl plan's checklist did not include the `axe_result=None, source_type="url"` branch, so this item was not in scope for the checklist. The checklist itself was incomplete relative to the spec.

---

## Proposed Skill Changes

### impl-plan.md — Require plan to audit spec success criteria against spec logic sections

**Insert after**: the "Steps" section description / verification step guidance in impl-plan.md

```diff
+ **Before finalizing verification steps**: cross-check the spec's "Success Criteria" section
+ against the spec's "logic" or "behavior" sections. If a Success Criteria bullet describes a
+ branch or combination not covered by the logic section, flag it as a spec inconsistency and
+ add it explicitly to the Post-Implementation Checklist. Do not silently skip success criteria
+ that appear only in the Success Criteria section and not in the logic section.
```
**Why**: Prevents `SPEC_DRIFT` caused by impl plans that follow the logic section but miss success criteria bullets that describe additional branches not covered by the logic.

[ ] Apply?

---

## Proposed learnings.md Additions

Copy-paste these into learnings.md under the relevant section:

```
- 2026-04-15 context-events-and-prompt-assembly: Spec's "Success Criteria" section described a branch (axe_result=None, source_type="url") not covered by the spec's "axe block logic" section. The impl plan followed the logic section only and missed the criterion. Plans must cross-check Success Criteria against logic sections and add any unrepresented branches to the checklist. → impl-plan.md
```

---

## Re-Audit (after fix loop 1)
**Date**: 2026-04-15

> Re-audit — scoped to fixer's stated changes.

### What the Fixer Did

The fixer applied one change to `ui-analyzer/ui_analyzer/prompt_builder.py`:

- Added an `elif axe_result is None and source_type == "url"` branch that injects an `axe_unavailable` event with `reason="axe-core returned no result"`, `tier1_mode="estimated"`, and the standard visual-estimation instruction string.
- Updated the function docstring to explicitly enumerate all four `axe_result` cases.

No other files were touched. The fixer noted the spec internal inconsistency (logic section vs. Success Criteria section) and treated the Success Criteria as authoritative, which is consistent with the audit's recommendation.

### Updated Goals Table

| Goal | Previous Status | New Status | Evidence |
|---|---|---|---|
| `build_thread()` with `axe_result=None`, `source_type="url"` → `events[1].type == "axe_unavailable"` | APPEARS UNMET | APPEARS MET | Direct execution: `events[1].type == 'axe_unavailable'`, `data['reason'] == 'axe-core returned no result'`, `data['tier1_mode'] == 'estimated'` |

All other goals remain APPEARS MET — no regressions detected.

### Test Suite Result

**35 passed, 1 failed** — identical to the pre-fix baseline.

The single failure is `test_image_source_url_integration` (Playwright Chromium not installed in WSL environment — pre-existing, unrelated to this fix). No new failures introduced.

### Remaining Actionable Errors

None. Error 1 (the only actionable error from the original audit) is resolved.
