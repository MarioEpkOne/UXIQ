# Implementation Plan: Project Bootstrap & Package Scaffold

## Header
- **Spec**: specs/applied/spec-01-project-bootstrap.md
- **Worktree**: .claude/worktrees/project-bootstrap/
- **Scope — files in play** (agent must not touch files not listed here):
  - ui-analyzer/pyproject.toml
  - ui-analyzer/.env.example
  - ui-analyzer/ui_analyzer/__init__.py
  - ui-analyzer/ui_analyzer/exceptions.py
- **Reading list** (read these in order before starting, nothing else):
  - None — all files are new creations. No existing files need to be read.

## Environment Assumptions Verified

This spec creates a greenfield package. No test dependencies are installed yet. The implementing agent must install them as part of Step 1 (`pip install -e .[dev]`). The following packages will be installed via that command:

- `pytest>=8.0`
- `pytest-asyncio>=0.23`
- `pytest-mock>=3.14`

The Success Criteria verification steps require `pytest-asyncio` for `asyncio_mode = "auto"` to work, but spec-01 has no test files of its own. Verification is done via manual import checks in a Python shell, not via pytest.

---

## Steps

### Step 1: Create the package directory structure

**Action**: Create the nested directory layout inside the worktree.

Run the following shell commands from the worktree root (`.claude/worktrees/project-bootstrap/`):

```bash
mkdir -p ui-analyzer/ui_analyzer
```

This creates:
- `ui-analyzer/` — the project root for the installable package
- `ui-analyzer/ui_analyzer/` — the Python package directory

**Verification**: Both directories exist at the expected paths.

---

### Step 2: Create `ui-analyzer/ui_analyzer/exceptions.py`

**File**: `ui-analyzer/ui_analyzer/exceptions.py`
**Action**: Create new file

**Full file content**:
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

**What it does**: Defines `UIAnalyzerError` as a plain subclass of `Exception` with no extra fields, no `__init__` override, and no imports. The docstring documents the hard-vs-soft failure contract for future implementers.

**Constraints enforced**:
- Plain `Exception` subclass — no extra fields, no overridden `__init__`.
- No imports of any kind.

**Verification**: File exists. `python -c "from ui_analyzer.exceptions import UIAnalyzerError; assert issubclass(UIAnalyzerError, Exception)"` passes.

---

### Step 3: Create `ui-analyzer/ui_analyzer/__init__.py`

**File**: `ui-analyzer/ui_analyzer/__init__.py`
**Action**: Create new file

**Full file content**:
```python
import os
from ui_analyzer.exceptions import UIAnalyzerError

if not os.getenv("ANTHROPIC_API_KEY"):
    raise UIAnalyzerError("ANTHROPIC_API_KEY environment variable not set.")

__all__ = ["UIAnalyzerError"]
```

**What it does**: On every import of `ui_analyzer`, the API key check runs at module load time. If `ANTHROPIC_API_KEY` is absent from the environment, it raises `UIAnalyzerError` immediately. If the key is present, import completes normally and `UIAnalyzerError` is re-exported so callers can use `from ui_analyzer import UIAnalyzerError`.

**Constraints enforced**:
- Only `os` (stdlib) and `UIAnalyzerError` (internal) are imported — no third-party libraries.
- The key check is top-level (executes at import time, not inside a function).

**Verification**: See Success Criteria steps below.

---

### Step 4: Create `ui-analyzer/pyproject.toml`

**File**: `ui-analyzer/pyproject.toml`
**Action**: Create new file

**Full file content**:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ui-analyzer"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.25.0",
    "playwright>=1.43.0",
    "pillow>=10.0.0",
    "pyyaml>=6.0",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.14",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**What it does**: Declares the package, its Python version requirement, runtime dependencies, and dev/test dependencies. Configures pytest to look in `tests/` with asyncio auto mode.

**Verification**: `pip install -e .[dev]` (run from `ui-analyzer/`) exits 0. No install errors.

---

### Step 5: Create `ui-analyzer/.env.example`

**File**: `ui-analyzer/.env.example`
**Action**: Create new file

**Full file content**:
```
ANTHROPIC_API_KEY=your_key_here
```

**What it does**: Provides a template for developers to copy to `.env` and fill in their API key.

**Verification**: File exists with the single line shown above.

---

### Step 6: Install the package

**Action**: From inside `ui-analyzer/`, install the package in editable mode with dev extras.

```bash
cd ui-analyzer && pip install -e ".[dev]"
```

**What it does**: Installs `ui-analyzer` and all runtime + dev dependencies into the active Python environment. Validates that `pyproject.toml` is syntactically valid and that all dependency specifiers are resolvable.

**Verification**: Command exits 0. Running `pip show ui-analyzer` shows `Name: ui-analyzer`.

---

### Step 7: Verify — import with key unset raises UIAnalyzerError

**Action**: Run the following in a shell (from any directory after Step 6):

```bash
python -c "
import os
# Ensure key is absent
os.environ.pop('ANTHROPIC_API_KEY', None)
# Force reimport (in case already imported in same process)
import importlib, sys
for mod in list(sys.modules.keys()):
    if mod.startswith('ui_analyzer'):
        del sys.modules[mod]
try:
    import ui_analyzer
    print('FAIL: No error raised')
except Exception as e:
    if type(e).__name__ == 'UIAnalyzerError':
        print('PASS: UIAnalyzerError raised:', e)
    else:
        print('FAIL: Wrong exception type:', type(e).__name__, e)
"
```

**Expected output**: `PASS: UIAnalyzerError raised: ANTHROPIC_API_KEY environment variable not set.`

**Verification**: Output starts with `PASS`.

---

### Step 8: Verify — import with key set raises nothing

**Action**: Run the following in a shell:

```bash
ANTHROPIC_API_KEY=test_dummy python -c "
import ui_analyzer
print('PASS: Import succeeded')
print('UIAnalyzerError accessible:', ui_analyzer.UIAnalyzerError)
"
```

**Expected output**:
```
PASS: Import succeeded
UIAnalyzerError accessible: <class 'ui_analyzer.exceptions.UIAnalyzerError'>
```

**Verification**: Output contains `PASS: Import succeeded` and no traceback.

---

### Step 9: Verify — no circular imports

**Action**: Run the following in a shell (with `ANTHROPIC_API_KEY` set):

```bash
ANTHROPIC_API_KEY=test_dummy python -c "
import sys
import ui_analyzer
import ui_analyzer.exceptions
print('All modules imported without circular import errors.')
print('Loaded modules:', [m for m in sys.modules if m.startswith('ui_analyzer')])
"
```

**Expected output**: No `ImportError`, no `partially initialized module` warnings. The loaded modules list should include `ui_analyzer` and `ui_analyzer.exceptions`.

**Verification**: Command exits 0 with no errors in output.

---

### Step 10: Verify — UIAnalyzerError is a plain Exception subclass

**Action**:

```bash
ANTHROPIC_API_KEY=test_dummy python -c "
from ui_analyzer import UIAnalyzerError
assert issubclass(UIAnalyzerError, Exception), 'Not a subclass of Exception'
assert UIAnalyzerError.__bases__ == (Exception,), f'Unexpected bases: {UIAnalyzerError.__bases__}'
# Verify no extra fields (no custom __init__)
import inspect
assert '__init__' not in UIAnalyzerError.__dict__, 'UIAnalyzerError must not define __init__'
print('PASS: UIAnalyzerError is a plain Exception subclass with no extra fields')
"
```

**Expected output**: `PASS: UIAnalyzerError is a plain Exception subclass with no extra fields`

**Verification**: Output contains `PASS`.

---

### Step 11: Commit

**Action**: Stage and commit the new files from the worktree root.

```bash
cd /mnt/c/Users/Epkone/UXIQ/.claude/worktrees/project-bootstrap
git add ui-analyzer/
git commit -m "feat: bootstrap ui-analyzer package scaffold

Creates the package skeleton with pyproject.toml, runtime and dev
dependencies, UIAnalyzerError exception class, and ANTHROPIC_API_KEY
guard that raises at import time when the key is absent."
```

**Verification**: `git status` shows clean working tree. `git log --oneline -3` shows the new commit.

---

## Post-Implementation Checklist

- [ ] `ui-analyzer/pyproject.toml` exists and is valid
- [ ] `ui-analyzer/.env.example` exists with `ANTHROPIC_API_KEY=your_key_here`
- [ ] `ui-analyzer/ui_analyzer/__init__.py` exists
- [ ] `ui-analyzer/ui_analyzer/exceptions.py` exists
- [ ] `pip install -e .[dev]` exits 0 (Step 6)
- [ ] Import with `ANTHROPIC_API_KEY` unset raises `UIAnalyzerError` (Step 7)
- [ ] Import with `ANTHROPIC_API_KEY` set raises nothing (Step 8)
- [ ] No circular imports (Step 9)
- [ ] `UIAnalyzerError` is a plain `Exception` subclass with no extra fields (Step 10)
- [ ] `__init__.py` imports only `os` and `UIAnalyzerError` — no third-party libraries
- [ ] All files committed to worktree branch `worktree-project-bootstrap`

## Verification Approach

All verification is done via `python -c "..."` one-liners in a shell. No pytest test files are created by this spec (tests are in spec-09). After Step 6, all verification steps (7–10) can be run in any order. The implementing agent should run each step's verification command and confirm it produces the expected output before moving to the next step.

If `pip install -e .[dev]` fails in Step 6, stop and diagnose before continuing — subsequent steps require the package to be installed.

## Commit Message (draft)

```
feat: bootstrap ui-analyzer package scaffold

Creates the package skeleton with pyproject.toml, runtime and dev
dependencies, UIAnalyzerError exception class, and ANTHROPIC_API_KEY
guard that raises at import time when the key is absent.

Blocks all other specs — every downstream module depends on this
package structure and the UIAnalyzerError type.
```
