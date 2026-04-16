# Spec: CLI Entry Point (`uxiq`)

**Date**: 2026-04-16  
**Status**: Ready for planning

---

## Goal

Add a `uxiq` CLI command to the `ui-analyzer` package so users can run UI audits directly from the terminal without writing Python code.

```
uxiq analyze screenshot.png --app-type web_dashboard
uxiq analyze https://example.com --app-type landing_page -o report.md
uxiq list-app-types
uxiq --version
```

---

## Current State

- `ui_analyzer` is a Python library with one public function: `analyze_ui_screenshot(image_source, app_type) -> str`
- No CLI exists yet
- `pyproject.toml` has no `[project.scripts]` entry
- `ui_analyzer/__init__.py` raises `UIAnalyzerError` at **import time** if `UXIQ_ANTHROPIC_API_KEY` is not set — this must be fixed or worked around so `uxiq --version` and `uxiq list-app-types` function without the API key

---

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| CLI framework | `argparse` (stdlib) | No new dependencies |
| CLI module location | `ui_analyzer/cli.py` | Inside the package, registered via pyproject.toml |
| Script name | `uxiq` | Matches the product name |
| App type input | `--app-type / -t` flag | Explicit, self-documenting |
| Missing app-type behavior | Error with usage hint | Fail fast with clear guidance |
| Output | Raw Markdown to stdout | Pipe-friendly |
| `-o / --output` flag | Save report to file | Optional, write Markdown to given path |
| API key env var | `UXIQ_ANTHROPIC_API_KEY` only | No change to library behavior |
| Import-time env var check | Move to `analyze_ui_screenshot()` body | Lets `--version`/`list-app-types` work without the key |

---

## Technical Design

### 1. Fix `__init__.py` import-time env var check

Remove the env var check from `ui_analyzer/__init__.py` and move it inside `analyze_ui_screenshot()` in `handler.py`. This allows importing the package for non-analyze commands without needing the API key.

**Before** (`__init__.py`):
```python
if not os.getenv("UXIQ_ANTHROPIC_API_KEY"):
    raise UIAnalyzerError("UXIQ_ANTHROPIC_API_KEY environment variable not set.")
```

**After**: Remove the check from `__init__.py`. Add it at the top of `analyze_ui_screenshot()` in `handler.py`:
```python
def analyze_ui_screenshot(image_source: str, app_type: str) -> str:
    if not os.getenv("UXIQ_ANTHROPIC_API_KEY"):
        raise UIAnalyzerError("UXIQ_ANTHROPIC_API_KEY environment variable is not set.")
    ...
```

### 2. New file: `ui_analyzer/cli.py`

Using `argparse` with subcommands:

```
uxiq
├── analyze <image_source>
│   ├── --app-type / -t  (required)
│   └── --output / -o    (optional, path to write report)
└── list-app-types
```

Top-level flags:
- `--version` / `-V`: print version from `importlib.metadata` and exit

#### Exit codes
- `0`: success
- `1`: user error (bad args, invalid app-type, file not found, missing API key)
- `2`: argparse usage error (automatic from argparse)

#### Error output
- All errors go to `stderr`
- Normal output (report, version, app type list) goes to `stdout`

#### `uxiq analyze` behavior
1. Parse `image_source` (positional) and `--app-type` (required)
2. Call `analyze_ui_screenshot(image_source, app_type)`
3. If `-o <path>`: write Markdown to file, print `Report saved to <path>` to stderr
4. If no `-o`: print Markdown to stdout
5. On `UIAnalyzerError` or `pydantic.ValidationError`: print error to stderr, exit 1

#### `uxiq list-app-types` behavior
Print the four valid app types, one per line:
```
forms
landing_page
onboarding_flow
web_dashboard
```

#### `uxiq --version` behavior
```
uxiq 0.1.0
```
Uses `importlib.metadata.version("ui-analyzer")`.

### 3. Register script in `pyproject.toml`

```toml
[project.scripts]
uxiq = "ui_analyzer.cli:main"
```

### 4. CLI module structure (`cli.py`)

```python
def main() -> None:
    """Entry point registered in pyproject.toml."""
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)  # dispatch to subcommand handler

def _cmd_analyze(args) -> None: ...
def _cmd_list_app_types(args) -> None: ...
def _build_parser() -> argparse.ArgumentParser: ...
```

---

## Edge Cases & Error Handling

| Scenario | Behavior |
|---|---|
| `uxiq analyze` with no `--app-type` | argparse error: "the following arguments are required: --app-type" |
| `--app-type` value not in valid set | `pydantic.ValidationError` caught, print "Invalid app-type: X. Valid: forms, landing_page, onboarding_flow, web_dashboard" → exit 1 |
| File not found | `UIAnalyzerError` caught → print to stderr → exit 1 |
| `UXIQ_ANTHROPIC_API_KEY` not set when running `analyze` | `UIAnalyzerError` caught → print to stderr → exit 1 |
| `UXIQ_ANTHROPIC_API_KEY` not set when running `--version` or `list-app-types` | Works fine (env check moved to `analyze_ui_screenshot()`) |
| `-o` path directory doesn't exist | Catch `OSError` → print to stderr → exit 1 |
| API timeout or rate limit | `UIAnalyzerError` caught → print to stderr → exit 1 |
| `uxiq` with no subcommand | Print help and exit 0 |

---

## Constraints & Invariants

- No new runtime dependencies — use only stdlib and packages already in `pyproject.toml`
- The library's public API (`analyze_ui_screenshot`) must not change signature
- Moving the env var check from `__init__.py` to `handler.py` must not break existing behavior — it still raises `UIAnalyzerError` before any API call is made
- `__init__.py` must still export `UIAnalyzerError`, `analyze_ui_screenshot`, `TOOL_DEFINITION` — only the env var check moves
- Tests that import `ui_analyzer` without `UXIQ_ANTHROPIC_API_KEY` set (e.g., unit tests) must continue to work — this is why the env var check needs to move

---

## Testing Strategy

### Unit tests (no API key required)

New file: `tests/test_cli.py`

Test with `subprocess.run(["python", "-m", "ui_analyzer.cli", ...])` or by calling `main()` directly via `unittest.mock` to avoid import issues.

Use `argparse` parsing directly where possible — avoids subprocess overhead.

| Test | What it checks |
|---|---|
| `uxiq --version` | Prints `uxiq X.Y.Z` to stdout, exit 0 |
| `uxiq list-app-types` | Prints 4 app types to stdout, exit 0 |
| `uxiq analyze` (missing `--app-type`) | Exits 2, message mentions `--app-type` |
| `uxiq analyze file.png --app-type invalid` | Exits 1, message mentions valid app types |
| `uxiq analyze` with `UIAnalyzerError` | Exits 1, error to stderr |
| `uxiq analyze -o /tmp/out.md` | On success, file written, message to stderr |
| `uxiq analyze -o /nonexistent/out.md` | Exits 1, OSError message to stderr |
| No subcommand | Exits 0, help text printed |

### Integration test (requires `UXIQ_ANTHROPIC_API_KEY`)

Existing integration tests in `test_handler.py` cover the library end-to-end. CLI integration test is optional and auto-skips when key is unset (same pattern as existing tests).

---

## Open Questions

None — all blocking decisions resolved.
