# Bug: Agents Write Unit Tests That Make Real Anthropic API Calls

**Date**: 2026-04-16
**Status**: Open
**Severity**: HIGH

---

## Symptom

Developer agents (e.g. the impl subagent in the pipeline) write unit tests that instantiate `anthropic.Anthropic()` or `anthropic.AsyncAnthropic()` and make real API calls during the default `pytest` run. This costs real money and is never acceptable in unit tests.

---

## Root Cause

Two gaps in the project infrastructure allow this to happen:

1. **No behavioral constraint** — There is no `tests/CLAUDE.md` file. When an agent navigates into the `tests/` directory to write tests, Claude Code loads `CLAUDE.md` files from the current directory automatically. Without one in `tests/`, the agent has no local guidance and defaults to writing whatever test pattern seems natural — including tests that call the real API.

2. **No structural enforcement** — There is no network-blocking mechanism in the test suite. `pytest-socket` is not installed and `--disable-socket` is not set in `pyproject.toml`. Any test that opens a socket succeeds, so real API calls go undetected until the bill arrives.

---

## Recommended Fix

### Fix 1 — `ui-analyzer/tests/CLAUDE.md` (behavioral)

Create a `CLAUDE.md` in the `tests/` directory. Claude Code automatically loads it when an agent works in that directory. It must state clearly:

- Unit tests must never instantiate `anthropic.Anthropic()` or `anthropic.AsyncAnthropic()` without mocking.
- All Anthropic client calls must be patched with `unittest.mock.patch` or `pytest-mock`.
- Integration tests (filename pattern `test_*_integration.py`) may use the real API but must begin with a skip guard that checks for `ANTHROPIC_API_KEY`.
- The reason: real API calls cost money and must never run as part of the default `pytest` suite.

Include a short example of the correct mock pattern so agents can follow it without guessing.

### Fix 2 — `pytest-socket` in `pyproject.toml` (structural)

Add `pytest-socket` to `[project.optional-dependencies] dev` and add `--disable-socket` to `[tool.pytest.ini_options] addopts`. This blocks all socket connections (not just Anthropic) during the default test run at the OS level. Integration tests that legitimately need network access can opt in per-test with `@pytest.mark.enable_socket`.

This makes real API calls structurally impossible in unit tests — no agent can bypass it accidentally.

---

## Affected Files

- `ui-analyzer/tests/` — missing `CLAUDE.md`
- `ui-analyzer/pyproject.toml` — missing `pytest-socket` dep and `--disable-socket` in `addopts`

---

## Also Revert

The root `CLAUDE.md` was modified during investigation to add testing rules there. That change should be reverted — testing rules belong in `tests/CLAUDE.md`, not the root.
