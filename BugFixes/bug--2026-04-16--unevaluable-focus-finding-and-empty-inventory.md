# Bug: Focus Indicator Finding Is Unevaluable + Empty Inventory Not Enforced

**Date**: 2026-04-16
**Status**: Open
**Severity**: LOW

---

## Bug A — WCAG 2.4.7 always produces a noise finding that can never be verified

### Symptom

Every audit report includes a `WCAG 2.4.7 — Focus indicators` finding marked `ESTIMATED — verify manually`. The finding body explicitly states "No focused element is visible in the static screenshot; cannot evaluate." This is not a finding — it is a placeholder acknowledging that evaluation is impossible.

### Root Cause

The rubric definition in `tier1.py` includes 2.4.7 as a standard check:

```python
{
    "id": "wcag_2_4_7",
    "criterion": "2.4.7",
    "description": "Focus indicators",
    "threshold": "flag only if focus state is visible in screenshot",
}
```

The threshold condition says "flag only if focus state is visible in screenshot," but because Claude is instructed to produce a finding for every check in the rubric, it generates an ESTIMATED PASS finding with a disclaimer instead of omitting the check entirely. The result is a low-value entry that adds noise and erodes trust in the ESTIMATED label (since "ESTIMATED" on a real contrast check means something different from "ESTIMATED — I can't see a focused element").

### Expected Behaviour

If no focused element is visible in the screenshot, 2.4.7 should produce no finding at all (not a placeholder PASS). The check should only appear in the report when a focus ring is visually present and can be assessed.

### Recommended Fix

Either:
- Remove `wcag_2_4_7` from the `tier1.py` rubric entirely and add a note in the system prompt that focus indicators are outside scope for static screenshots, **or**
- Add an explicit rubric instruction: `"omit_if": "no focused element visible in screenshot"` and handle it in `report_renderer.py` to suppress empty/inapplicable findings.

### Affected Files

- `ui-analyzer/ui_analyzer/rubric/tier1.py` — `wcag_2_4_7` entry

---

## Bug B — Empty inventory is not validated; downstream analysis is weakened silently

### Symptom

The run file shows `"Claude produced no inventory."` The inventory step is supposed to enumerate all visible interactive elements (buttons, links, form fields) before Tier 2/3 scoring begins. When it is empty, Claude's structural analysis proceeds without an explicit element list, increasing the chance of missed findings or hallucinated elements.

### Root Cause

The system prompt (`prompts.py:9`) instructs Claude to perform `inventory → structure → rubric` in order, but there is no validation that the parsed `<audit_report>` contains a non-empty inventory. `xml_parser.py` deserializes whatever Claude returns — an empty or missing inventory is accepted silently. Neither the verifier prompt nor the renderer flags this condition.

The verifier prompt (`prompts.py:21`) does include step 1 — "Re-examine your inventory and structure_observation" — but does not explicitly require that the inventory be non-empty or that missing elements be added.

### Expected Behaviour

If `audit_report.inventory` is empty or None after parsing, the system should either:
1. Log a warning (so operators can monitor inventory quality), or
2. Instruct the verifier to explicitly populate the inventory before proceeding with tier amendments.

### Recommended Fix

In `handler.py`, after parsing (step 9) and before verification (step 9.5), check inventory completeness and pass a flag to the verifier:

```python
inventory_empty = not audit_report.inventory or len(audit_report.inventory) == 0
if inventory_empty:
    logger.warning("Primary audit produced no inventory — verifier will be instructed to populate it.")
```

Then strengthen the verifier prompt to make inventory population a blocking requirement when empty, rather than a soft re-examination.

Alternatively, add an `inventory` check to the verifier rubric in `prompts.py:VERIFIER_PROMPT` step 1:
> "If the inventory is empty, populate it now from the screenshot before reviewing any tier findings."

### Affected Files

- `ui-analyzer/ui_analyzer/handler.py` — after step 9 (parse), before step 9.5 (verify)
- `ui-analyzer/ui_analyzer/prompts.py` — `VERIFIER_PROMPT` step 1
