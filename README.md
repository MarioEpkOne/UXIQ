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
# Analyze a local screenshot
uxiq analyze path/to/screenshot.png --app-type web_dashboard

# Analyze a live URL (also runs axe-core accessibility checks)
uxiq analyze https://example.com --app-type landing_page

# Save report to a file
uxiq analyze screenshot.png --app-type forms -o report.md

# List valid app types
uxiq list-app-types
```

**Valid app types:** `web_dashboard`, `landing_page`, `onboarding_flow`, `forms`

### Python API

```python
from ui_analyzer import analyze_ui_screenshot

report = analyze_ui_screenshot("path/to/screenshot.png", "web_dashboard")
print(report)  # Markdown string
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

For URL sources, [axe-core](https://github.com/dequelabs/axe-core) accessibility checks are run via Playwright and fed into the audit as additional context.

## Development

```bash
cd ui-analyzer
pytest
```

Integration tests are skipped automatically when `UXIQ_ANTHROPIC_API_KEY` is not set.
