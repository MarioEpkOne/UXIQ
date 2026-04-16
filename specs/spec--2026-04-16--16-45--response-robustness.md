# Spec: Response Robustness — Truncation Detection & XML Sanitization

**Date**: 2026-04-16  
**Status**: Ready for implementation

---

## Goal

Prevent the silent-perfect-score failure mode where `analyze_ui_screenshot()` returns ★★★★★ (5.0 / 5) on all tiers with a malformed-response warning, caused by either:

1. Claude's response being cut off by the `max_tokens` ceiling (no `</audit_report>` closing tag), or
2. Claude emitting bare `&` characters in XML text content, causing `ET.ParseError`.

Both have the same observable symptom — an empty `AuditReport` → scorer gives 5/5 — but different causes and different fixes. This spec covers both.

---

## Current State

### handler.py
- `max_tokens=8192` (raised from 4096 in a prior hotfix, not yet committed).
- No `stop_reason` check after the API call. If Claude is cut off mid-XML, the raw text is passed directly to `xml_parser.parse()`, which silently returns an empty `AuditReport`.

### xml_parser.py
- `parse()` extracts the `<audit_report>…</audit_report>` slice and calls `ET.fromstring()` directly.
- No sanitization step. Claude occasionally emits bare `&` in free-text content (e.g. `"ratio 3:1 & 4.5:1 required"`), which causes `ET.ParseError`. The parser catches it, returns a fully-empty `AuditReport`, and the scorer gives 5/5 on every tier.

---

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| max_tokens ceiling | 16,384 | 2× the current value; covers all realistic audit responses; well within Sonnet's 64K output limit |
| On stop_reason == "max_tokens" | Raise `UIAnalyzerError` | Truncation is a hard failure — no meaningful partial result can be returned safely |
| On bare `&` in XML | Sanitize before `ET.fromstring` | Soft-escape only unrecognized entities; preserve valid XML entities; avoids double-escaping |
| Other XML special chars (`<`, `>` in text) | Out of scope | Claude reliably avoids bare angle brackets in prose; address only if a future run surfaces it |

---

## Technical Design

### File 1: `ui-analyzer/ui_analyzer/handler.py`

**Change 1 — raise the token ceiling.**

Replace the inline `max_tokens=8192` with a module-level constant and set it to 16,384:

```python
MAX_TOKENS = 16_384
```

Use it in the API call:

```python
response = client.messages.create(
    model=MODEL,
    max_tokens=MAX_TOKENS,
    ...
)
```

**Change 2 — detect truncation immediately after the API call.**

Add a `stop_reason` check between the API call (step 7) and the preamble extraction (step 8):

```python
# 7b. Detect truncation
if response.stop_reason == "max_tokens":
    raise UIAnalyzerError(
        f"Claude's response was cut off — the audit exceeded the {MAX_TOKENS}-token "
        "output ceiling. Try a simpler screenshot or contact support."
    )
```

This must run **before** `response.content[0].text` is passed to `_extract_preamble` or `parse()`, so that a truncated response never silently becomes a 5/5 report.

---

### File 2: `ui-analyzer/ui_analyzer/xml_parser.py`

**Change — sanitize bare `&` before parsing.**

Add `import re` at the top of the file (alongside the existing imports).

In `parse()`, between the `xml_slice` extraction and the `ET.fromstring()` call, insert one sanitization step:

```python
# Sanitize bare & that Claude may emit in free-text content.
# Replaces & not already part of a named/numeric XML entity with &amp;.
xml_slice = re.sub(
    r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)",
    "&amp;",
    xml_slice,
)
```

The regex uses a negative lookahead to skip entities that are already valid (`&amp;`, `&lt;`, `&gt;`, `&quot;`, `&apos;`, numeric `&#123;`, hex `&#x1A;`). All other bare `&` are replaced.

---

## Edge Cases & Error Handling

| Scenario | Expected behaviour |
|---|---|
| `stop_reason == "max_tokens"`, no `</audit_report>` | `UIAnalyzerError` raised. No parsing attempted. |
| `stop_reason == "max_tokens"`, `<audit_report>` partially present | `UIAnalyzerError` raised (check fires before parse). |
| `stop_reason == "end_turn"`, but `</audit_report>` absent | Existing soft-failure path: `parse_warnings` contains `"No <audit_report> block found"`, report is empty. Not affected by this spec. |
| Bare `&` in tier finding text | Sanitized to `&amp;` before `ET.fromstring`. Parses successfully. No parse error. |
| `&amp;` or `&lt;` already present | Negative lookahead skips them. Not double-escaped. |
| `&` in an XML attribute value | Same regex covers attribute values since they are part of the same `xml_slice`. |
| API returns no `content` blocks | Pre-existing `response.content[0]` access raises `IndexError`. Out of scope — this would be a new API contract violation. |

---

## Constraints & Invariants

- `parse()` must **never raise** — the sanitization must not change this contract.
- `UIAnalyzerError` is the only exception type raised on hard failure; this spec does not introduce new exception types.
- `MAX_TOKENS` must be used consistently in the API call, the error message, and tests — no magic numbers.
- The `stop_reason` check must occur **before** any attempt to read `response.content[0].text` for parsing purposes.

---

## Testing Strategy

### Unit tests — handler.py

**Test 1: truncation raises UIAnalyzerError**

Mock `client.messages.create` to return a response where `stop_reason == "max_tokens"` and `content[0].text` is a partial XML string (no closing tag). Assert `UIAnalyzerError` is raised. Assert the error message contains "cut off" or "ceiling".

**Test 2: normal completion does not raise**

Mock `client.messages.create` to return `stop_reason == "end_turn"` with valid XML. Assert no `UIAnalyzerError` is raised and a non-empty Markdown string is returned.

### Unit tests — xml_parser.py

**Test 3: bare `&` in finding text parses without error**

Call `parse()` with a minimal well-formed `<audit_report>` containing a tier finding whose `<issue>` text includes `ratio 3:1 & 4.5:1 required`. Assert `parse_warnings` contains no XML-related entries and the finding is present in the returned `AuditReport`.

**Test 4: already-escaped `&amp;` is not double-escaped**

Call `parse()` with XML containing `&amp;` in text content. Assert the finding text in the returned `AuditReport` contains a single `&` (decoded correctly), not `&amp;amp;`.

**Test 5: other valid entities (`&lt;`, `&gt;`) are preserved**

Call `parse()` with XML containing `&lt;` and `&gt;` in text. Assert they decode to `<` and `>` without error.

### Integration test (requires ANTHROPIC_API_KEY)

**Test 6: real screenshot produces non-empty AuditReport**

Call `analyze_ui_screenshot()` with a real screenshot URL. Assert the returned Markdown is non-empty, contains at least one tier heading, and does not contain "Claude returned a malformed response".

---

## Open Questions

None — all decisions were made during the interview.
