# Implementation Plan: Handler Preamble Passthrough

## Header
- **Spec**: specs/applied/spec--2026-04-16--02-31--handler-preamble-passthrough.md
- **Worktree**: .claude/worktrees/handler-preamble-passthrough/
- **Scope — files in play** (agent must not touch files not listed here):
  - `ui-analyzer/ui_analyzer/handler.py`
  - `ui-analyzer/tests/test_handler.py`
- **Reading list** (read these in order before starting, nothing else):
  1. `ui-analyzer/ui_analyzer/handler.py`
  2. `ui-analyzer/tests/test_handler.py`

## Environment assumptions verified
- `pytest`, `pytest-mock`, and `pytest-asyncio` are all listed in `[project.optional-dependencies].dev` in `ui-analyzer/pyproject.toml`.
- Test command: `cd ui-analyzer && pytest tests/ -m "not integration"` — no API key required.

---

## Steps

### Step 1: Add `_extract_preamble()` helper to `handler.py`

**File**: `ui-analyzer/ui_analyzer/handler.py`  
**Location**: In the `# Private helpers` section, after the `_media_type()` function (after line 183)  
**Action**: Add new private helper function

**Current value (verified from `/mnt/c/Users/Epkone/UXIQ/ui-analyzer/ui_analyzer/handler.py`):**
```python
def _media_type(image_source: str) -> str:
    """Derive MIME type from image source.

    URL (Playwright always captures PNG) → "image/png"
    .jpg / .jpeg → "image/jpeg"
    .webp → "image/webp"
    Default → "image/png"
    """
    lower = image_source.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/png"
```

**What to add** (append at the end of the file, after `_media_type()`):
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

**What it does**: Finds the position of `<audit_report>` in the raw Claude response. Returns everything before it, stripped of leading/trailing whitespace. If no `<audit_report>` tag is found, returns the entire raw string stripped (treating the whole response as preamble). Returns `""` if the string is empty or whitespace-only.

**Verification**: File compiles without errors.

---

### Step 2: Update `analyze_ui_screenshot()` call site in `handler.py`

**File**: `ui-analyzer/ui_analyzer/handler.py`  
**Location**: The `# 8. Parse Claude's XML response` comment block (lines 139–156)  
**Action**: Replace the existing step 8 through the final `return` with the preamble-aware version

**Current value (verified from `/mnt/c/Users/Epkone/UXIQ/ui-analyzer/ui_analyzer/handler.py`):**
```python
    # 8. Parse Claude's XML response
    audit_report = parse(response.content[0].text)

    # 9. Compute scores
    scores = compute(audit_report)

    # 10. Determine axe_succeeded flag
    axe_succeeded = isinstance(axe_result, AxeCoreResult)

    # 11. Render and return Markdown report
    return render(
        report=audit_report,
        scores=scores,
        app_type=req.app_type,
        image_source=req.image_source,
        axe_succeeded=axe_succeeded,
        model=MODEL,
    )
```

**Replace with:**
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

**What it does**: Captures the raw response text, extracts any preamble before `<audit_report>`, then parses and renders as before. If preamble is non-empty after stripping, it is prepended to the final output separated by exactly one blank line (`"\n\n"`). The return type remains `str`.

**Verification**: File compiles without errors. Existing tests for no-preamble paths (`test_valid_file_path_returns_markdown_with_all_tiers`, `test_axe_failure_returns_string_not_exception`) continue to pass — the `MINIMAL_VALID_XML` mock response starts directly with `<audit_report>` so `_extract_preamble()` returns `""` and no prepending occurs.

---

### Step 3: Restore the preamble assertion in `test_handler_non_ui_preamble_passes_through`

**File**: `ui-analyzer/tests/test_handler.py`  
**Location**: `test_handler_non_ui_preamble_passes_through`, assertions block (lines 303–307)  
**Action**: Replace the weakened assertion block with the full spec-09 assertions

**Current value (verified from `/mnt/c/Users/Epkone/UXIQ/ui-analyzer/tests/test_handler.py`):**
```python
    assert isinstance(result, str)
    # Does not raise — preamble prose before <audit_report> is stripped by xml_parser;
    # the valid XML block is extracted and rendered normally.
    assert "## Tier 1" in result
```

**Replace with:**
```python
    assert isinstance(result, str)
    assert "⚠️ The provided image does not appear to be a web UI" in result
    assert "## Tier 1" in result
```

**What it does**: Restores the preamble presence assertion (spec-09 original intent). Both the preamble text and the rendered report body must appear in the output. The comment describing the old (broken) behavior is removed.

**Verification**: `test_handler_non_ui_preamble_passes_through` passes with all three assertions satisfied.

---

### Step 4: Add `test_handler_no_preamble_output_unchanged`

**File**: `ui-analyzer/tests/test_handler.py`  
**Location**: After `test_handler_non_ui_preamble_passes_through` (after line 307), before the integration tests section  
**Action**: Add new unit test

**Test to add:**
```python
# ---------------------------------------------------------------------------
# Unit: no preamble → output starts with "# UI Analysis Report" (no leading blank lines)
# ---------------------------------------------------------------------------

def test_handler_no_preamble_output_unchanged(fixtures_dir, mocker):
    """Response starting directly with <audit_report> → output is unchanged (no extra whitespace prepended)."""
    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        MINIMAL_VALID_XML
    )

    result = analyze_ui_screenshot(f"{fixtures_dir}/dashboard_good.png", "web_dashboard")

    assert result.startswith("# UI Analysis Report")
```

**What it does**: Confirms the happy path (no preamble) is unaffected — when `<audit_report>` is the first content, `_extract_preamble()` returns `""`, no prepending occurs, and the output starts directly with `# UI Analysis Report`.

**Verification**: Test passes.

---

### Step 5: Add `test_handler_whitespace_only_preamble_not_prepended`

**File**: `ui-analyzer/tests/test_handler.py`  
**Location**: After `test_handler_no_preamble_output_unchanged`  
**Action**: Add new unit test

**Test to add:**
```python
# ---------------------------------------------------------------------------
# Unit: whitespace-only preamble → suppressed, output starts with "# UI Analysis Report"
# ---------------------------------------------------------------------------

def test_handler_whitespace_only_preamble_not_prepended(fixtures_dir, mocker):
    """Response with whitespace-only text before <audit_report> → preamble suppressed."""
    WHITESPACE_PREAMBLE_XML = "   \n\n" + MINIMAL_VALID_XML

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        WHITESPACE_PREAMBLE_XML
    )

    result = analyze_ui_screenshot(f"{fixtures_dir}/dashboard_good.png", "web_dashboard")

    assert result.startswith("# UI Analysis Report")
```

**What it does**: Confirms that a whitespace-only string before `<audit_report>` (e.g. `"   \n\n"`) strips to `""` and is not prepended, so the output still begins with `# UI Analysis Report`.

**Verification**: Test passes.

---

### Step 6: Add `test_handler_no_xml_preamble_shown`

**File**: `ui-analyzer/tests/test_handler.py`  
**Location**: After `test_handler_whitespace_only_preamble_not_prepended`  
**Action**: Add new unit test

**Test to add:**
```python
# ---------------------------------------------------------------------------
# Unit: no <audit_report> at all → entire response is preamble; malformed warning also shown
# ---------------------------------------------------------------------------

def test_handler_no_xml_preamble_shown(fixtures_dir, mocker):
    """Response with no <audit_report> tag → entire response used as preamble; malformed warning present."""
    NO_XML_RESPONSE = "I cannot analyze this image."

    mocker.patch(
        "ui_analyzer.handler.resolve",
        return_value=_make_resolved_file(),
    )
    mock_create = mocker.patch("ui_analyzer.handler.anthropic.Anthropic")
    mock_create.return_value.messages.create.return_value = _make_claude_response(
        NO_XML_RESPONSE
    )

    result = analyze_ui_screenshot(f"{fixtures_dir}/dashboard_good.png", "web_dashboard")

    assert result.startswith("I cannot analyze this image.")
    assert "⚠️" in result or "malformed" in result.lower() or "warning" in result.lower()
```

**What it does**: Confirms the "no XML at all" edge case. When `start == -1`, `_extract_preamble()` returns the entire response string stripped. That preamble is prepended. `parse()` still receives the full raw string (no XML found → returns empty `AuditReport` with parse warnings), and `render()` emits a malformed-response warning. Both the preamble and the warning appear in the output.

**Verification**: Test passes.

---

### Step 7: Run the full unit test suite

**Action**: Run all non-integration tests from the `ui-analyzer/` directory.

**Command**:
```bash
cd /mnt/c/Users/Epkone/UXIQ/ui-analyzer && pytest tests/ -m "not integration" -v
```

**Expected outcome**: All tests pass, 0 failures. In particular:
- `test_handler_non_ui_preamble_passes_through` — preamble assertion passes
- `test_handler_no_preamble_output_unchanged` — no-preamble path unaffected
- `test_handler_whitespace_only_preamble_not_prepended` — whitespace suppressed
- `test_handler_no_xml_preamble_shown` — full-response-as-preamble path works
- `test_valid_file_path_returns_markdown_with_all_tiers` — no regression
- `test_axe_failure_returns_string_not_exception` — no regression

---

## Post-Implementation Checklist
- [ ] `pytest tests/ -m "not integration"` exits 0
- [ ] `test_handler_non_ui_preamble_passes_through` passes with preamble assertion (`"⚠️ The provided image does not appear to be a web UI" in result`)
- [ ] `test_handler_no_preamble_output_unchanged` passes (output starts with `"# UI Analysis Report"`)
- [ ] `test_handler_whitespace_only_preamble_not_prepended` passes (whitespace-only preamble suppressed)
- [ ] `test_handler_no_xml_preamble_shown` passes (entire response as preamble; malformed warning present)
- [ ] `test_valid_file_path_returns_markdown_with_all_tiers` still passes (no regression)
- [ ] `test_axe_failure_returns_string_not_exception` still passes (no regression)
- [ ] `xml_parser.py` is not modified
- [ ] `AuditReport` dataclass is not modified
- [ ] `report_renderer.py` is not modified
- [ ] `_extract_preamble()` is a private module-level function in `handler.py` (not a method)
- [ ] Preamble separator is exactly `"\n\n"` (not `"\n"`, not `"\n\n\n"`)
- [ ] Return type of `analyze_ui_screenshot()` is still `str`

## Verification Approach

Run `cd /mnt/c/Users/Epkone/UXIQ/ui-analyzer && pytest tests/ -m "not integration" -v` after completing all steps. No build step required (pure Python). The test suite uses `pytest-mock` (already installed per `pyproject.toml`) and requires no API key.

If any test fails, read the failure message carefully. The most likely failure modes are:
1. `test_handler_no_preamble_output_unchanged` failing — means `render()` does not start the output with `# UI Analysis Report`; inspect the actual output prefix to update the assertion if the header text differs slightly.
2. `test_handler_no_xml_preamble_shown` — the `NO_XML_RESPONSE` string `"I cannot analyze this image."` is shorter than 14 chars (the length of `<audit_report>`) so `find()` will return -1; confirm `_extract_preamble()` handles this correctly.

## Commit Message (draft)
feat: pass Claude preamble through to final Markdown output

When Claude prepends prose before <audit_report> (e.g. a non-UI disclaimer),
that text was silently discarded by xml_parser.parse(). This change adds
_extract_preamble() to handler.py to capture text before <audit_report> and
prepend it to the rendered output, separated by a blank line. The weakened
preamble assertion in test_handler_non_ui_preamble_passes_through is restored,
and three new unit tests cover the no-preamble, whitespace-only, and no-XML paths.
