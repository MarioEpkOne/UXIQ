# Bug: Hosted Image URL Bypasses axe-core and DOM Extraction

**Date**: 2026-04-16
**Status**: Open

---

## Symptom

When a hosted screenshot URL (e.g. `https://imglink.cc/cdn/JAKLPM0RN6.png`) is passed as `image_source`, the report header claims "Tier 1 mode: Authoritative (axe-core)" but all Tier 1 findings are marked "ESTIMATED — verify manually".

## Root Cause

`handler.py` passes `req.image_source` directly to both `run_axe()` and `extract_dom()`. When the URL points to a hosted image file rather than a live webpage, Playwright navigates to a browser image-viewer page containing only a single `<img>` tag. axe-core runs without error (so `AxeCoreResult` is returned, not `AxeFailure`) but finds no interactive elements. The DOM extractor returns an empty elements list. Claude receives no real accessibility or DOM data and falls back to visual estimation for all findings — while the report falsely claims authoritative mode.

## Fix Options

1. Detect image-file URLs (by extension or `Content-Type` header) before calling axe/DOM and return `AxeFailure` / `DomFailure` with reason `"URL points to an image file, not a webpage"` so estimated mode is signalled honestly.
2. Accept an optional separate `page_url` parameter used exclusively for axe-core and DOM extraction, while `image_source` is used only for the screenshot.
3. Document the limitation in the README and CLI help so users know to pass the live page URL, not a screenshot URL, for authoritative results.
