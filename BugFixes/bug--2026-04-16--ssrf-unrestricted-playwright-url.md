# Bug: SSRF — Playwright Fetches Arbitrary Internal URLs Without Restriction

**Date**: 2026-04-16
**Status**: Open
**Severity**: MEDIUM (CRITICAL in cloud-hosted deployments)

---

## Symptom

The URL validator in `handler.py` only checks that the `image_source` starts with `http://` or `https://`. It does not restrict the destination host or IP. Playwright will faithfully fetch any URL — including internal services, loopback addresses, and cloud instance metadata endpoints — and embed the resulting screenshot in the Claude API call.

---

## Root Cause

`handler.py:53–55` (the `AnalyzeRequest` validator):

```python
def validate_url(cls, v: str) -> str:
    if not (v.startswith("http://") or v.startswith("https://")):
        raise ValueError("image_source must be a URL (http:// or https://)")
    return v
```

This is the only gate before Playwright is invoked in `image_source.py:_resolve_url()`, `axe_runner.py:run_axe()`, and `dom_extractor.py:extract_dom()`. All three call `page.goto(url, ...)` with the user-supplied URL, which Playwright executes without any IP-level filtering.

---

## Exploit Scenarios

**Scenario 1 — AWS/GCP/Azure instance metadata (CRITICAL in cloud):**
```
uxiq analyze http://169.254.169.254/latest/meta-data/iam/security-credentials/ --app-type web_dashboard
```
Playwright loads the IMDS endpoint, renders the plaintext credentials response, and takes a screenshot. The screenshot is base64-encoded and sent to Claude. The content is also written to a `runs/` debug Markdown file.

**Scenario 2 — Internal service probing:**
```
uxiq analyze http://localhost:8080/admin --app-type web_dashboard
```
Internal admin panels, databases with web UIs, or other services bound to loopback are accessible.

**Scenario 3 — Private network scanning:**
```
uxiq analyze http://10.0.0.1/ --app-type web_dashboard
```
Devices on the same private subnet as the server are reachable.

---

## Steps to Reproduce

1. In an AWS/GCP/Azure environment: `uxiq analyze http://169.254.169.254/ --app-type forms`
2. Observe Playwright successfully loading and screenshotting the metadata page.
3. Observe the screenshot base64 in the Claude API call and the rendered content in `runs/`.

---

## Expected Behaviour

Before passing any URL to Playwright, the hostname should be resolved and the resulting IP address validated against a blocklist:
- Loopback: `127.0.0.0/8`
- Private: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
- Link-local (IMDS): `169.254.0.0/16`
- IPv6 loopback/link-local: `::1`, `fe80::/10`

---

## Recommended Fix

Add a hostname resolution and IP blocklist check in `handler.py` before `AnalyzeRequest` is processed (or as an additional validator):

```python
import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
]

def _is_ssrf_safe(url: str) -> bool:
    hostname = urlparse(url).hostname
    if not hostname:
        return False
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(hostname))
    except (socket.gaierror, ValueError):
        return False
    return not any(ip in net for net in _BLOCKED_NETWORKS)
```

Raise `UIAnalyzerError` (or `pydantic.ValidationError`) if the check fails.

---

## Affected Files

- `ui-analyzer/ui_analyzer/handler.py` — lines 53–55 (validator), lines 102–110 (Playwright calls)
- `ui-analyzer/ui_analyzer/image_source.py` — line 59 (`page.goto`)
- `ui-analyzer/ui_analyzer/axe_runner.py` — line 108 (`page.goto`)
- `ui-analyzer/ui_analyzer/dom_extractor.py` — line 71 (`page.goto`)
