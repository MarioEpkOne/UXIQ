# Bug: axe-core Loaded from External CDN Without Integrity Check

**Date**: 2026-04-16
**Status**: Open
**Severity**: LOW

---

## Symptom

axe-core is injected into the Playwright browser directly from an external CDN URL without any Subresource Integrity (SRI) verification. If the CDN file is tampered with or the CDN itself is compromised, arbitrary JavaScript executes in the browser context with full DOM access to the target page being audited.

---

## Root Cause

`axe_runner.py:21–23`:

```python
AXE_CDN_URL = (
    "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js"
)
```

`axe_runner.py:116`:

```python
page.add_script_tag(url=AXE_CDN_URL)
```

Playwright fetches the script at runtime over HTTPS and executes it in the page context. There is no hash verification — the content is trusted implicitly because the URL uses HTTPS. This is insufficient: the CDN provider, a CDN cache node, or a network-level attacker with a valid certificate could serve a modified file.

---

## Exploit Scenario

A supply-chain attacker compromises the `cdnjs.cloudflare.com` CDN for `axe-core/4.9.1/axe.min.js` and replaces it with a file that exfiltrates `document.cookie` and `localStorage` from the target page before running the real axe checks. The UI audit proceeds normally, masking the attack.

---

## Steps to Reproduce

This is a theoretical supply-chain risk that cannot be easily reproduced without controlling the CDN. The absence of a hash check can be verified by inspecting `axe_runner.py:116` — `add_script_tag` is called with only `url=`, not with a `content=` pinned string or any hash comparison.

---

## Expected Behaviour

The axe-core script should be loaded from a pinned local source — either bundled as a Python package dependency or read from disk — so its content is known and immutable at audit time.

---

## Recommended Fix

**Option A (preferred) — bundle axe-core locally:**

Install `axe-core` as a Node.js dev dependency or vendor the JS file into the package:

```
ui_analyzer/
  vendor/
    axe.min.js   # pinned copy of axe-core 4.9.1
```

Then in `axe_runner.py`, inject from disk:

```python
import pathlib

_AXE_JS = (pathlib.Path(__file__).parent / "vendor" / "axe.min.js").read_text()

# Instead of:
# page.add_script_tag(url=AXE_CDN_URL)
# Use:
page.add_script_tag(content=_AXE_JS)
```

**Option B — fetch with hash verification:**

```python
import hashlib, urllib.request

AXE_EXPECTED_SHA256 = "<sha256-of-axe-core-4.9.1.min.js>"

script_content = urllib.request.urlopen(AXE_CDN_URL).read()
actual_hash = hashlib.sha256(script_content).hexdigest()
if actual_hash != AXE_EXPECTED_SHA256:
    raise RuntimeError("axe-core integrity check failed")
page.add_script_tag(content=script_content.decode())
```

---

## Affected Files

- `ui-analyzer/ui_analyzer/axe_runner.py` — lines 21–23 (CDN URL), line 116 (`add_script_tag`)
