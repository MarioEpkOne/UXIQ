# Spec 02 — Image Source Resolution & Preprocessing

**Parent spec:** spec--2026-04-15--15-30--ui-screenshot-analyzer.md  
**Status:** Ready for implementation  
**Depends on:** Spec 01 (UIAnalyzerError, package scaffold)  
**Blocks:** Spec 03 (axe-core shares Playwright), Spec 08 (handler calls resolve())

---

## Goal

Implement `ui_analyzer/image_source.py`. This module is responsible for:
1. Detecting whether the input is a URL or a file path
2. Loading image bytes from either source
3. Capturing a screenshot via Playwright when the input is a URL (screenshot only — axe-core is NOT run here)
4. Validating file type and existence for file-path inputs
5. Resizing any image whose longest edge exceeds 1568px using Pillow before returning

Returns: `(image_bytes: bytes, source_type: Literal["url", "file"])`

---

## Scope

Files created by this spec:

```
ui_analyzer/
└── image_source.py
```

---

## Public Interface

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class ResolvedImage:
    bytes: bytes
    source_type: Literal["url", "file"]
    # Populated from Playwright capture (URL mode) or image metadata (file mode)
    width_px: int
    height_px: int

def resolve(image_source: str) -> ResolvedImage:
    """Resolve a URL or absolute file path to image bytes.

    Raises UIAnalyzerError on hard failure:
        - URL: HTTP 4xx/5xx, Playwright timeout (>30s), blank/spinner page
        - File: path not found, unsupported extension
    """
```

`resolve()` is the only public symbol. Everything else is private.

---

## URL Mode

Detection: `image_source.startswith("https://") or image_source.startswith("http://")`

### Playwright setup

```python
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    # ... capture
    browser.close()
```

**Browser lifecycle rule:** A new browser instance is launched and closed for each `resolve()` call. No shared browser state. This rule is repeated in Spec 08 because it is a hard invariant.

### Capture sequence

1. `page.goto(url, timeout=30_000, wait_until="networkidle")` — waits for network to settle
2. If `TimeoutError`: raise `UIAnalyzerError("URL did not load within 30s. Provide a screenshot file path instead.")`
3. Check HTTP status: if response status is 4xx or 5xx: raise `UIAnalyzerError(f"Could not load URL: HTTP {status}. Provide a screenshot file path instead.")`
4. Check for blank/spinner page: call `page.evaluate("document.body.innerText")`. If result is empty string or contains only whitespace, and `page.evaluate("document.images.length") == 0`: raise `UIAnalyzerError("Page rendered no visible content. Provide a screenshot file path instead.")`
5. `screenshot_bytes = page.screenshot(full_page=False)` — viewport screenshot, not full page
6. `width_px = 1280`, `height_px = 800` (from viewport; read back from Playwright if API supports it)

### axe-core is NOT run here

This module captures the screenshot only. axe-core execution is the responsibility of `axe_runner.py` (Spec 03). The handler (Spec 08) calls both independently.

---

## File Mode

Detection: anything that does not start with `http://` or `https://`

### Validation

1. Normalize to absolute path: `image_source = os.path.abspath(image_source)` — do this before all other checks so that the error messages and `ResolvedImage` always contain the resolved absolute path.
2. Check existence: if `not os.path.exists(image_source)`: raise `UIAnalyzerError(f"File not found: {image_source}")`
2. Check extension: extract suffix with `pathlib.Path(image_source).suffix.lower()`. Accepted: `.png`, `.jpg`, `.jpeg`, `.webp`. Anything else: raise `UIAnalyzerError("Unsupported file type. Accepted: PNG, JPG, JPEG, WebP.")`
3. Load bytes: `image_bytes = pathlib.Path(image_source).read_bytes()`

### Width/height extraction

Use Pillow to read dimensions without decoding the full image:

```python
from PIL import Image
import io

with Image.open(io.BytesIO(image_bytes)) as img:
    width_px, height_px = img.size
```

---

## Resize Logic (applies to both modes)

After bytes are loaded and before returning, call `_resize_if_needed()` which returns both the (possibly new) bytes **and** the post-resize dimensions. The `ResolvedImage` must always reflect the actual dimensions of the bytes it contains.

```python
from dataclasses import dataclass

MAX_EDGE = 1568

@dataclass
class _ResizeResult:
    bytes: bytes
    width_px: int
    height_px: int

def _resize_if_needed(image_bytes: bytes, orig_width: int, orig_height: int) -> _ResizeResult:
    if max(orig_width, orig_height) <= MAX_EDGE:
        return _ResizeResult(bytes=image_bytes, width_px=orig_width, height_px=orig_height)
    ratio = MAX_EDGE / max(orig_width, orig_height)
    new_w = int(orig_width * ratio)
    new_h = int(orig_height * ratio)
    with Image.open(io.BytesIO(image_bytes)) as img:
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        fmt = img.format or "PNG"
        resized.save(buf, format=fmt)
    return _ResizeResult(bytes=buf.getvalue(), width_px=new_w, height_px=new_h)
```

The caller uses the returned `width_px`/`height_px` to populate `ResolvedImage` — not the pre-resize values.

**Original file is never modified.** Resize operates on in-memory bytes only.

---

## Error Message Catalogue

These exact messages are referenced in Spec 09 (tests) and must not be changed:

| Scenario | UIAnalyzerError message |
|----------|------------------------|
| HTTP 404 | `"Could not load URL: HTTP 404. Provide a screenshot file path instead."` |
| HTTP 5xx | `"Could not load URL: HTTP 500. Provide a screenshot file path instead."` (status interpolated) |
| Playwright timeout | `"URL did not load within 30s. Provide a screenshot file path instead."` |
| Blank page | `"Page rendered no visible content. Provide a screenshot file path instead."` |
| File not found | `"File not found: {path}"` |
| Bad extension | `"Unsupported file type. Accepted: PNG, JPG, JPEG, WebP."` |

---

## Constraints

- `resolve()` must be synchronous. Playwright sync API is used; no asyncio.
- Do not import `axe_runner` from this module. They are siblings, not a hierarchy.
- Do not log inside `resolve()`. Callers (handler.py) own logging.
- Width/height from Playwright viewport are always 1280×800 for URL mode in v1. They are included in `ResolvedImage` so Spec 05 can inject them into the `<analysis_request>` ContextEvent.

---

## Success Criteria

Covered by tests in Spec 09. Key assertions:

- [ ] URL input → returns `ResolvedImage` with `source_type="url"`, non-empty bytes, width=1280, height=800
- [ ] Valid file path → returns `ResolvedImage` with `source_type="file"`, correct dimensions
- [ ] Missing file raises `UIAnalyzerError` with exact message
- [ ] Unsupported extension raises `UIAnalyzerError` with exact message
- [ ] Image >1568px longest side is resized (bytes differ, no temp file created)
- [ ] Image ≤1568px is returned unchanged
