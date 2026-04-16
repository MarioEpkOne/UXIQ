# Spec — Handler Preamble Passthrough

**Created:** 2026-04-16 02:31 Prague  
**Status:** Ready for implementation  
**Closes open product gap:** learnings.md → OPEN PRODUCT GAPS → "xml_parser strips preamble — handler must preserve it"

---

## Goal

When Claude prepends prose before the `<audit_report>` XML block (e.g. a disclaimer that the image does not appear to be a UI screenshot), that preamble text must survive into the final Markdown string returned by `analyze_ui_screenshot()`. Today it is silently discarded by `xml_parser.parse()`, which extracts only the XML block and ignores everything before it.

---

## Current State

### Flow (as-is)

```
response.content[0].text  →  parse()  →  AuditReport  →  render()  →  output str
```

`xml_parser.parse()` (line 260–267) slices the raw response from `<audit_report>` onward:

```python
start = response_text.find("<audit_report>")
end   = response_text.find("</audit_report>")
xml_slice = response_text[start : end + len("</audit_report>")]
```

Any text before `start` is computed but never used. It is thrown away.

`handler.py` (line 140) passes the raw text directly to `parse()` and feeds the result straight to `render()`:

```python
audit_report = parse(response.content[0].text)  # preamble lost here
...
return render(report=audit_report, ...)
```

### Existing test (weakened)

`tests/test_handler.py` — `test_handler_non_ui_preamble_passes_through` (line 285–306) was downgraded during a fix pass. It no longer asserts the preamble text appears in the output — only that a string is returned and contains `"## Tier 1"`.

---

## Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Extraction logic lives in `handler.py` only | `xml_parser.parse()` is a pure XML parser; it should not own prose-detection concerns. `handler.py` already owns the raw response string. No change to `AuditReport` dataclass or `xml_parser`. |
| 2 | Preamble placed at very top of output, before `# UI Analysis Report` | This matches natural reading order: Claude's caveat should be the first thing seen. |
| 3 | Preamble rendered verbatim (no Markdown wrapping) | What Claude writes is already plain text or contains its own emoji/formatting. Adding blockquotes or bold risks double-formatting. |
| 4 | Preamble stripped of leading/trailing whitespace | Prevents accidental extra blank lines at the top of the document caused by Claude's own newlines around the XML block. |
| 5 | Preamble is shown even when no `<audit_report>` is found | The entire raw response is treated as preamble when `start == -1`. The user sees what Claude actually said, alongside the normal malformed-response warning from `render()`. |
| 6 | Test restored to full spec-09 assertion | The only way to prevent regression is to assert the preamble text is present in the output. The weakened assertion is replaced. |

---

## Technical Design

### Files changed

| File | Change |
|------|--------|
| `ui-analyzer/ui_analyzer/handler.py` | Add `_extract_preamble()` helper; call it in `analyze_ui_screenshot()`; prepend to render output |
| `ui-analyzer/tests/test_handler.py` | Restore preamble assertion in `test_handler_non_ui_preamble_passes_through` |

`xml_parser.py`, `AuditReport`, and `report_renderer.py` are **not touched**.

---

### `_extract_preamble(raw: str) -> str`

Private helper added to `handler.py`:

```python
def _extract_preamble(raw: str) -> str:
    """Return any text Claude wrote before <audit_report>, stripped.

    Returns '' if there is no such text or if the string is empty.
    """
    start = raw.find("<audit_report>")
    if start == -1:
        # No XML block at all — treat entire response as preamble.
        return raw.strip()
    return raw[:start].strip()
```

### Updated call site in `analyze_ui_screenshot()`

Replace the current step 8 (lines 139–155 of `handler.py`) with:

```python
# 8. Extract preamble (text before <audit_report>) from raw response
raw_text = response.content[0].text
preamble = _extract_preamble(raw_text)

# 9. Parse Claude's XML response
audit_report = parse(raw_text)

# 10. Compute scores
scores = compute(audit_report)

# 11. Determine axe_succeeded flag
axe_succeeded = isinstance(axe_result, AxeCoreResult)

# 12. Render Markdown report
output = render(
    report=audit_report,
    scores=scores,
    app_type=req.app_type,
    image_source=req.image_source,
    axe_succeeded=axe_succeeded,
    model=MODEL,
)

# 13. Prepend preamble if present
if preamble:
    output = preamble + "\n\n" + output

return output
```

The step numbering in the docstring comment block shifts by 1 after the insertion of step 8.

---

### Updated test

In `tests/test_handler.py`, replace the body of `test_handler_non_ui_preamble_passes_through` assertions with:

```python
assert isinstance(result, str)
assert "⚠️ The provided image does not appear to be a web UI" in result
assert "## Tier 1" in result
```

The preamble assertion is restored (spec-09 original intent). The `"## Tier 1"` assertion is kept as a belt-and-suspenders check that the report body is also present.

---

## Edge Cases & Error Handling

This table is authoritative. Contradictions with code sketches above must be resolved in favor of this table.

| Scenario | Input (`raw_text`) | Expected output |
|----------|-------------------|-----------------|
| **Happy path — no preamble** | Starts with `<audit_report>` | `_extract_preamble()` returns `""`. Output is unchanged — render output only. |
| **Preamble before XML** | `"⚠️ Disclaimer.\n\n<audit_report>..."` | `_extract_preamble()` returns `"⚠️ Disclaimer."`. Output is `"⚠️ Disclaimer.\n\n# UI Analysis Report\n..."`. |
| **Preamble with leading/trailing newlines** | `"\n\n⚠️ Disclaimer.\n\n<audit_report>..."` | `.strip()` removes surrounding whitespace. Output starts with `"⚠️ Disclaimer."` — no leading blank lines. |
| **Multi-line preamble** | `"Line 1.\nLine 2.\n<audit_report>..."` | Entire `"Line 1.\nLine 2."` is preserved verbatim after stripping. |
| **No `<audit_report>` at all** | `"I cannot analyze this image."` | `_extract_preamble()` returns `"I cannot analyze this image."`. Output is `"I cannot analyze this image.\n\n# UI Analysis Report\n...\n⚠️ Claude returned a malformed response..."`. |
| **Empty response** | `""` | `_extract_preamble()` returns `""`. No prepending. Output is normal malformed-warning report. |
| **Whitespace-only response** | `"   \n\n   "` | `.strip()` returns `""`. No prepending. |
| **Preamble is only whitespace** | `"   \n<audit_report>..."` | `.strip()` returns `""`. No prepending — whitespace-only preamble is treated as absent. |

---

## Constraints & Invariants

- `xml_parser.parse()` must not be modified. Its contract (never raises, always returns `AuditReport`) is unchanged.
- `AuditReport` dataclass must not be modified.
- `report_renderer.render()` must not be modified.
- `_extract_preamble()` must never raise on any string input.
- The `analyze_ui_screenshot()` return type remains `str`. Prepending does not change that.
- The preamble separator is always exactly `"\n\n"` (one blank line) — not a horizontal rule or any other Markdown element.
- Unit tests must not require an API key or browser (already the case; no change here).

---

## Testing Strategy

### Unit test to update

**File:** `ui-analyzer/tests/test_handler.py`  
**Function:** `test_handler_non_ui_preamble_passes_through`

Restore the assertion:
```python
assert "⚠️ The provided image does not appear to be a web UI" in result
```

### New unit tests to add

Add these to `test_handler.py` (unit, no API key needed):

```python
# test_handler_no_preamble_output_unchanged
# Mock: messages.create() → response starting directly with <audit_report>
# Result must NOT start with a blank line — no extra whitespace prepended.
# "# UI Analysis Report" appears at position 0 of the output.

# test_handler_whitespace_only_preamble_not_prepended
# Mock: messages.create() → response = "   \n\n<audit_report>..."
# Result starts with "# UI Analysis Report" — whitespace-only preamble is suppressed.

# test_handler_no_xml_preamble_shown
# Mock: messages.create() → response = "I cannot analyze this image."
# Result starts with "I cannot analyze this image."
# Result also contains "⚠️ Claude returned a malformed response"
```

### Regression guard

The existing tests `test_valid_file_path_returns_markdown_with_all_tiers` and `test_axe_failure_returns_string_not_exception` both mock a response that starts directly with `<audit_report>` — they must continue to pass unchanged, confirming the no-preamble path is unaffected.

### Success criteria

- [ ] `pytest tests/ -m "not integration"` exits 0
- [ ] `test_handler_non_ui_preamble_passes_through` passes with the full preamble assertion restored
- [ ] The three new unit tests listed above pass
- [ ] All existing handler tests continue to pass
- [ ] No changes to `xml_parser.py`, `AuditReport`, or `report_renderer.py`

---

## Open Questions

None. All decisions resolved during interview.
