# Spec 01 — Project Bootstrap & Package Scaffold

**Parent spec:** spec--2026-04-15--15-30--ui-screenshot-analyzer.md  
**Status:** Ready for implementation  
**Depends on:** nothing  
**Blocks:** all other specs

---

## Goal

Create the package skeleton, dependency manifest, and the two cross-cutting primitives every other module in the project needs:
- `UIAnalyzerError` — the single exception class the tool raises on hard failures
- API-key guard — raises at import time if `ANTHROPIC_API_KEY` is absent

---

## Scope

Files created by this spec:

```
ui-analyzer/
├── pyproject.toml
├── .env.example
└── ui_analyzer/
    ├── __init__.py          ← exports UIAnalyzerError; validates ANTHROPIC_API_KEY
    └── exceptions.py        ← UIAnalyzerError definition
```

No other files. All other modules are created by their own specs.

---

## pyproject.toml

### Build system

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Project metadata

```toml
[project]
name = "ui-analyzer"
version = "0.1.0"
requires-python = ">=3.11"
```

### Runtime dependencies

```toml
dependencies = [
    "anthropic>=0.25.0",
    "playwright>=1.43.0",
    "pillow>=10.0.0",
    "pyyaml>=6.0",
    "pydantic>=2.0",
]
```

### Dev / test dependencies

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.14",
]
```

### Tool config

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

---

## .env.example

```
ANTHROPIC_API_KEY=your_key_here
```

---

## exceptions.py

```python
class UIAnalyzerError(Exception):
    """Raised on hard failures in ui-analyzer.

    Hard failures (raise UIAnalyzerError):
        - URL load failure (404, timeout, blank page)
        - File not found or unsupported type
        - ANTHROPIC_API_KEY not set
        - Anthropic API timeout or rate limit

    Soft failures (return degraded Markdown report, never raise):
        - axe-core failure
        - Claude returning malformed XML
        - Partial tier output
    """
```

---

## `__init__.py`

```python
import os
from ui_analyzer.exceptions import UIAnalyzerError

if not os.getenv("ANTHROPIC_API_KEY"):
    raise UIAnalyzerError("ANTHROPIC_API_KEY environment variable not set.")

__all__ = ["UIAnalyzerError"]
```

**Critical rule:** The API key check must execute at import time, not lazily inside any function. This ensures callers fail fast rather than discovering the missing key after Playwright has already launched.

---

## Constraints

- `UIAnalyzerError` must be a plain `Exception` subclass with no extra fields in v1.
- No logging configuration goes here. Logging is the responsibility of individual modules.
- The `__init__.py` must NOT import any third-party library except `os` and `UIAnalyzerError`. Heavy imports (anthropic, playwright, PIL) are deferred to the modules that need them.

---

## Success Criteria

- [ ] `pyproject.toml` is valid (`pip install -e .[dev]` succeeds)
- [ ] `from ui_analyzer import UIAnalyzerError` works
- [ ] Importing `ui_analyzer` with `ANTHROPIC_API_KEY` unset raises `UIAnalyzerError`
- [ ] Importing `ui_analyzer` with `ANTHROPIC_API_KEY` set raises nothing
- [ ] No circular imports
