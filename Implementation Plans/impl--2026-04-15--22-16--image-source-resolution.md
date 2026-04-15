# Implementation Plan: Image Source Resolution & Preprocessing

## Header
- **Spec**: specs/applied/spec-02-image-source-resolution.md
- **Worktree**: `.claude/worktrees/` — N/A; the active worktree IS the working directory (`/mnt/c/Users/Epkone/UXIQ-spec-02` on branch `spec-02-image-source-resolution`)
- **Scope — files in play** (agent must not touch files not listed here):
  - `ui-analyzer/ui_analyzer/image_source.py` ← new file (create)
  - `ui-analyzer/tests/conftest.py` ← new file (create)
  - `ui-analyzer/tests/fixtures/dashboard_good.png` ← new fixture (create via Pillow)
  - `ui-analyzer/tests/fixtures/dashboard_bad.png` ← new fixture (create via Pillow)
  - `ui-analyzer/tests/fixtures/landing_page.png` ← new fixture (create via Pillow)
  - `ui-analyzer/tests/fixtures/form.png` ← new fixture (create via Pillow)
  - `ui-analyzer/tests/fixtures/not_a_ui.jpg` ← new fixture (create via Pillow)
  - `ui-analyzer/tests/test_image_source.py` ← new file (create)
- **Reading list** (read these in order before starting, nothing else):
  1. `ui-analyzer/ui_analyzer/exceptions.py`
  2. `ui-analyzer/ui_analyzer/__init__.py`
  3. `ui-analyzer/pyproject.toml`

## Environment assumptions verified

The following packages were confirmed installed in the active Python environment before writing this plan:

| Package | Version confirmed |
|---------|------------------|
| `pytest` | 9.0.3 |
| `pytest-asyncio` | 1.3.0 |
| `pytest-mock` | 3.15.1 |
| `pillow` | 12.2.0 |
| `playwright` | 1.58.0 |

`asyncio_mode = "auto"` is set in `pyproject.toml` under `[tool.pytest.ini_options]`. `testpaths = ["tests"]` is also set.

---

## Steps

### Step 1: Create `ui-analyzer/ui_analyzer/image_source.py`

**File**: `ui-analyzer/ui_analyzer/image_source.py`
**Action**: Create new file with the full module implementation.

**What it does**: Implements `resolve(image_source: str) -> ResolvedImage`. Detects URL vs file-path input, loads image bytes from either source (Playwright screenshot for URLs, direct file read for file paths), resizes any image whose longest edge exceeds 1568px, and returns a `ResolvedImage` dataclass with bytes and dimensions. Raises `UIAnalyzerError` on all hard failures.

**Full file content**:

```python
"""image_source.py — resolve a URL or absolute file path to image bytes.

Public interface:
    resolve(image_source: str) -> ResolvedImage

Raises UIAnalyzerError on hard failure. See docstring for details.
"""
from __future__ import annotations

import io
import os
import pathlib
from dataclasses import dataclass
from typing import Literal

from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from ui_analyzer.exceptions import UIAnalyzerError

MAX_EDGE = 1568
_ACCEPTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class ResolvedImage:
    bytes: bytes
    source_type: Literal["url", "file"]
    width_px: int
    height_px: int


@dataclass
class _ResizeResult:
    bytes: bytes
    width_px: int
    height_px: int


def resolve(image_source: str) -> ResolvedImage:
    """Resolve a URL or absolute file path to image bytes.

    Raises UIAnalyzerError on hard failure:
        - URL: HTTP 4xx/5xx, Playwright timeout (>30s), blank/spinner page
        - File: path not found, unsupported extension
    """
    if image_source.startswith("https://") or image_source.startswith("http://"):
        return _resolve_url(image_source)
    return _resolve_file(image_source)


def _resolve_url(url: str) -> ResolvedImage:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        try:
            response = page.goto(url, timeout=30_000, wait_until="networkidle")
        except PlaywrightTimeout:
            browser.close()
            raise UIAnalyzerError(
                "URL did not load within 30s. Provide a screenshot file path instead."
            )

        if response is not None and response.status >= 400:
            status = response.status
            browser.close()
            raise UIAnalyzerError(
                f"Could not load URL: HTTP {status}. Provide a screenshot file path instead."
            )

        body_text = page.evaluate("document.body.innerText")
        image_count = page.evaluate("document.images.length")
        if (not body_text or not body_text.strip()) and image_count == 0:
            browser.close()
            raise UIAnalyzerError(
                "Page rendered no visible content. Provide a screenshot file path instead."
            )

        screenshot_bytes = page.screenshot(full_page=False)
        browser.close()

    orig_width = 1280
    orig_height = 800
    resized = _resize_if_needed(screenshot_bytes, orig_width, orig_height)
    return ResolvedImage(
        bytes=resized.bytes,
        source_type="url",
        width_px=resized.width_px,
        height_px=resized.height_px,
    )


def _resolve_file(image_source: str) -> ResolvedImage:
    image_source = os.path.abspath(image_source)

    if not os.path.exists(image_source):
        raise UIAnalyzerError(f"File not found: {image_source}")

    ext = pathlib.Path(image_source).suffix.lower()
    if ext not in _ACCEPTED_EXTENSIONS:
        raise UIAnalyzerError(
            "Unsupported file type. Accepted: PNG, JPG, JPEG, WebP."
        )

    image_bytes = pathlib.Path(image_source).read_bytes()

    with Image.open(io.BytesIO(image_bytes)) as img:
        orig_width, orig_height = img.size

    resized = _resize_if_needed(image_bytes, orig_width, orig_height)
    return ResolvedImage(
        bytes=resized.bytes,
        source_type="file",
        width_px=resized.width_px,
        height_px=resized.height_px,
    )


def _resize_if_needed(image_bytes: bytes, orig_width: int, orig_height: int) -> _ResizeResult:
    if max(orig_width, orig_height) <= MAX_EDGE:
        return _ResizeResult(bytes=image_bytes, width_px=orig_width, height_px=orig_height)

    ratio = MAX_EDGE / max(orig_width, orig_height)
    new_w = int(orig_width * ratio)
    new_h = int(orig_height * ratio)

    with Image.open(io.BytesIO(image_bytes)) as img:
        fmt = img.format or "PNG"
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format=fmt)

    return _ResizeResult(bytes=buf.getvalue(), width_px=new_w, height_px=new_h)
```

**Verification**: File is importable (`python -c "from ui_analyzer.image_source import resolve, ResolvedImage"` exits 0). No syntax errors.

---

### Step 2: Create `ui-analyzer/tests/` directory structure

**Action**: Create directories `ui-analyzer/tests/` and `ui-analyzer/tests/fixtures/`. These do not exist yet.

```bash
mkdir -p ui-analyzer/tests/fixtures
touch ui-analyzer/tests/__init__.py
```

**Note**: `testpaths = ["tests"]` in `pyproject.toml` is relative to the project root (`ui-analyzer/`). Tests must be run from within `ui-analyzer/`.

**Verification**: Directories exist.

---

### Step 3: Create `ui-analyzer/tests/conftest.py`

**File**: `ui-analyzer/tests/conftest.py`
**Action**: Create new file.

**What it does**: Sets a fake `ANTHROPIC_API_KEY` before any `ui_analyzer` import so that the `__init__.py` guard does not raise during test collection. Registers the `integration` marker. Provides the `fixtures_dir` fixture.

**Full file content**:

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

**Verification**: `pytest --collect-only` (from `ui-analyzer/`) exits 0 without errors about unconfigured markers.

---

### Step 4: Create fixture images via Pillow

**File**: Python script run inline (do NOT commit the script; commit only the PNG/JPG outputs)
**Action**: Create 5 synthetic fixture images in `ui-analyzer/tests/fixtures/` using Pillow. These must be valid image files — not empty, not placeholder. Each must satisfy the content requirement described in Spec 09.

Run this Python snippet **from the `ui-analyzer/` directory** (or with absolute paths):

```python
import os
from PIL import Image, ImageDraw, ImageFont

fixtures_dir = "tests/fixtures"
os.makedirs(fixtures_dir, exist_ok=True)

# dashboard_good.png — dark text on light background, clear layout (200x200 PNG)
img = Image.new("RGB", (200, 200), color=(255, 255, 255))
draw = ImageDraw.Draw(img)
draw.rectangle([10, 10, 190, 40], fill=(30, 30, 30))
draw.text((20, 15), "Dashboard", fill=(255, 255, 255))
draw.rectangle([10, 50, 90, 90], fill=(70, 130, 180))
draw.text((15, 60), "Users", fill=(255, 255, 255))
draw.rectangle([100, 50, 190, 90], fill=(60, 179, 113))
draw.text((105, 60), "Revenue", fill=(255, 255, 255))
img.save(os.path.join(fixtures_dir, "dashboard_good.png"), format="PNG")

# dashboard_bad.png — light gray text on white, small elements (200x200 PNG)
img = Image.new("RGB", (200, 200), color=(255, 255, 255))
draw = ImageDraw.Draw(img)
draw.text((5, 5), "Dashboard", fill=(200, 200, 200))
draw.rectangle([5, 25, 45, 45], fill=(230, 230, 230))
draw.text((7, 30), "A", fill=(210, 210, 210))
draw.rectangle([50, 25, 90, 45], fill=(230, 230, 230))
draw.text((52, 30), "B", fill=(210, 210, 210))
img.save(os.path.join(fixtures_dir, "dashboard_bad.png"), format="PNG")

# landing_page.png — headline, CTA button, trust section (200x250 PNG)
img = Image.new("RGB", (200, 250), color=(245, 245, 255))
draw = ImageDraw.Draw(img)
draw.text((20, 20), "Welcome!", fill=(20, 20, 80))
draw.rectangle([50, 60, 150, 90], fill=(0, 120, 215))
draw.text((65, 68), "Get Started", fill=(255, 255, 255))
draw.text((30, 110), "Trusted by 1000+", fill=(80, 80, 80))
draw.text((50, 130), "customers", fill=(80, 80, 80))
img.save(os.path.join(fixtures_dir, "landing_page.png"), format="PNG")

# form.png — 3+ labeled inputs, at least one required (200x300 PNG)
img = Image.new("RGB", (200, 300), color=(255, 255, 255))
draw = ImageDraw.Draw(img)
draw.text((10, 10), "Contact Form", fill=(30, 30, 30))
for i, label in enumerate(["Name *", "Email *", "Phone", "Message *"]):
    y = 40 + i * 55
    draw.text((10, y), label, fill=(50, 50, 50))
    draw.rectangle([10, y + 16, 190, y + 36], outline=(150, 150, 150))
img.save(os.path.join(fixtures_dir, "form.png"), format="PNG")

# not_a_ui.jpg — landscape photograph (no UI elements), 200x150 JPEG
img = Image.new("RGB", (200, 150), color=(100, 150, 200))  # sky-like blue
draw = ImageDraw.Draw(img)
draw.rectangle([0, 100, 200, 150], fill=(34, 139, 34))  # ground
draw.ellipse([70, 10, 130, 70], fill=(255, 220, 50))     # sun
img.save(os.path.join(fixtures_dir, "not_a_ui.jpg"), format="JPEG")

print("All fixtures created.")
```

Run as: `cd ui-analyzer && python -c "<above script content>"` (or save to a temp file, run, then delete).

**Verification**: All 5 files exist and are non-zero size. `python -c "from PIL import Image; Image.open('tests/fixtures/dashboard_good.png').verify()"` exits 0 for each.

---

### Step 5: Create `ui-analyzer/tests/test_image_source.py`

**File**: `ui-analyzer/tests/test_image_source.py`
**Action**: Create new file with all unit tests (and one integration test) for `image_source.py`.

**Full file content**:

```python
"""Tests for ui_analyzer.image_source."""
import io
import os

import pytest
from PIL import Image
from unittest.mock import MagicMock, patch

from ui_analyzer.exceptions import UIAnalyzerError
from ui_analyzer.image_source import ResolvedImage, resolve

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REAL_KEY = os.getenv("ANTHROPIC_API_KEY", "")
skip_if_no_key = pytest.mark.skipif(
    _REAL_KEY in ("", "test-key-unit-tests"),
    reason="ANTHROPIC_API_KEY not set to a real key",
)


def _make_png_bytes(width: int = 100, height: int = 100) -> bytes:
    """Return in-memory PNG bytes for a solid-colour image."""
    img = Image.new("RGB", (width, height), color=(100, 149, 237))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# File mode — valid input
# ---------------------------------------------------------------------------


def test_image_source_file_valid(fixtures_dir):
    """Valid PNG path returns ResolvedImage with source_type='file' and correct dimensions."""
    path = os.path.join(fixtures_dir, "dashboard_good.png")
    result = resolve(path)

    assert isinstance(result, ResolvedImage)
    assert result.source_type == "file"
    assert len(result.bytes) > 0
    # dashboard_good.png is 200x200 (created in Step 4)
    assert result.width_px == 200
    assert result.height_px == 200


# ---------------------------------------------------------------------------
# File mode — missing file
# ---------------------------------------------------------------------------


def test_image_source_file_missing(tmp_path):
    """Non-existent path raises UIAnalyzerError with correct message."""
    missing = str(tmp_path / "does_not_exist.png")
    with pytest.raises(UIAnalyzerError) as exc_info:
        resolve(missing)
    assert "File not found:" in str(exc_info.value)
    assert "does_not_exist.png" in str(exc_info.value)


# ---------------------------------------------------------------------------
# File mode — bad extension
# ---------------------------------------------------------------------------


def test_image_source_file_bad_extension(tmp_path):
    """Unsupported extension raises UIAnalyzerError with exact catalogue message."""
    pdf_file = tmp_path / "document.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake content")

    with pytest.raises(UIAnalyzerError) as exc_info:
        resolve(str(pdf_file))
    assert str(exc_info.value) == "Unsupported file type. Accepted: PNG, JPG, JPEG, WebP."


# ---------------------------------------------------------------------------
# Resize logic — image larger than MAX_EDGE
# ---------------------------------------------------------------------------


def test_image_resize_large(tmp_path):
    """Image with longest edge > 1568px is resized; original bytes not mutated."""
    original_bytes = _make_png_bytes(width=2000, height=1000)
    large_file = tmp_path / "large.png"
    large_file.write_bytes(original_bytes)

    result = resolve(str(large_file))

    # Longest edge must be <= 1568
    assert max(result.width_px, result.height_px) <= 1568
    # Bytes should differ from original (resized)
    assert result.bytes != original_bytes
    # Original file unchanged
    assert large_file.read_bytes() == original_bytes


# ---------------------------------------------------------------------------
# Resize logic — image smaller than or equal to MAX_EDGE
# ---------------------------------------------------------------------------


def test_image_resize_small(tmp_path):
    """Image with longest edge <= 1568px is returned unchanged."""
    original_bytes = _make_png_bytes(width=800, height=600)
    small_file = tmp_path / "small.png"
    small_file.write_bytes(original_bytes)

    result = resolve(str(small_file))

    # Dimensions unchanged
    assert result.width_px == 800
    assert result.height_px == 600
    # Bytes identical to input
    assert result.bytes == original_bytes


# ---------------------------------------------------------------------------
# URL mode — error scenarios (Playwright mocked)
# ---------------------------------------------------------------------------


def _make_mock_pw_context(
    *,
    response_status: int = 200,
    raise_timeout: bool = False,
    body_text: str = "Hello world",
    image_count: int = 0,
    screenshot_bytes: bytes = b"\x89PNG\r\n",
):
    """Build a nested mock that replaces sync_playwright()."""
    mock_response = MagicMock()
    mock_response.status = response_status

    mock_page = MagicMock()
    if raise_timeout:
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        mock_page.goto.side_effect = PlaywrightTimeout("Timeout exceeded")
    else:
        mock_page.goto.return_value = mock_response

    mock_page.evaluate.side_effect = lambda expr: (
        body_text if "innerText" in expr else image_count
    )
    mock_page.screenshot.return_value = screenshot_bytes

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw_instance = MagicMock()
    mock_pw_instance.chromium.launch.return_value = mock_browser

    mock_pw_cm = MagicMock()
    mock_pw_cm.__enter__ = MagicMock(return_value=mock_pw_instance)
    mock_pw_cm.__exit__ = MagicMock(return_value=False)

    return mock_pw_cm


def test_url_mode_timeout(mocker):
    """Playwright TimeoutError raises UIAnalyzerError with exact catalogue message."""
    mock_cm = _make_mock_pw_context(raise_timeout=True)
    mocker.patch("ui_analyzer.image_source.sync_playwright", return_value=mock_cm)

    with pytest.raises(UIAnalyzerError) as exc_info:
        resolve("https://example.com")
    assert str(exc_info.value) == "URL did not load within 30s. Provide a screenshot file path instead."


def test_url_mode_http_404(mocker):
    """HTTP 404 response raises UIAnalyzerError with exact catalogue message."""
    mock_cm = _make_mock_pw_context(response_status=404)
    mocker.patch("ui_analyzer.image_source.sync_playwright", return_value=mock_cm)

    with pytest.raises(UIAnalyzerError) as exc_info:
        resolve("https://example.com")
    assert str(exc_info.value) == "Could not load URL: HTTP 404. Provide a screenshot file path instead."


def test_url_mode_http_500(mocker):
    """HTTP 500 response raises UIAnalyzerError with status interpolated."""
    mock_cm = _make_mock_pw_context(response_status=500)
    mocker.patch("ui_analyzer.image_source.sync_playwright", return_value=mock_cm)

    with pytest.raises(UIAnalyzerError) as exc_info:
        resolve("https://example.com")
    assert str(exc_info.value) == "Could not load URL: HTTP 500. Provide a screenshot file path instead."


def test_url_mode_blank_page(mocker):
    """Blank page (no text, no images) raises UIAnalyzerError with exact catalogue message."""
    mock_cm = _make_mock_pw_context(body_text="   ", image_count=0)
    mocker.patch("ui_analyzer.image_source.sync_playwright", return_value=mock_cm)

    with pytest.raises(UIAnalyzerError) as exc_info:
        resolve("https://example.com")
    assert str(exc_info.value) == "Page rendered no visible content. Provide a screenshot file path instead."


def test_url_mode_blank_page_with_images_does_not_raise(mocker):
    """Blank body text but images present — should NOT raise (page has content)."""
    screenshot_bytes = _make_png_bytes(1280, 800)
    mock_cm = _make_mock_pw_context(body_text="  ", image_count=3, screenshot_bytes=screenshot_bytes)
    mocker.patch("ui_analyzer.image_source.sync_playwright", return_value=mock_cm)

    result = resolve("https://example.com")
    assert result.source_type == "url"
    assert result.width_px == 1280
    assert result.height_px == 800


def test_url_mode_success(mocker):
    """Successful URL capture returns ResolvedImage with source_type='url', w=1280, h=800."""
    screenshot_bytes = _make_png_bytes(1280, 800)
    mock_cm = _make_mock_pw_context(
        response_status=200,
        body_text="Hello world",
        image_count=2,
        screenshot_bytes=screenshot_bytes,
    )
    mocker.patch("ui_analyzer.image_source.sync_playwright", return_value=mock_cm)

    result = resolve("https://example.com")
    assert result.source_type == "url"
    assert len(result.bytes) > 0
    assert result.width_px == 1280
    assert result.height_px == 800


# ---------------------------------------------------------------------------
# Integration — real Playwright (skipped without real API key / environment)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@skip_if_no_key
def test_image_source_url_integration():
    """Integration: real Playwright captures https://example.com."""
    result = resolve("https://example.com")

    assert isinstance(result, ResolvedImage)
    assert result.source_type == "url"
    assert len(result.bytes) > 0
    assert result.width_px == 1280
    assert result.height_px == 800
```

**Verification**: `pytest tests/test_image_source.py -m "not integration" -v` (from `ui-analyzer/`) exits 0. All unit tests pass. No Playwright browser is launched.

---

## Post-Implementation Checklist

- [ ] `ui-analyzer/ui_analyzer/image_source.py` exists and is importable without error
- [ ] `resolve` and `ResolvedImage` are importable from `ui_analyzer.image_source`
- [ ] `ui-analyzer/tests/conftest.py` exists
- [ ] All 5 fixture images exist in `ui-analyzer/tests/fixtures/` and are valid (non-zero size)
- [ ] `pytest tests/ -m "not integration"` from `ui-analyzer/` exits 0 with all unit tests passing
- [ ] No test launches a real Playwright browser (confirmed by absence of Chromium process in `test_url_mode_*` tests)
- [ ] `test_image_source_file_valid` passes with correct dimensions (200×200 for `dashboard_good.png`)
- [ ] `test_image_source_file_missing` raises `UIAnalyzerError` with `"File not found:"` in message
- [ ] `test_image_source_file_bad_extension` raises with exact message `"Unsupported file type. Accepted: PNG, JPG, JPEG, WebP."`
- [ ] `test_image_resize_large` passes: resized image has longest edge ≤ 1568px and bytes differ from original
- [ ] `test_image_resize_small` passes: small image returned unchanged
- [ ] URL error tests (`test_url_mode_timeout`, `test_url_mode_http_404`, `test_url_mode_http_500`, `test_url_mode_blank_page`) all pass with exact catalogue error messages
- [ ] `test_url_mode_success` passes: returns `source_type="url"`, `width_px=1280`, `height_px=800`
- [ ] Original file not modified by resize (verified by `test_image_resize_large`)
- [ ] `resolve()` is synchronous (no `async def`, no `asyncio`)
- [ ] No import of `axe_runner` in `image_source.py`
- [ ] No logging calls inside `resolve()` or any private function

## Verification Approach

All verification is done via pytest, run from the `ui-analyzer/` directory:

```bash
cd ui-analyzer
pytest tests/test_image_source.py -m "not integration" -v
```

For import sanity check:
```bash
cd ui-analyzer
python -c "from ui_analyzer.image_source import resolve, ResolvedImage; print('OK')"
```

Note: `ANTHROPIC_API_KEY` does not need to be set for unit tests — `conftest.py` sets the fake sentinel automatically.

## Commit Message (draft)

```
feat: implement image_source.py with URL capture and file loading

Adds ui_analyzer/image_source.py (resolve(), ResolvedImage), which:
- Detects URL vs file-path input
- Captures Playwright screenshots for URLs (new browser per call, sync API)
- Validates file existence and extension for file-path inputs
- Resizes images with longest edge > 1568px using Pillow LANCZOS
- Raises UIAnalyzerError on all hard failures with exact catalogue messages

Also adds tests/conftest.py, synthetic fixture images (5 files), and
tests/test_image_source.py covering all file-mode paths, resize logic,
and URL error scenarios via mocked Playwright.
```
