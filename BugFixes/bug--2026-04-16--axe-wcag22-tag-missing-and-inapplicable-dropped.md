# Bug: WCAG 2.2 Rules Never Checked + `inapplicable` Results Silently Dropped

**Date**: 2026-04-16
**Status**: Open
**Severity**: MEDIUM

---

## Bug A — WCAG 2.2 tag missing from axe run (`target-size` / 2.5.8)

### Symptom

Touch-target size checks (WCAG 2.5.8) are always `ESTIMATED — verify manually` in the output, even when a full URL scan is performed. axe-core supports this rule natively but the data is never collected.

### Root Cause

`axe_runner.py:127-133` runs axe with a hardcoded tag list:

```python
runOnly: {
    type: 'tag',
    values: ['wcag2a', 'wcag2aa', 'wcag21aa']
}
```

The `target-size` rule was introduced in WCAG 2.2 and is tagged `wcag22aa` in axe-core. Because `wcag22aa` is absent from the list, axe never evaluates it. The rule never appears in `violations` or `passes`, so `_parse_axe_result` produces no finding for 2.5.8, and Claude falls back to visual estimation on every run.

### Expected Behaviour

Touch target size should be evaluated authoritatively by axe-core for URL inputs, the same as color-contrast.

### Recommended Fix

Add `'wcag22aa'` to the `runOnly.values` array in `axe_runner.py:130`:

```python
values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']
```

Also add `'target-size'` to `_RULE_TO_CRITERION` if not already mapped — it is already present at `axe_runner.py:31`.

### Affected Files

- `ui-analyzer/ui_analyzer/axe_runner.py` — line 130 (tag list)

---

## Bug B — `inapplicable` axe results silently dropped, causing unnecessary ESTIMATED findings

### Symptom

Criteria such as `non-text-contrast` (1.4.11) and `color-not-used-as-sole-meaning` (1.4.1) are marked `ESTIMATED — verify manually` even when axe ran successfully, because they appear in axe's `inapplicable` bucket rather than `passes`. Claude then re-estimates them visually, producing lower-confidence findings for checks that axe has definitively determined are not applicable.

### Root Cause

`axe_runner.py:163-167` explicitly ignores `incomplete` and `inapplicable`:

```python
"""
Only 'violations' and 'passes' are used.
'incomplete' and 'inapplicable' are ignored.
"""
```

When axe classifies a rule as `inapplicable` (e.g., `non-text-contrast` on a page with no icon-only interactive elements, or `color-not-used-as-sole-meaning` on a simple page), it means axe actively evaluated the page and found no elements to which the rule applies. This is semantically equivalent to a PASS from the audit's perspective — there are no violations. But because `inapplicable` is dropped, the criterion disappears from `AxeCoreResult.findings`, and the rubric instruction in `tier1.py` tells Claude to estimate anything absent.

### Expected Behaviour

A criterion axe marks `inapplicable` should be recorded as a PASS in `AxeCoreResult.findings` (with a note that no applicable elements were found), not omitted. Claude should not re-estimate it.

### Recommended Fix

In `_parse_axe_result` (`axe_runner.py:160`), read the `inapplicable` array in addition to `passes`:

```python
inapplicable_raw: list[dict] = raw.get("inapplicable", [])

# Extend passing_rules with rules axe found inapplicable
for item in inapplicable_raw:
    passing_rules.add(item["id"])
```

This treats inapplicable rules the same as passing rules — both result in `AxeCriterionResult(result="PASS")` — preventing Claude from estimating them visually.

### Affected Files

- `ui-analyzer/ui_analyzer/axe_runner.py` — `_parse_axe_result` (line 160 onwards)
