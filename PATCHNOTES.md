<!-- last-commit: a716c0105d7c2d5e6557b7a1326af6ec0a2cdfb0 -->
# Patch Notes

## v0.2.0 — 2026-04-15

### initial commit (specs only)
Added the full specification suite for the `ui-analyzer` tool — a parent spec plus nine child specs covering every module from project bootstrap through the final test suite. This establishes the complete design blueprint before any implementation begins.

### bootstrap ui-analyzer package scaffold
Created the `ui-analyzer` Python package skeleton: `pyproject.toml` with hatchling build backend, runtime dependencies (anthropic, playwright, pillow, pyyaml, pydantic), dev dependencies (pytest, pytest-asyncio, pytest-mock), the `UIAnalyzerError` exception class, and an `ANTHROPIC_API_KEY` guard that raises at import time when the key is absent. All downstream specs depend on this foundation.

### wrap-up pipeline artifacts for spec-01 project bootstrap
Committed the full pipeline paper trail for the project-bootstrap spec: implementation plan, working log, fixer log, audit report (with re-audit), and `learnings.md`. Also moved `spec-01-project-bootstrap.md` to `specs/applied/` to mark it as complete.
