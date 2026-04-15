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
