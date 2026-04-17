# UXIQ — UI Analyzer

## What This Project Is

A Python library (`ui-analyzer`) that audits UI screenshots using Claude's vision API. Given an image (URL, local path, or base64) and an app type, it produces a structured Markdown accessibility and UX audit report.

## Architecture

```
ui-analyzer/
  ui_analyzer/
    handler.py          # Public entry point: analyze_ui_screenshot(image_source, app_type) -> str
    image_source.py     # Resolve image input to base64
    axe_runner.py       # Run axe-core accessibility checks (Playwright, URL sources only)
    context_events.py   # ContextEvent dataclass + XML serialization
    prompt_builder.py   # Assemble the structured Claude message thread
    prompts.py          # SYSTEM_PROMPT constant
    xml_parser.py       # Deserialize Claude's <audit_report> XML → typed dataclasses
    scorer.py           # Compute per-tier star ratings + overall score
    report_renderer.py  # Render final Markdown audit report
    tool_definition.py  # Claude Tool Use JSON schema for registering as a tool
    rubric/             # YAML rubric definitions (tiers 1–4)
```

## Key Conventions

- **Single public function**: `analyze_ui_screenshot(image_source, app_type)` in `handler.py` — chains all 10 pipeline stages.
- **Never raises on partial failures**: axe-core failures, malformed XML, and partial Claude output are degraded gracefully. Only `UIAnalyzerError` is raised on hard failures.
- **Preamble passthrough**: any prose Claude outputs before the `<audit_report>` XML is captured and prepended to the Markdown output.
- **Specs**: new specs go in `specs/` (root). Implemented specs move to `specs/applied/`.
- **Tests**: `pytest` with `asyncio_mode = auto`. Integration tests auto-skip when `ANTHROPIC_API_KEY` is unset.

## Commands

```bash
cd ui-analyzer
pip install -e ".[dev]"
pytest
```

> **WSL2 note**: `UXIQ_ANTHROPIC_API_KEY` is set in `~/.bashrc`. Non-login shells (e.g. Claude Code sessions) don't source it automatically. Prefix CLI invocations with `source ~/.bashrc &&` or run it once before using `uxiq analyze`.
