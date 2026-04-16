# UXIQ — UI Analyzer

A Python library and CLI that audits UI screenshots using Claude's vision API. Given an image and an app type, it produces a structured Markdown accessibility and UX audit report.

## Requirements

- Python 3.11+
- An Anthropic API key set as `UXIQ_ANTHROPIC_API_KEY`

## Installation

```bash
cd ui-analyzer
pip install -e ".[dev]"
playwright install chromium  # required for URL-based axe-core checks
```

## Usage

### CLI

```bash
# Analyze a live URL
uxiq analyze https://example.com --app-type web_dashboard

# Save report to a file
uxiq analyze https://example.com --app-type landing_page -o report.md

# List valid app types
uxiq list-app-types
```

**Valid app types:** `web_dashboard`, `landing_page`, `onboarding_flow`, `forms`

> **Note:** Only URLs are accepted as input. Local file paths and base64 strings are not supported.

### Python API

```python
from ui_analyzer import analyze_ui_screenshot

report = analyze_ui_screenshot("https://example.com", "web_dashboard")
print(report)  # Markdown string

# Skip the verification pass
report = analyze_ui_screenshot("https://example.com", "web_dashboard", verify=False)
```

### As a Claude Tool

```python
from ui_analyzer import TOOL_DEFINITION
# Pass TOOL_DEFINITION to your Claude client's tools parameter
```

## What the Report Contains

The audit is structured across four tiers:

| Tier | Focus |
|------|-------|
| 1 | Accessibility (contrast, labels, keyboard nav) |
| 2 | Visual hierarchy and layout |
| 3 | UX patterns and interaction design |
| 4 | App-type-specific criteria |

Each tier receives a star rating; the report also includes an overall score and actionable recommendations.

For each analysis, axe-core accessibility checks and interactive DOM extraction are run via Playwright and fed into the audit as additional context. A second verification pass reviews the primary audit output by default — this can be disabled with `verify=False` at roughly 10–15% additional cost.

A per-run debug file is written to `runs/` after each analysis.

## Development

```bash
cd ui-analyzer
pytest
```

Integration tests are skipped automatically when `UXIQ_ANTHROPIC_API_KEY` is not set.
