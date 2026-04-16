"""page_capture.py — unified Playwright capture: screenshot + DOM + axe in one session.

Public interface:
    capture_page(url: str, *, max_elements: int = 300,
                 goto_timeout_ms: int = 30_000,
                 step_timeout_ms: int = 10_000) -> PageCapture

Raises UIAnalyzerError with an attribution prefix identifying which step failed
(goto, fonts, screenshot, dom, axe_inject, axe_run). All-or-nothing: never
returns a partial PageCapture, never falls through to soft-failure mode.

Browser lifecycle: one Playwright Chromium browser per capture_page() call.
Viewport is fixed at 1280x800 for all URL inputs.
"""
from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from ui_analyzer.axe_runner import AxeCoreResult, _parse_axe_result
from ui_analyzer.dom_extractor import DomElement
from ui_analyzer.exceptions import UIAnalyzerError
from ui_analyzer.utils import safe_log_url

logger = logging.getLogger(__name__)

VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 800
SETTLE_MS = 300
FONTS_READY_TIMEOUT_MS = 5_000

_AXE_JS = (pathlib.Path(__file__).parent / "vendor" / "axe.min.js").read_text(encoding="utf-8")

# JS run in the page context to extract visible interactive elements + headings + images.
# Emits viewport-pixel integer bounding boxes (x, y clamped to viewport; w, h unclamped).
_DOM_JS = r"""
(maxElements) => {
  const VW = 1280, VH = 800;
  const SEL = 'button, a, input, select, textarea, h1, h2, h3, h4, h5, h6, img, [role]';
  const isVisible = (r, cs) => (
    r.right > 0 && r.left < VW && r.bottom > 0 && r.top < VH &&
    r.width > 0 && r.height > 0 &&
    cs.display !== 'none' &&
    cs.visibility !== 'hidden' &&
    parseFloat(cs.opacity) > 0
  );
  const out = [];
  for (const el of document.querySelectorAll(SEL)) {
    if (out.length >= maxElements) break;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (!isVisible(r, cs)) continue;
    out.push({
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      text: (el.innerText || el.value || '').trim().slice(0, 120),
      aria_label: el.getAttribute('aria-label') || '',
      placeholder: el.getAttribute('placeholder') || '',
      input_type: el.tagName.toLowerCase() === 'input' ? (el.type || '') : '',
      alt: el.tagName.toLowerCase() === 'img' ? (el.getAttribute('alt') || '') : '',
      x: Math.max(0, Math.min(VW, Math.round(r.left))),
      y: Math.max(0, Math.min(VH, Math.round(r.top))),
      w: Math.round(r.width),
      h: Math.round(r.height),
    });
  }
  return out;
}
"""

# Wrapped axe run: Promise.race against a 10 s timeout, same tag set as axe_runner.run_axe.
_AXE_RUN_JS = r"""
async () => {
  return await Promise.race([
    axe.run(document, {
      runOnly: {
        type: 'tag',
        values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']
      }
    }),
    new Promise((_, reject) => setTimeout(
      () => reject(new Error('axe-core timed out')),
      10000
    ))
  ]);
}
"""


@dataclass
class PageCapture:
    """Everything captured from one page.goto. All fields populated on success."""
    image_bytes: bytes
    image_width_px: int        # always VIEWPORT_WIDTH
    image_height_px: int       # always VIEWPORT_HEIGHT
    dom_elements: list[DomElement]
    axe_result: AxeCoreResult


def capture_page(
    url: str,
    *,
    max_elements: int = 300,
    goto_timeout_ms: int = 30_000,
    step_timeout_ms: int = 10_000,
) -> PageCapture:
    """Run the full unified capture against `url`.

    Returns PageCapture on success. Raises UIAnalyzerError with an
    attribution prefix identifying which step failed. Never returns None,
    never returns a partial capture.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            context = browser.new_context(
                viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
            )
            page = context.new_page()

            # --- 1. goto ---
            try:
                response = page.goto(
                    url, timeout=goto_timeout_ms, wait_until="networkidle"
                )
            except PlaywrightTimeout as exc:
                raise UIAnalyzerError(
                    f"capture failed at goto: timed out after {goto_timeout_ms/1000:.0f}s"
                ) from exc
            except PlaywrightError as exc:
                raise UIAnalyzerError(f"capture failed at goto: {exc}") from exc

            if response is not None and response.status >= 400:
                raise UIAnalyzerError(
                    f"capture failed at goto: HTTP {response.status}"
                )

            # --- 2. fonts.ready (soft — warn on timeout, continue) ---
            try:
                page.evaluate(
                    "() => Promise.race(["
                    "  document.fonts.ready,"
                    f"  new Promise((_, r) => setTimeout(() => r(new Error('fonts timeout')), {FONTS_READY_TIMEOUT_MS}))"
                    "])"
                )
            except Exception as exc:
                logger.warning(
                    "capture: document.fonts.ready did not resolve within %d ms for %s: %s",
                    FONTS_READY_TIMEOUT_MS, safe_log_url(url), exc,
                )

            # --- 3. settle ---
            page.wait_for_timeout(SETTLE_MS)

            # --- 4. screenshot ---
            try:
                image_bytes = page.screenshot(
                    full_page=False, timeout=step_timeout_ms
                )
            except Exception as exc:
                raise UIAnalyzerError(f"capture failed at screenshot: {exc}") from exc

            # --- 5. DOM extract ---
            try:
                raw_elements = page.evaluate(_DOM_JS, max_elements)
            except Exception as exc:
                raise UIAnalyzerError(f"capture failed at dom: {exc}") from exc

            dom_elements = [
                DomElement(
                    tag=item.get("tag", ""),
                    role=item.get("role", ""),
                    text=item.get("text", ""),
                    aria_label=item.get("aria_label", ""),
                    placeholder=item.get("placeholder", ""),
                    input_type=item.get("input_type", ""),
                    alt=item.get("alt", ""),
                    x=int(item.get("x", 0)),
                    y=int(item.get("y", 0)),
                    w=int(item.get("w", 0)),
                    h=int(item.get("h", 0)),
                )
                for item in (raw_elements or [])
            ]

            # --- 6. axe inject ---
            try:
                page.add_script_tag(content=_AXE_JS)
            except Exception as exc:
                raise UIAnalyzerError(f"capture failed at axe_inject: {exc}") from exc

            # --- 7. axe run ---
            try:
                raw_axe = page.evaluate(_AXE_RUN_JS)
            except Exception as exc:
                raise UIAnalyzerError(f"capture failed at axe_run: {exc}") from exc

            axe_result = _parse_axe_result(raw_axe)

            return PageCapture(
                image_bytes=image_bytes,
                image_width_px=VIEWPORT_WIDTH,
                image_height_px=VIEWPORT_HEIGHT,
                dom_elements=dom_elements,
                axe_result=axe_result,
            )
        finally:
            browser.close()
