<!-- last-commit: f1fb8214409978d95b38bd97f3da125eda069f33 -->
# Patch Notes

## v0.4.0 — 2026-04-15

### implement xml_parser and AuditReport dataclasses
Adds `xml_parser.py`, which deserializes the LLM's structured XML audit output into typed Python dataclasses (`AuditReport`, `Finding`, `Tier4Finding`). Handles all four tier variants, extracts Nielsen heuristic and WCAG criterion metadata, and surfaces parse warnings for malformed or partially-valid XML rather than raising hard errors. Includes 384-line test suite covering happy paths, malformed inputs, and edge cases across all tier types.

### move spec-03 to applied subfolder
Moves `spec-03-axe-core-runner.md` into `specs/applied/` to mark the axe-core runner spec as complete and keep the active specs directory uncluttered.

## v0.3.0 — 2026-04-15

### implement image_source.py with URL capture and file loading
Adds `image_source.py` as the first data-ingestion module, handling both URL screenshots (via Playwright Chromium) and local file paths (PNG/JPG/WebP). Images with a longest edge over 1568px are automatically downsampled with Pillow LANCZOS before passing downstream. Also establishes the test fixtures directory with five synthetic images and 11 unit tests covering all file-mode and URL error paths.

### pipeline artifacts for spec-02 image-source-resolution
Commits the implementation plan, working log, and retro for spec-02; moves the spec to `specs/applied/` to mark it complete.

### implement axe_runner.py with WCAG 2.1 AA axe-core integration
Adds `axe_runner.py`, which launches a dedicated Playwright browser per call, injects axe-core 4.9.1 from CDN, and runs WCAG 2.1 AA checks. Maps four axe rules to WCAG criteria (1.4.3, 1.4.11, 2.5.8, 1.4.1), extracts contrast ratios and touch-target sizes from node data, and returns soft `AxeFailure` on any error rather than raising — keeping the pipeline fault-tolerant when axe-core is unavailable.

### enforce axe-core timeout via Promise.race (remove invalid page.evaluate timeout kwarg)
Playwright's Python `page.evaluate()` does not accept a `timeout` keyword argument; the previous implementation silently ignored the intended 10-second limit. Replaced with a JS-side `Promise.race` + `setTimeout(10000)` to properly enforce the cutoff. Also adds `browser.close()` on all early-return failure paths to prevent browser leaks.

### spec-03 pipeline artifacts (axe-core runner impl plan, audit, learnings)
Commits the full spec-03 pipeline paper trail: implementation plan, audit report, fixer log, and learnings additions. Includes the spec-03 spec file.

### add rubric definition modules (spec-04)
Creates the `ui_analyzer/rubric/` package with all static tier definition constants used by the prompt builder: WCAG/Gestalt/Nielsen rubric dicts for Tiers 1–3, four app-type-specific Tier 4 dicts, and the raw `OUTPUT_SCHEMA_XML` string for verbatim injection into the LLM user message. None of these generate content dynamically — they are pure data modules that can be diffed and iterated independently of pipeline logic.

### wrap-up pipeline artifacts for spec-04 rubric definitions
Commits the spec-04 implementation plan and audit retro to the repository.

## v0.2.0 — 2026-04-15

### initial commit (specs only)
Added the full specification suite for the `ui-analyzer` tool — a parent spec plus nine child specs covering every module from project bootstrap through the final test suite. This establishes the complete design blueprint before any implementation begins.

### bootstrap ui-analyzer package scaffold
Created the `ui-analyzer` Python package skeleton: `pyproject.toml` with hatchling build backend, runtime dependencies (anthropic, playwright, pillow, pyyaml, pydantic), dev dependencies (pytest, pytest-asyncio, pytest-mock), the `UIAnalyzerError` exception class, and an `ANTHROPIC_API_KEY` guard that raises at import time when the key is absent. All downstream specs depend on this foundation.

### wrap-up pipeline artifacts for spec-01 project bootstrap
Committed the full pipeline paper trail for the project-bootstrap spec: implementation plan, working log, fixer log, audit report (with re-audit), and `learnings.md`. Also moved `spec-01-project-bootstrap.md` to `specs/applied/` to mark it as complete.
