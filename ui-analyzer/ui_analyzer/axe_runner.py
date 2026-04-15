"""axe_runner.py — run axe-core WCAG 2.1 AA accessibility checks against a URL.

Public interface:
    run_axe(url: str) -> AxeCoreResult | AxeFailure

This module never raises UIAnalyzerError. axe-core failure is always soft:
the caller receives an AxeFailure with a reason string and proceeds in
estimated mode.

Browser lifecycle: one Playwright Chromium browser per run_axe() call.
No shared browser state with image_source.resolve().
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

AXE_CDN_URL = (
    "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js"
)
AXE_TIMEOUT_MS = 10_000  # 10 seconds for axe.run()

# axe-core rule ID → WCAG criterion mapping (only the 4 criteria extracted)
_RULE_TO_CRITERION: dict[str, str] = {
    "color-contrast": "1.4.3",
    "non-text-contrast": "1.4.11",
    "target-size": "2.5.8",
    "color-not-used-as-sole-meaning": "1.4.1",
}

# Supported criteria set (used to decide what to include in findings)
_SUPPORTED_CRITERIA = frozenset(_RULE_TO_CRITERION.values())

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AxeViolation:
    """A single WCAG violation detected by axe-core."""

    element: str        # CSS selector or description (e.g. ".nav-link")
    criterion: str      # WCAG criterion (e.g. "1.4.3")
    result: str         # "FAIL" always (violations are failures)
    detail: str         # Human-readable description of the violation
    # Optional numeric fields populated when available:
    ratio: float | None = None           # contrast ratio (for 1.4.3 / 1.4.11)
    required_ratio: float | None = None
    size_px: str | None = None           # e.g. "18x18" (for 2.5.8)
    required_px: str | None = None


@dataclass
class AxeCriterionResult:
    """Per-criterion result aggregated from axe violations / passes."""

    criterion: str           # e.g. "1.4.3"
    result: str              # "PASS" or "FAIL"
    violations: list[AxeViolation] = field(default_factory=list)


@dataclass
class AxeCoreResult:
    """Successful axe-core run output."""

    source: str = "axe-core — authoritative, do not re-estimate"
    findings: list[AxeCriterionResult] = field(default_factory=list)


@dataclass
class AxeFailure:
    """Returned when axe-core cannot complete.

    Carries a reason string so the handler can inject the correct
    human-readable message into <axe_unavailable>.
    """

    reason: str  # e.g. "axe-core JS injection failed", "axe-core timed out"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_axe(url: str) -> AxeCoreResult | AxeFailure:
    """Run axe-core against the given URL.

    Returns AxeCoreResult on success.
    Returns AxeFailure (with a specific reason string) on any failure.
    Never raises UIAnalyzerError — axe failure is always soft.
    """
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context()
            page = context.new_page()

            # --- 1. Load the page ---
            try:
                page.goto(url, timeout=30_000, wait_until="networkidle")
            except PlaywrightTimeout:
                logger.warning("axe-core: page load timed out for %s", url)
                browser.close()
                return AxeFailure(reason="axe-core page load timed out")

            # --- 2. Inject axe-core from CDN ---
            try:
                page.add_script_tag(url=AXE_CDN_URL)
            except Exception as e:
                logger.warning("axe-core: script injection failed: %s", e)
                browser.close()
                return AxeFailure(reason="axe-core JS injection failed")

            # --- 3. Run axe ---
            try:
                raw = page.evaluate(
                    """async () => {
                        return await axe.run(document, {
                            runOnly: {
                                type: 'tag',
                                values: ['wcag2a', 'wcag2aa', 'wcag21aa']
                            }
                        });
                    }""",
                    timeout=AXE_TIMEOUT_MS,
                )
            except Exception as e:
                logger.warning(
                    "axe-core: evaluation failed or timed out: %s", e
                )
                browser.close()
                return AxeFailure(reason="axe-core timed out")

            browser.close()
            return _parse_axe_result(raw)

    except Exception as e:
        logger.warning("axe-core: unexpected error: %s", e)
        return AxeFailure(reason=f"axe-core unexpected error: {e}")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_axe_result(raw: dict) -> AxeCoreResult:
    """Map raw axe JSON output to AxeCoreResult.

    Only 'violations' and 'passes' are used.
    'incomplete' and 'inapplicable' are ignored.

    For each supported criterion:
    - If any violation matches → AxeCriterionResult(result="FAIL", violations=[...])
    - If in passes and no violation → AxeCriterionResult(result="PASS")
    - If in neither → omit from findings (no placeholder)
    """
    violations_raw: list[dict] = raw.get("violations", [])
    passes_raw: list[dict] = raw.get("passes", [])

    # Build a set of rule IDs that appear in passes (for quick lookup)
    passing_rules: set[str] = {item["id"] for item in passes_raw}

    # Build a mapping criterion → list[AxeViolation] from violations
    criterion_violations: dict[str, list[AxeViolation]] = {}
    for violation in violations_raw:
        rule_id: str = violation.get("id", "")
        criterion = _RULE_TO_CRITERION.get(rule_id)
        if criterion is None:
            continue  # not a criterion we track

        description: str = violation.get("description", "")
        nodes: list[dict] = violation.get("nodes", [])

        for node in nodes:
            element = _extract_selector(node)
            ratio, required_ratio = _extract_contrast(rule_id, node)
            size_px, required_px = _extract_size(rule_id, node)

            av = AxeViolation(
                element=element,
                criterion=criterion,
                result="FAIL",
                detail=description,
                ratio=ratio,
                required_ratio=required_ratio,
                size_px=size_px,
                required_px=required_px,
            )
            criterion_violations.setdefault(criterion, []).append(av)

    # Build findings list
    findings: list[AxeCriterionResult] = []

    # Determine which criteria are referenced by passing rules
    criteria_in_passes: set[str] = set()
    for rule_id, criterion in _RULE_TO_CRITERION.items():
        if rule_id in passing_rules:
            criteria_in_passes.add(criterion)

    # Merge: violations take priority; PASS if in passes and no violation
    all_referenced_criteria: set[str] = (
        set(criterion_violations.keys()) | criteria_in_passes
    )

    for criterion in sorted(all_referenced_criteria):
        if criterion in criterion_violations:
            findings.append(
                AxeCriterionResult(
                    criterion=criterion,
                    result="FAIL",
                    violations=criterion_violations[criterion],
                )
            )
        else:
            # criterion in passes_only
            findings.append(
                AxeCriterionResult(
                    criterion=criterion,
                    result="PASS",
                )
            )

    return AxeCoreResult(findings=findings)


def _extract_selector(node: dict) -> str:
    """Extract a CSS selector string from a node's 'target' list."""
    target = node.get("target", [])
    if target:
        # target is a list of selectors; join with ' > ' for a path
        return " > ".join(str(t) for t in target)
    return node.get("html", "unknown element")


def _extract_contrast(rule_id: str, node: dict) -> tuple[float | None, float | None]:
    """Extract contrast ratio and required ratio for contrast-related rules."""
    if rule_id not in ("color-contrast", "non-text-contrast"):
        return None, None

    any_checks: list[dict] = node.get("any", [])
    for check in any_checks:
        data = check.get("data") or {}
        contrast_ratio = data.get("contrastRatio")
        expected = data.get("expectedContrastRatio")
        if contrast_ratio is not None:
            ratio = float(contrast_ratio) if contrast_ratio is not None else None
            req = float(expected) if expected is not None else None
            return ratio, req

    return None, None


def _extract_size(rule_id: str, node: dict) -> tuple[str | None, str | None]:
    """Extract size_px and required_px for target-size rule."""
    if rule_id != "target-size":
        return None, None

    any_checks: list[dict] = node.get("any", [])
    for check in any_checks:
        data = check.get("data") or {}
        width = data.get("width")
        height = data.get("height")
        min_size = data.get("minSize")

        size_px = f"{width}x{height}" if (width is not None and height is not None) else None
        required_px = f"{min_size}x{min_size}" if min_size is not None else None
        return size_px, required_px

    return None, None
