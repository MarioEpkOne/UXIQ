# Bug: Full URL Logged in Warning Messages (Potential Token/Credential Leakage)

**Date**: 2026-04-16
**Status**: Open
**Severity**: LOW

---

## Symptom

When Playwright times out loading a page, the full URL — including query string and fragment — is written to the warning log. URLs frequently contain sensitive values in query parameters (API keys, session tokens, OAuth codes). These end up in log files or log aggregation services.

---

## Root Cause

Two warning log calls embed the full user-supplied URL:

**`axe_runner.py:109`:**
```python
logger.warning("axe-core: page load timed out for %s", url)
```

**`dom_extractor.py:73`:**
```python
logger.warning("dom_extractor: page load timed out for %s", url)
```

The `url` argument is the raw string passed in by the caller, which may be:
```
https://app.example.com/dashboard?token=eyJhbGciOiJIUzI1NiJ9...&session=abc123
```

---

## Exploit Scenario

A user runs `uxiq analyze` against an authenticated app URL (common for SaaS dashboards that embed short-lived tokens in the URL). The page times out (e.g. slow network, auth redirect). The full URL including the token is written to the Python warning log. If logs are shipped to a log aggregation service (Datadog, Splunk, CloudWatch), the token is now accessible to anyone with log read access.

---

## Steps to Reproduce

1. Run `uxiq analyze "https://example.com/app?api_key=secret123" --app-type web_dashboard` against a URL that will time out.
2. Observe the log output — the full URL including `api_key=secret123` appears in the warning message.

---

## Expected Behaviour

Log messages should include only the scheme and hostname (e.g. `https://example.com`), stripping the path, query string, and fragment.

---

## Recommended Fix

Use `urllib.parse.urlparse` to extract only the safe portion before logging:

```python
from urllib.parse import urlparse

def _safe_log_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"
```

Apply in both locations:

**`axe_runner.py:109`:**
```python
logger.warning("axe-core: page load timed out for %s", _safe_log_url(url))
```

**`dom_extractor.py:73`:**
```python
logger.warning("dom_extractor: page load timed out for %s", _safe_log_url(url))
```

The helper can live in a shared `ui_analyzer/utils.py` module or be inlined in each file.

---

## Affected Files

- `ui-analyzer/ui_analyzer/axe_runner.py` — line 109
- `ui-analyzer/ui_analyzer/dom_extractor.py` — line 73
