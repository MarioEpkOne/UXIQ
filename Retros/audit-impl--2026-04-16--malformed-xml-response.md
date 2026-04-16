# Implementation Audit: Malformed XML Response → Silent Perfect Score
**Date**: 2026-04-16
**Status**: COMPLETE
**Working log**: N/A — live test run, not a past implementation
**Impl plan**: N/A
**Spec**: N/A

---

## Independent Evaluator Verdict

Skipped — no spec document. Diagnosis performed by direct code trace.

---

## Failures & Root Causes

### XML parse error silently produces perfect 5/5 scores

**Category**: `SPEC_DRIFT`

**What happened**: Claude returned an `<audit_report>` block containing unescaped `&`
characters in finding text (e.g. `"ratio 3:1 & 4.5:1 required"`). `ET.fromstring` raised
`ET.ParseError`. The parser caught it, returned a fully-empty `AuditReport` with one
warning in `parse_warnings`. The scorer computed 5/5 on all tiers (no findings = perfect).
The renderer showed the warning but the scores looked real.

**Why**: `xml_parser.py` has no XML sanitization step before calling `ET.fromstring`.
Claude does not reliably escape `&` to `&amp;` in free-text content.

**Evidence**: Live test output showed `⚠️ Claude returned a malformed response — some tiers
may be missing.` alongside `★★★★★ (5.0 / 5)` on every tier. A genuinely perfect UI score
from a real screenshot is implausible.

---

## Actionable Errors

### Error 1: Unescaped `&` in Claude XML causes silent empty report
- **Category**: `SPEC_DRIFT`
- **File(s)**: `ui-analyzer/ui_analyzer/xml_parser.py`
- **What broke**: Claude emits bare `&` in finding text; `ET.fromstring` throws `ET.ParseError`;
  parser returns empty `AuditReport`; scorer gives 5/5 everywhere; user sees fake perfect scores.
- **Evidence**: Warning `⚠️ Claude returned a malformed response` with all-5/5 scores on a real screenshot.
- **Suggested fix**: Pre-process `xml_slice` with a regex to replace bare `&` (not part of a
  named entity) with `&amp;` before calling `ET.fromstring`.

**Not actionable (requires human judgment):**
- None.

---

## Applied Fix

`xml_parser.py` — added sanitization step between slice extraction and `ET.fromstring`:

```python
import re
xml_slice = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", xml_slice)
```

This handles the common case. Other invalid XML characters (`<`, `>` in text content) are
less likely since Claude avoids angle brackets in prose, but could be addressed similarly
if they appear in future runs.

---

## Proposed learnings.md Additions

```
- 2026-04-16 xml-parse: Claude sometimes emits bare & in XML finding text; pre-sanitize with
  regex before ET.fromstring to prevent silent empty AuditReport and fake 5/5 scores.
```
