# Spec — axe-core Runner

**Source spec:** specs/spec-03-axe-core-runner.md  
**Parent spec:** spec--2026-04-15--15-30--ui-screenshot-analyzer.md  
**Status:** Ready for implementation  
**Depends on:** Spec 01 (UIAnalyzerError), Spec 02 (for shared Playwright pattern)  
**Blocks:** Spec 05 (prompt builder consumes AxeCoreResult), Spec 08 (handler calls run_axe())

---

## Goal

Implement `ui_analyzer/axe_runner.py`. This module:
1. Accepts a URL (never a file path — axe-core requires a live DOM)
2. Uses Playwright to load the page and inject the axe-core JS library
3. Executes axe-core WCAG 2.1 AA checks
4. Returns an `AxeCoreResult` dataclass on success, or an `AxeFailure` dataclass on soft failure

This module never raises `UIAnalyzerError`. axe-core failure is a **soft failure** — the handler injects `<axe_unavailable>` (using `AxeFailure.reason`) instead and proceeds in estimated mode.

---

## Current State

The `ui_analyzer/` package exists with:
- `__init__.py` — imports `UIAnalyzerError`, checks `ANTHROPIC_API_KEY`
- `exceptions.py` — defines `UIAnalyzerError`; documents axe-core failure as soft

`playwright>=1.43.0` is already listed in `pyproject.toml` dependencies.

`axe_runner.py` does not yet exist.

---

## Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Soft failure return type | `AxeFailure` (not `None`) | Carries a `reason` string for injection into `<axe_unavailable>` |
| axe-core version | 4.9.1 (CDN-pinned) | Reproducible; if CDN unreachable, injection fails and AxeFailure is returned |
| WCAG scope | `wcag2a`, `wcag2aa`, `wcag21aa` tags | Matches WCAG 2.1 Level AA rubric in Tier 1 |
| Criteria extracted | 1.4.3, 1.4.11, 2.5.8, 1.4.1 | Per axe rule-to-criterion mapping table |
| 2.4.7 (focus indicators) | NOT extracted from axe | Visual judgment by Claude from screenshot |
| `incomplete` results | Ignored | Introduce ambiguity the Tier 1 model doesn't handle |
| Browser lifecycle | One browser per `run_axe()` call | Isolation from `image_source.resolve()` |

---

## Technical Design

### Scope

Files created by this spec:

```
ui_analyzer/
└── axe_runner.py
```

### Public Interface

```python
from dataclasses import dataclass, field

@dataclass
class AxeViolation:
    element: str        # CSS selector or description (e.g. ".nav-link")
    criterion: str      # WCAG criterion (e.g. "1.4.3")
    result: str         # "FAIL" always (violations are failures)
    detail: str         # Human-readable description of the violation
    # Optional numeric fields populated when available:
    ratio: float | None = None          # contrast ratio (for 1.4.3 / 1.4.11)
    required_ratio: float | None = None
    size_px: str | None = None          # e.g. "18x18" (for 2.5.8)
    required_px: str | None = None

@dataclass
class AxeCriterionResult:
    criterion: str           # e.g. "1.4.3"
    result: str              # "PASS" or "FAIL"
    violations: list[AxeViolation] = field(default_factory=list)

@dataclass
class AxeCoreResult:
    source: str = "axe-core — authoritative, do not re-estimate"
    findings: list[AxeCriterionResult] = field(default_factory=list)

@dataclass
class AxeFailure:
    """Returned when axe-core cannot complete. Carries a reason string so the
    handler can inject the correct human-readable message into <axe_unavailable>."""
    reason: str  # e.g. "axe-core JS injection failed", "axe-core timed out"

def run_axe(url: str) -> AxeCoreResult | AxeFailure:
    """Run axe-core against the given URL.

    Returns AxeCoreResult on success.
    Returns AxeFailure (with a specific reason string) on any failure.
    Never raises UIAnalyzerError — axe failure is always soft.
    """
```

### axe-core Rule-to-Criterion Mapping

| axe-core rule id(s) | WCAG criterion |
|--------------------|----------------|
| `color-contrast` | 1.4.3 |
| `non-text-contrast` | 1.4.11 |
| `target-size` | 2.5.8 |
| `color-not-used-as-sole-meaning` (or equivalent) | 1.4.1 |

### Playwright Setup

```python
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import json
import logging

AXE_TIMEOUT_MS = 10_000  # 10 seconds

logger = logging.getLogger(__name__)
```

**Browser lifecycle rule:** `run_axe()` launches and closes its own browser instance. It does NOT share a browser with `image_source.resolve()`. Both functions are called independently by the handler. Cross-call state isolation is required.

### Execution Sequence

```python
def run_axe(url: str) -> AxeCoreResult | AxeFailure:
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context()
            page = context.new_page()

            try:
                page.goto(url, timeout=30_000, wait_until="networkidle")
            except PlaywrightTimeout:
                logger.warning("axe-core: page load timed out for %s", url)
                return AxeFailure(reason="axe-core page load timed out")

            # Inject axe-core from CDN
            try:
                page.add_script_tag(url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js")
            except Exception as e:
                logger.warning("axe-core: script injection failed: %s", e)
                return AxeFailure(reason="axe-core JS injection failed")

            # Run axe
            try:
                raw = page.evaluate(
                    """async () => {
                        return await Promise.race([
                            axe.run(document, {
                                runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] }
                            }),
                            new Promise((_, reject) => setTimeout(
                                () => reject(new Error('axe-core timed out')),
                                10000
                            ))
                        ]);
                    }""",
                )
            except Exception as e:
                logger.warning("axe-core: evaluation failed or timed out: %s", e)
                return AxeFailure(reason="axe-core timed out")

            browser.close()
            return _parse_axe_result(raw)

    except Exception as e:
        logger.warning("axe-core: unexpected error: %s", e)
        return AxeFailure(reason=f"axe-core unexpected error: {e}")
```

### Parsing axe Output

`_parse_axe_result(raw: dict) -> AxeCoreResult` maps the axe JSON output format to `AxeCoreResult`.

axe-core returns:
```json
{
  "violations": [...],
  "passes": [...],
  "incomplete": [...],
  "inapplicable": [...]
}
```

Only `violations` and `passes` are used. `incomplete` and `inapplicable` are ignored.

Mapping logic:
- For each relevant criterion (1.4.3, 1.4.11, 2.5.8, 1.4.1):
  - If any axe violation matches: create `AxeCriterionResult(result="FAIL", violations=[...])`
  - If criterion appears in `passes` and no violations: create `AxeCriterionResult(result="PASS")`
  - If criterion appears in neither: **omit from findings** (do not add a placeholder)

For violations, extract element selectors from `axe.violations[].nodes[].target` and details from `axe.violations[].description`.

Optional numeric fields (`ratio`, `required_ratio`, `size_px`, `required_px`) are extracted from axe node data when available:
- For `color-contrast` / `non-text-contrast`: extract from `nodes[].any[].data.contrastRatio` and `nodes[].any[].data.expectedContrastRatio`
- For `target-size`: extract from node data if available; leave `None` otherwise

---

## Edge Cases & Error Handling

| Failure | `AxeFailure.reason` | Action |
|---------|---------------------|--------|
| Page load timeout | `"axe-core page load timed out"` | `logger.warning(...)`, return `AxeFailure` |
| axe JS injection fails | `"axe-core JS injection failed"` | `logger.warning(...)`, return `AxeFailure` |
| `axe.run()` exceeds 10s | `"axe-core timed out"` | `logger.warning(...)`, return `AxeFailure` |
| axe crashes / throws | `"axe-core timed out"` | `logger.warning(...)`, return `AxeFailure` |
| Any unexpected exception | `"axe-core unexpected error: {e}"` | `logger.warning(...)`, return `AxeFailure` |

The `reason` string is injected verbatim into the `<axe_unavailable>` block by `prompt_builder.py`.

**No `UIAnalyzerError` is raised from this module under any circumstances.**

---

## Constraints & Invariants

- This module only accepts URLs. It must not be called with a file path. The handler enforces this.
- axe-core version is pinned to `4.9.1` (CDN URL). If the CDN is unreachable, the injection step fails and `AxeFailure` is returned.
- Do not parse or return `incomplete` results. They introduce ambiguity the Tier 1 scoring model doesn't handle.
- `AxeCoreResult.source` is a fixed string — it tells Claude the data is authoritative and must not be re-estimated.
- `run_axe()` never raises any exception — all failure paths return `AxeFailure`.
- Browser lifecycle: launch and close within each `run_axe()` call. No shared browser state.

---

## Testing Strategy

Covered by Spec 09. Key assertions:
- [ ] Valid URL with axe violations → `AxeCoreResult` with populated `findings`, criteria mapped correctly
- [ ] Valid URL with no violations → `AxeCoreResult` with all criteria as PASS
- [ ] Page load timeout → returns `AxeFailure` with reason `"axe-core page load timed out"` (no exception propagated)
- [ ] axe JS injection failure → returns `AxeFailure` with reason `"axe-core JS injection failed"` (no exception propagated)
- [ ] axe evaluation timeout → returns `AxeFailure` with reason `"axe-core timed out"` (no exception propagated)
- [ ] `run_axe()` never raises any exception — all failures return `AxeFailure`
- [ ] Criteria not found in axe output are omitted (not added as placeholders)
- [ ] `AxeCoreResult.source` is always the fixed string `"axe-core — authoritative, do not re-estimate"`

---

## Open Questions

None — all decisions resolved.
