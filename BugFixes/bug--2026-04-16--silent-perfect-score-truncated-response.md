# Bug: Silent Perfect Score on Truncated Claude Response

**Date**: 2026-04-16
**Status**: Fixed

---

## Symptom

App returns ★★★★★ (5.0/5) on all tiers with the warning:
> ⚠️ Claude returned a malformed response — some tiers may be missing.

## Root Cause

`max_tokens=4096` in `handler.py` is too low for a full audit response. Claude gets cut off
mid-sentence before writing `</audit_report>`. The parser's `str.find("</audit_report>")`
returns `-1`, triggers the early-exit path, and returns an empty `AuditReport`.
Empty report → no findings → scorer gives 5/5 on every tier.

## Evidence

Raw response was 13,621 chars and ended mid-sentence with no closing tag:
```
...makes it unclear whether the cancelled row is a different content type or simply
missing a container.</issue><recommendation>Apply a consistent card container to all
event rows, or use
```

## Fix

`ui-analyzer/ui_analyzer/handler.py` — increased `max_tokens` from `4096` to `8192`.
