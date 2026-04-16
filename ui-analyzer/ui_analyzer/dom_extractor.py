"""dom_extractor.py — Extract interactive DOM elements from a live page via Playwright.

Public interface:
    extract_dom(url: str, max_elements: int = 300) -> DomElements | DomFailure

Never raises. DomFailure is returned on any Playwright error.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

_JS_SELECTOR = """
(maxElements) => {
    return Array.from(document.querySelectorAll(
        'button, a, input, select, textarea, [role]'
    )).slice(0, maxElements).map(el => ({
        tag: el.tagName.toLowerCase(),
        role: el.getAttribute('role') || '',
        text: (el.innerText || el.value || '').trim().slice(0, 120),
        aria_label: el.getAttribute('aria-label') || '',
        placeholder: el.getAttribute('placeholder') || '',
        input_type: el.tagName.toLowerCase() === 'input' ? (el.type || '') : ''
    }));
}
"""


@dataclass
class DomElement:
    tag: str          # e.g. "button", "a", "input"
    role: str         # ARIA role (explicit or implicit) — empty string if none
    text: str         # visible text content or value (truncated at 120 chars)
    aria_label: str   # aria-label attribute — empty string if absent
    placeholder: str  # placeholder attribute (inputs) — empty string if absent
    input_type: str   # type attribute (inputs) — empty string if not an input


@dataclass
class DomElements:
    elements: list[DomElement] = field(default_factory=list)


@dataclass
class DomFailure:
    reason: str


def extract_dom(url: str, max_elements: int = 300) -> DomElements | DomFailure:
    """Extract interactive elements from the live page at url.

    Opens a fresh Playwright Chromium session (separate from image_source and
    axe_runner sessions). Loads the page to networkidle, evaluates the JS
    selector, then closes the browser.

    Returns DomFailure on any Playwright error, timeout, or JS evaluation error.
    Never raises.
    """
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            try:
                page.goto(url, timeout=30_000, wait_until="networkidle")
            except PlaywrightTimeout:
                logger.warning("dom_extractor: page load timed out for %s", url)
                browser.close()
                return DomFailure(reason="Playwright timed out after 30s")

            try:
                raw = page.evaluate(_JS_SELECTOR, max_elements)
            except Exception as exc:
                logger.warning("dom_extractor: JS evaluation failed: %s", exc)
                browser.close()
                return DomFailure(reason=f"JS evaluation failed: {exc}")

            browser.close()

        elements = [
            DomElement(
                tag=item.get("tag", ""),
                role=item.get("role", ""),
                text=item.get("text", ""),
                aria_label=item.get("aria_label", ""),
                placeholder=item.get("placeholder", ""),
                input_type=item.get("input_type", ""),
            )
            for item in (raw or [])
        ]
        return DomElements(elements=elements)

    except Exception as exc:
        logger.warning("dom_extractor: unexpected error: %s", exc)
        return DomFailure(reason=f"unexpected error: {exc}")
