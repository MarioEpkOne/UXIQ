# Spec 09 — Tests

**Parent spec:** spec--2026-04-15--15-30--ui-screenshot-analyzer.md  
**Status:** Ready for implementation  
**Depends on:** Specs 01–08 (all modules under test)  
**Blocks:** nothing

---

## Goal

Implement the full test suite: unit tests for each module, integration tests requiring a live Anthropic API key, and the fixture images used by both.

All unit tests run without internet access, without an Anthropic API key, and without a live browser. Integration tests are skipped when `ANTHROPIC_API_KEY` is not set.

---

## Scope

Files created by this spec:

```
tests/
├── conftest.py
├── fixtures/
│   ├── dashboard_good.png      ← clean SaaS dashboard
│   ├── dashboard_bad.png       ← dense, low-contrast dashboard
│   ├── landing_page.png        ← marketing page
│   ├── form.png                ← multi-field form
│   └── not_a_ui.jpg            ← photograph (not a UI)
├── test_image_source.py
├── test_axe_runner.py
├── test_context_events.py
├── test_prompt_builder.py
├── test_xml_parser.py
├── test_scorer.py
├── test_report_renderer.py
└── test_handler.py             ← unit + integration tests
```

---

## conftest.py

```python
import os
import pytest

# IMPORTANT: ui_analyzer/__init__.py raises UIAnalyzerError at import time
# if ANTHROPIC_API_KEY is unset. Set a fake key before any ui_analyzer import
# so that unit tests (which mock the API) can import the package.
# This must happen before pytest collects test modules.
if not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "test-key-unit-tests"

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as requiring a real ANTHROPIC_API_KEY"
    )

@pytest.fixture
def fixtures_dir():
    return os.path.join(os.path.dirname(__file__), "fixtures")
```

Integration tests are decorated with `@pytest.mark.integration` and skipped if the key value is still the fake sentinel:

```python
import pytest
import os

_REAL_KEY = os.getenv("ANTHROPIC_API_KEY", "")
skip_if_no_key = pytest.mark.skipif(
    _REAL_KEY in ("", "test-key-unit-tests"),
    reason="ANTHROPIC_API_KEY not set to a real key"
)
```

---

## Fixtures

Fixture images are committed to the repo. They are small PNG/JPG files created specifically for testing. Each fixture's content must be sufficient to trigger the described scenario:

| File | Purpose | Minimum requirements |
|------|---------|---------------------|
| `dashboard_good.png` | SaaS dashboard with few accessibility issues | Dark text on light background, clear layout |
| `dashboard_bad.png` | Dense, low-contrast dashboard | Light gray text on white, small touch targets |
| `landing_page.png` | Marketing landing page | Headline, CTA button, trust section visible |
| `form.png` | Multi-field form | 3+ labeled inputs, at least one required field |
| `not_a_ui.jpg` | Photograph of a landscape or object | No UI elements whatsoever |

Fixtures do not need to be real screenshots — they can be synthetic images that satisfy the content requirements. They must be valid PNG/JPG files (not empty).

---

## test_image_source.py

```python
# test_image_source_file_valid
# Given a valid PNG file path
# Returns ResolvedImage with source_type="file", non-empty bytes, correct dimensions

# test_image_source_file_missing
# Given a path that does not exist
# Raises UIAnalyzerError with message "File not found: ..."

# test_image_source_file_bad_extension
# Given a .pdf file path
# Raises UIAnalyzerError with message "Unsupported file type. Accepted: PNG, JPG, JPEG, WebP."

# test_image_resize_large
# Given an image with longest edge > 1568px (synthetic bytes via Pillow)
# Returns bytes where longest edge <= 1568px
# Original bytes unchanged (different object)

# test_image_resize_small
# Given an image with longest edge <= 1568px
# Returns bytes identical to input (no resize applied)

# test_image_source_url (integration — requires Playwright)
# Given a reachable URL (use a stable fixture URL or mock)
# Returns ResolvedImage with source_type="url", non-empty bytes, width=1280, height=800
```

URL-specific error tests (404, timeout, blank page) require mocking Playwright. Use `pytest-mock` to patch `playwright.sync_api.sync_playwright`.

---

## test_axe_runner.py

```python
# test_run_axe_returns_none_on_injection_failure
# Mock page.add_script_tag to raise Exception
# run_axe() returns None, no exception propagated

# test_run_axe_returns_none_on_evaluation_timeout
# Mock page.evaluate to raise TimeoutError
# run_axe() returns None, no exception propagated

# test_run_axe_returns_none_on_unexpected_error
# Mock entire sync_playwright context to raise RuntimeError
# run_axe() returns None, no exception propagated

# test_run_axe_never_raises
# Any exception inside the function → return None only
# Property-based: parametrize over multiple failure modes
```

All axe_runner tests mock Playwright. No live browser is launched.

---

## test_context_events.py

```python
# test_event_to_xml_with_dict
# ContextEvent(type="rubric_tier1", data={"protocol": "WCAG"})
# Output: "<rubric_tier1>\nprotocol: WCAG\n</rubric_tier1>"
# (YAML-serialized body)

# test_event_to_xml_with_str
# ContextEvent(type="output_schema", data="<raw xml>")
# Output: "<output_schema>\n<raw xml>\n</output_schema>"
# (verbatim — no YAML)

# test_event_to_xml_with_dataclass
# ContextEvent(type="axe_core_result", data=AxeCoreResult(...))
# Output contains "<axe_core_result>" tag and YAML body
# Does not raise

# test_thread_to_prompt_structure
# thread_to_prompt([ContextEvent(type="rubric_tier1", data={})])
# Starts with "Here is everything known about this analysis task:"
# Ends with "What is the complete audit report?"

# test_thread_to_prompt_ordering
# Multiple events → output order matches input list order
```

---

## test_prompt_builder.py

```python
# test_build_thread_with_axe_data
# build_thread(..., axe_result=AxeCoreResult(...))
# events[1].type == "axe_core_result"
# events[0].data["tier1_mode"] == "authoritative"

# test_build_thread_axe_failure_url_mode
# build_thread(..., source_type="url", axe_result=AxeFailure(reason="axe-core timed out"))
# events[1].type == "axe_unavailable"
# events[1].data["reason"] == "axe-core timed out"
# events[0].data["tier1_mode"] == "estimated"

# test_build_thread_file_mode
# build_thread(..., source_type="file", axe_result=None)
# No event with type == "axe_core_result" or "axe_unavailable"
# events[1].type == "rubric_tier1"

# test_build_thread_canonical_order
# build_thread with axe_result present
# Order: analysis_request → axe_core_result → rubric_tier1 → rubric_tier2
#         → rubric_tier3 → rubric_tier4 → output_schema

# test_analysis_request_contains_viewport
# events[0].data["viewport_width"] == 1280
# events[0].data["viewport_height"] == 800

# test_system_prompt_structure
# SYSTEM_PROMPT contains "inventory"
# SYSTEM_PROMPT contains "structure"
# SYSTEM_PROMPT contains "rubric"
# SYSTEM_PROMPT contains "Do not compute numeric scores"
```

---

## test_xml_parser.py

```python
FULL_REPORT_XML = """
<audit_report>
  <confidence level="high"></confidence>
  <inventory>Nav bar, hero button, 3 metric cards</inventory>
  <structure_observation>2-column layout, blue primary color</structure_observation>
  <tier1_findings>
    <finding criterion="1.4.3" element=".nav-link" result="FAIL" estimated="false">
      <observed>contrast ratio 2.8:1</observed>
      <required>4.5:1 for normal text</required>
      <recommendation>Change to #374151</recommendation>
    </finding>
    <finding criterion="1.4.1" element="status indicator" result="PASS" estimated="false">
      <observed>color + icon used</observed>
      <required>not sole indicator</required>
      <recommendation>none</recommendation>
    </finding>
  </tier1_findings>
  <tier2_findings>
    <finding principle="proximity" severity="2" element="Metric cards">
      <issue>4px gap too small</issue>
      <recommendation>Increase to 24px</recommendation>
      <nielsen_tag>4</nielsen_tag>
    </finding>
  </tier2_findings>
  <tier3_findings>
    <finding principle="visual_hierarchy" severity="1" element="CTA button">
      <issue>Not dominant enough</issue>
      <recommendation>Increase size</recommendation>
      <nielsen_tag>8</nielsen_tag>
    </finding>
  </tier3_findings>
  <tier4_findings>
    <finding pattern="data_ink_ratio" element="Sidebar">
      <issue>Icon-only nav</issue>
      <recommendation>Add labels</recommendation>
    </finding>
  </tier4_findings>
</audit_report>
"""

# test_xml_parser_full_response
# parse(FULL_REPORT_XML) → AuditReport
# tier1_findings has 2 items
# tier1_findings[0].result == "FAIL", estimated == False
# tier2_findings[0].severity == 2, nielsen_tag == 4
# tier4_findings[0].pattern == "data_ink_ratio"
# parse_warnings == []

# test_xml_parser_missing_tier
# Remove <tier2_findings> from FULL_REPORT_XML
# parse() → tier2_findings == []
# parse_warnings contains one entry
# All other tiers still populated

# test_xml_parser_no_audit_report_tag
# parse("just prose, no XML tags")
# Returns AuditReport() with all findings empty
# parse_warnings contains "No <audit_report> block found"

# test_xml_parser_malformed_xml
# parse("<audit_report><unclosed>")
# Returns AuditReport() with all findings empty
# parse_warnings is non-empty
# No exception raised

# test_xml_parser_never_raises
# Parametrize over: empty string, random bytes as string, None-like strings
# parse() never raises

# test_tier1_estimated_flag
# Finding with estimated="true" → Tier1Finding.estimated == True
# Finding with estimated="false" → Tier1Finding.estimated == False
```

---

## test_scorer.py

```python
# test_tier1_stars_all_pass
# All findings result="PASS" → 5.0

# test_tier1_stars_60_percent_pass
# 3 PASS, 2 FAIL → 3.0

# test_tier1_stars_no_findings
# [] → 5.0

# test_tier23_stars_no_findings
# [] → 5.0

# test_tier23_stars_all_severity_3
# [severity=3, severity=3] → 1.0

# test_tier23_stars_mixed
# [severity=1, severity=2] → avg=1.5 → 5.0 - 1.5*1.5 = 2.75 → 2.8

# test_overall_weighting
# T1=5.0, T2=3.0, T3=4.0
# overall = round(5.0*0.4 + 3.0*0.35 + 4.0*0.25, 1)
# = round(2.0 + 1.05 + 1.0, 1) = round(4.05, 1) = 4.1

# test_stars_to_display_3_1
# stars_to_display(3.1) → "★★★☆☆"

# test_stars_to_display_5_0
# stars_to_display(5.0) → "★★★★★"

# test_stars_to_display_1_0
# stars_to_display(1.0) → "★☆☆☆☆"
```

---

## test_report_renderer.py

```python
# test_render_contains_all_tier_headers
# render(report_with_all_tiers, scores, ...) output contains:
# "## Tier 1 — Accessibility"
# "## Tier 2 — Visual Structure"
# "## Tier 3 — Usability & Affordance"
# "## Tier 4 — Domain Patterns"

# test_render_fail_finding_has_red_x
# Tier1Finding with result="FAIL" → "❌" in rendered output

# test_render_pass_finding_has_checkmark
# Tier1Finding with result="PASS" → "✅" in rendered output

# test_render_estimated_label
# Tier1Finding with estimated=True → "ESTIMATED" appears in rendered output

# test_render_empty_tier_shows_no_issues_found
# AuditReport with tier2_findings=[] → "No issues found." in Tier 2 section

# test_render_parse_warnings_appended
# AuditReport with parse_warnings=["something wrong"]
# Output contains "⚠️ Claude returned a malformed response"

# test_render_tier4_flag_icon
# Tier4Finding → "🚩" in rendered output

# test_render_severity_3_has_red_circle
# Tier2Finding with severity=3 → "🔴" in rendered output

# test_render_footer_contains_model
# Output ends with line containing "claude-sonnet-4-6"
```

---

## test_handler.py

### Unit tests (mocked — no API key, no browser)

```python
# test_handler_invalid_app_type
# analyze_ui_screenshot("file.png", "invalid_type")
# Raises pydantic.ValidationError before any API call

# test_handler_returns_string_on_malformed_xml
# Mock: resolve() → valid ResolvedImage
# Mock: run_axe() → None (file mode, so not called)
# Mock: anthropic.Anthropic().messages.create() → response with non-XML text
# analyze_ui_screenshot(fixture_png, "web_dashboard")
# Returns str containing "⚠️ Claude returned a malformed response"
# Does not raise

# test_handler_raises_on_api_timeout
# Mock: messages.create() raises anthropic.APITimeoutError
# analyze_ui_screenshot(...) raises UIAnalyzerError

# test_handler_raises_on_rate_limit
# Mock: messages.create() raises anthropic.RateLimitError
# analyze_ui_screenshot(...) raises UIAnalyzerError

# test_handler_axe_failure_does_not_raise
# Mock: run_axe() returns AxeFailure(reason="axe-core JS injection failed")
# Mock: messages.create() → valid XML response
# analyze_ui_screenshot(url, "web_dashboard") returns str
# No exception raised

# test_handler_non_ui_preamble_passes_through
# Mock: messages.create() → response text starting with
#   "⚠️ The provided image does not appear to be a web UI screenshot."
#   followed by a valid <audit_report> block
# analyze_ui_screenshot(fixture_png, "web_dashboard") returns str
# Returned str contains "⚠️ The provided image does not appear to be a web UI"
# Does not raise
```

### Integration tests (require ANTHROPIC_API_KEY)

Decorated with `@skip_if_no_key`:

```python
# test_full_analysis_file_path
# analyze_ui_screenshot(str(fixtures_dir / "dashboard_good.png"), "web_dashboard")
# Returns str
# Contains "## Tier 1", "## Tier 2", "## Tier 3", "## Tier 4"
# Does not raise

# test_full_analysis_url
# analyze_ui_screenshot("https://example.com", "web_dashboard")
# Returns str
# Contains "Authoritative (axe-core)" in report
# Does not raise

# test_non_ui_image
# analyze_ui_screenshot(str(fixtures_dir / "not_a_ui.jpg"), "landing_page")
# Returns str (does not raise)
# May contain "⚠️ The provided image does not appear to be a web UI"
# (Claude decides this — test only asserts no exception)

# test_app_type_forms
# analyze_ui_screenshot(str(fixtures_dir / "form.png"), "forms")
# Returns str containing "## Tier 4 — Domain Patterns (forms)"
```

---

## Constraints

- Unit tests must run in under 5s total on a modern machine (no sleeps, no real network).
- Integration tests may be slow (Playwright + API). No timeout constraint imposed.
- Playwright must never be called in unit tests — all Playwright calls must be mocked.
- `anthropic.Anthropic()` must never be called in unit tests — mock at the `messages.create` level.
- Test files must not import from each other.
- Fixtures must be committed to the repo — no downloading at test time.

---

## Success Criteria

- [ ] `pytest tests/ -m "not integration"` exits 0 with no internet access and no API key
- [ ] All unit tests listed above pass
- [ ] `pytest tests/ -m integration` exits 0 when `ANTHROPIC_API_KEY` is set
- [ ] No test imports from another test file
- [ ] Coverage: all public functions in all modules have at least one unit test
