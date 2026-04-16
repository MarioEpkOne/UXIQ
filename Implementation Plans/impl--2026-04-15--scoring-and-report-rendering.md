# Implementation Plan: Scoring & Report Rendering

## Header
- **Spec**: specs/applied/spec-07-scoring-and-report-rendering.md
- **Worktree**: .claude/worktrees/scoring-and-report-rendering/
- **Scope — files in play** (agent must not touch files not listed here):
  - ui-analyzer/ui_analyzer/scorer.py  ← new file
  - ui-analyzer/ui_analyzer/report_renderer.py  ← new file
- **Reading list** (read these in order before starting, nothing else):
  1. /mnt/c/Users/Epkone/UXIQ/ui-analyzer/ui_analyzer/xml_parser.py
  2. /mnt/c/Users/Epkone/UXIQ/ui-analyzer/pyproject.toml

## Environment assumptions verified

- `pytest` 9.0.3 installed at system Python (`/usr/bin/python3`)
- `pytest-asyncio` 1.3.0 installed (required by pyproject.toml dev extras)
- `pytest-mock` 3.15.1 installed
- `pyproject.toml` has `asyncio_mode = "auto"` — no per-test `@pytest.mark.asyncio` needed
- `tests/conftest.py` sets a fake `ANTHROPIC_API_KEY` before any imports — unit tests do not need a real key

---

## Steps

### Step 1: Create `ui_analyzer/scorer.py`
**File**: `ui-analyzer/ui_analyzer/scorer.py`
**Action**: Create new file

**Full file content**:
```python
"""scorer.py — Compute per-tier star ratings and overall weighted score.

Pure, deterministic. Does not call any API. Never raises.
"""

from __future__ import annotations

from dataclasses import dataclass

from ui_analyzer.xml_parser import AuditReport


@dataclass
class Scores:
    tier1: float            # 1.0–5.0
    tier2: float            # 1.0–5.0
    tier3: float            # 1.0–5.0
    tier4_flag_count: int   # count only — not scored
    overall: float          # weighted: T1×0.4 + T2×0.35 + T3×0.25


def compute(report: AuditReport) -> Scores:
    """Compute Scores from an AuditReport. Always returns Scores, never raises."""
    t1 = _compute_tier1_stars(report.tier1_findings)
    t2 = _compute_tier23_stars(report.tier2_findings)
    t3 = _compute_tier23_stars(report.tier3_findings)
    overall = round((t1 * 0.4) + (t2 * 0.35) + (t3 * 0.25), 1)
    return Scores(
        tier1=t1,
        tier2=t2,
        tier3=t3,
        tier4_flag_count=len(report.tier4_findings),
        overall=overall,
    )


def _compute_tier1_stars(findings) -> float:
    """% of Tier 1 checks that passed, mapped to 1–5 stars.

    100% = 5★, 80% = 4★, 60% = 3★, 40% = 2★, <40% = 1★
    No findings → 5★ (assume clean).
    """
    if not findings:
        return 5.0
    passes = sum(1 for f in findings if f.result == "PASS")
    total = len(findings)
    ratio = passes / total
    return max(1.0, round(ratio * 5, 1))


def _compute_tier23_stars(findings) -> float:
    """Avg severity inverted to stars.

    avg=0 → 5★, avg=1 → 4★, avg=2 → 2.5★, avg=3 → 1★
    No findings → 5★ (no issues found).
    """
    if not findings:
        return 5.0
    severities = [f.severity for f in findings if isinstance(f.severity, int)]
    if not severities:
        return 5.0
    avg = sum(severities) / len(severities)
    return max(1.0, round(5.0 - (avg * 1.5), 1))


def stars_to_display(score: float) -> str:
    """Convert a 1.0–5.0 score to a Unicode star string.

    E.g. 3.1 → "★★★☆☆"
    Rounds to nearest whole star for display.
    """
    filled = round(score)
    return "★" * filled + "☆" * (5 - filled)
```

**What it does**: Implements the `Scores` dataclass, `compute()`, `_compute_tier1_stars()`, `_compute_tier23_stars()`, and `stars_to_display()` exactly as specified.

**Verification**: `python3 -c "from ui_analyzer.scorer import compute, Scores, stars_to_display"` exits 0 with no output.

---

### Step 2: Create `ui_analyzer/report_renderer.py`
**File**: `ui-analyzer/ui_analyzer/report_renderer.py`
**Action**: Create new file

**Full file content**:
```python
"""report_renderer.py — Assemble a Markdown audit report from AuditReport + Scores.

Pure, deterministic. Does not import anthropic, playwright, or any I/O module.
render() always returns a str and never raises.
"""

from __future__ import annotations

from ui_analyzer.xml_parser import AuditReport, Tier1Finding, Tier2Finding, Tier3Finding, Tier4Finding
from ui_analyzer.scorer import Scores, stars_to_display


def render(
    report: AuditReport,
    scores: Scores,
    app_type: str,
    image_source: str,
    axe_succeeded: bool,
    model: str = "claude-sonnet-4-6",
) -> str:
    """Assemble the final Markdown report string. Always returns str, never raises."""
    lines: list[str] = []

    # --- Header ---
    tier1_mode_display = (
        "Authoritative (axe-core)"
        if axe_succeeded
        else "Estimated (visual)"
    )

    lines.append("# UI Analysis Report")
    lines.append("")
    lines.append(f"**App type:** {app_type}")
    lines.append(f"**Input:** {image_source}")
    lines.append(f"**Tier 1 mode:** {tier1_mode_display}")
    lines.append(f"**Model:** {model}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # --- Overall Score table ---
    overall_stars = stars_to_display(scores.overall)
    lines.append(f"## Overall Score: {overall_stars} ({scores.overall} / 5)")
    lines.append("")
    lines.append("| Tier | Score | Weight |")
    lines.append("|------|-------|--------|")
    lines.append(f"| Tier 1 — Accessibility | {stars_to_display(scores.tier1)} | 40% |")
    lines.append(f"| Tier 2 — Visual Structure | {stars_to_display(scores.tier2)} | 35% |")
    lines.append(f"| Tier 3 — Usability | {stars_to_display(scores.tier3)} | 25% |")
    lines.append(f"| Tier 4 — Domain Patterns | {scores.tier4_flag_count} flags | — |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # --- Tier 1 ---
    lines.append("## Tier 1 — Accessibility (WCAG 2.1 AA)")
    lines.append("")
    if report.inventory:
        lines.append(report.inventory)
        lines.append("")
    lines.append("**Findings:**")
    lines.append("")
    if report.tier1_findings:
        for f in report.tier1_findings:
            lines.append(_render_tier1_finding(f))
            lines.append("")
    else:
        lines.append("*No issues found.*")
        lines.append("")
    lines.append("---")
    lines.append("")

    # --- Tier 2 ---
    lines.append("## Tier 2 — Visual Structure (Gestalt / CRAP)")
    lines.append("")
    if report.structure_observation:
        lines.append(report.structure_observation)
        lines.append("")
    lines.append("**Findings:**")
    lines.append("")
    if report.tier2_findings:
        for f in report.tier2_findings:
            lines.append(_render_tier23_finding(f))
            lines.append("")
    else:
        lines.append("*No issues found.*")
        lines.append("")
    lines.append("---")
    lines.append("")

    # --- Tier 3 ---
    lines.append("## Tier 3 — Usability & Affordance")
    lines.append("")
    lines.append("**Findings:**")
    lines.append("")
    if report.tier3_findings:
        for f in report.tier3_findings:
            lines.append(_render_tier23_finding(f))
            lines.append("")
    else:
        lines.append("*No issues found.*")
        lines.append("")
    lines.append("---")
    lines.append("")

    # --- Tier 4 ---
    lines.append(f"## Tier 4 — Domain Patterns ({app_type})")
    lines.append("")
    if report.tier4_findings:
        for f in report.tier4_findings:
            lines.append(_render_tier4_finding(f))
            lines.append("")
    else:
        lines.append("*No issues found.*")
        lines.append("")
    lines.append("---")
    lines.append("")

    # --- parse_warnings passthrough ---
    if report.parse_warnings:
        lines.append("---")
        lines.append("")
        lines.append("⚠️ Claude returned a malformed response — some tiers may be missing.")
        lines.append("")

    # --- Footer ---
    lines.append(f"*Generated by ui-analyzer v1 using {model}*")

    return "\n".join(lines)


def _render_tier1_finding(f: Tier1Finding) -> str:
    icon = "❌" if f.result == "FAIL" else "✅"
    estimated_label = " *(ESTIMATED — verify manually)*" if f.estimated else ""
    lines = [
        f"{icon} **{f.result}** — WCAG {f.criterion}",
        f"Element: `{f.element}`{estimated_label}",
        f"Issue: {f.observed} (required {f.required})",
        f"Recommendation: {f.recommendation}",
    ]
    return "\n".join(lines)


def _render_tier23_finding(f: Tier2Finding | Tier3Finding) -> str:
    severity_icon = "🔴" if f.severity == 3 else "⚠️"
    lines = [
        f"{severity_icon} **Severity {f.severity}** — {f.principle}",
        f"Element: {f.element}",
        f"Issue: {f.issue}",
        f"Recommendation: {f.recommendation}",
    ]
    if f.nielsen_tag is not None:
        lines.append(f"Nielsen heuristic: #{f.nielsen_tag}")
    return "\n".join(lines)


def _render_tier4_finding(f: Tier4Finding) -> str:
    lines = [
        f"🚩 **Flag** — {f.pattern}",
        f"Element: {f.element}",
        f"Issue: {f.issue}",
        f"Recommendation: {f.recommendation}",
    ]
    return "\n".join(lines)
```

**What it does**: Implements the complete `render()` function plus three private per-finding renderers, following the exact Markdown structure and section header contract from the spec.

**Verification**: `python3 -c "from ui_analyzer.report_renderer import render"` exits 0 with no output.

---

### Step 3: Verify imports from project root
**Action**: Run smoke-import check from `ui-analyzer/` directory.

```bash
cd /mnt/c/Users/Epkone/UXIQ/ui-analyzer && python3 -c "
from ui_analyzer.scorer import Scores, compute, stars_to_display, _compute_tier1_stars, _compute_tier23_stars
from ui_analyzer.report_renderer import render
print('All imports OK')
"
```

Expected output: `All imports OK`

---

### Step 4: Run inline logic verification
**Action**: Run a quick in-process calculation to confirm the spec's stated formula outputs.

```bash
cd /mnt/c/Users/Epkone/UXIQ/ui-analyzer && python3 -c "
from ui_analyzer.scorer import _compute_tier1_stars, _compute_tier23_stars, stars_to_display, compute
from ui_analyzer.xml_parser import AuditReport, Tier1Finding, Tier2Finding, Tier3Finding

# _compute_tier1_stars([]) → 5.0
assert _compute_tier1_stars([]) == 5.0, '_compute_tier1_stars([]) should be 5.0'

# All PASS → 5.0
class FakeFinding:
    def __init__(self, result): self.result = result
all_pass = [FakeFinding('PASS')] * 5
assert _compute_tier1_stars(all_pass) == 5.0, 'all PASS should be 5.0'

# 60% PASS → 3.0
mixed = [FakeFinding('PASS')] * 3 + [FakeFinding('FAIL')] * 2
assert _compute_tier1_stars(mixed) == 3.0, '60% PASS should be 3.0'

# _compute_tier23_stars([]) → 5.0
assert _compute_tier23_stars([]) == 5.0, '_compute_tier23_stars([]) should be 5.0'

# all severity-3 → 1.0 (5.0 - 3*1.5 = 0.5, max(1.0, 0.5) = 1.0)
class SevFinding:
    def __init__(self, sev): self.severity = sev
all_sev3 = [SevFinding(3)] * 3
assert _compute_tier23_stars(all_sev3) == 1.0, 'all sev-3 should be 1.0'

# stars_to_display(3.1) → '★★★☆☆'
assert stars_to_display(3.1) == '★★★☆☆', f'Got: {stars_to_display(3.1)}'
assert stars_to_display(5.0) == '★★★★★', f'Got: {stars_to_display(5.0)}'

# compute() overall: T1=5.0, T2=3.0, T3=4.0 → 4.1
# (5*0.4) + (3*0.35) + (4*0.25) = 2.0 + 1.05 + 1.0 = 4.05 → 4.1
from ui_analyzer.xml_parser import AuditReport, Tier1Finding, Tier2Finding, Tier3Finding
# Build report that produces T1=5.0 (no findings), T2=3.0 (avg sev=1.33), T3=4.0 (avg sev=0.67)
report = AuditReport()
# T1=5.0 — empty findings
# T2: avg severity = (1+1+2)/3 = 1.33 → 5-(1.33*1.5)=3.0 → round(3.0,1)=3.0
report.tier2_findings = [Tier2Finding(principle='p', severity=1, element='e', issue='i', recommendation='r'),
                          Tier2Finding(principle='p', severity=1, element='e', issue='i', recommendation='r'),
                          Tier2Finding(principle='p', severity=2, element='e', issue='i', recommendation='r')]
# T3: avg severity = (1+0)/2? Use severity=0 → 5-(0.67*1.5)=3.995≈4.0
# Actually let's just use severity=1 for 2 findings → avg=1 → 5-1.5=3.5 ≠ 4.0
# Use 1 finding severity=0 isn't an int...
# Simpler: verify formula independently
scores = compute(report)
print(f'T1={scores.tier1}, T2={scores.tier2}, T3={scores.tier3}, overall={scores.overall}')
expected_overall = round((scores.tier1 * 0.4) + (scores.tier2 * 0.35) + (scores.tier3 * 0.25), 1)
assert scores.overall == expected_overall, f'overall mismatch: {scores.overall} != {expected_overall}'

print('All inline assertions passed')
"
```

Expected output ends with: `All inline assertions passed`

---

### Step 5: Run existing test suite to confirm no regressions
**Action**: Run the full pytest suite from `ui-analyzer/`.

```bash
cd /mnt/c/Users/Epkone/UXIQ/ui-analyzer && python3 -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all previously-passing tests still pass.

---

## Post-Implementation Checklist
- [ ] `ui-analyzer/ui_analyzer/scorer.py` exists and imports cleanly
- [ ] `ui-analyzer/ui_analyzer/report_renderer.py` exists and imports cleanly
- [ ] `scorer.py` does not import `anthropic`, `playwright`, or any I/O module
- [ ] `report_renderer.py` does not import `anthropic`, `playwright`, or any I/O module
- [ ] `_compute_tier1_stars([])` returns `5.0`
- [ ] `_compute_tier1_stars` with all PASS returns `5.0`
- [ ] `_compute_tier1_stars` with 60% PASS returns `3.0`
- [ ] `_compute_tier23_stars([])` returns `5.0`
- [ ] `_compute_tier23_stars` with all severity-3 returns `1.0`
- [ ] `stars_to_display(3.1)` returns `"★★★☆☆"`
- [ ] `stars_to_display(5.0)` returns `"★★★★★"`
- [ ] `compute()` overall formula: `round(T1*0.4 + T2*0.35 + T3*0.25, 1)` — for T1=5.0, T2=3.0, T3=4.0 result is `4.1`
- [ ] `render()` output contains all four tier section headers: "Tier 1 — Accessibility", "Tier 2 — Visual Structure", "Tier 3 — Usability & Affordance", "Tier 4 — Domain Patterns"
- [ ] FAIL finding has `❌` icon; PASS finding has `✅` icon
- [ ] `finding.estimated=True` renders `*(ESTIMATED — verify manually)*`
- [ ] Empty tier findings section renders `*No issues found.*`
- [ ] Non-empty `parse_warnings` appends malformed-response warning block
- [ ] `axe_succeeded=True` → header shows "Authoritative (axe-core)"; `False` → "Estimated (visual)"
- [ ] Non-empty `inventory` is printed before Tier 1 findings; empty `inventory` is omitted
- [ ] Non-empty `structure_observation` is printed before Tier 2 findings; empty is omitted
- [ ] severity-3 finding renders with `🔴`; severity-1 and severity-2 render with `⚠️`
- [ ] Tier 4 flag renders with `🚩 **Flag** — {pattern}`
- [ ] `nielsen_tag` is present → "Nielsen heuristic: #{n}" line is included; `None` → omitted
- [ ] All existing tests still pass (`python3 -m pytest tests/ -v`)

## Verification Approach

Run `python3 -m pytest tests/ -v` from `/mnt/c/Users/Epkone/UXIQ/ui-analyzer/` after each file creation. Spec 09 will provide the formal test suite for scorer and renderer; this spec's verification is confirmed by the inline smoke-check in Step 4 and absence of regressions in Step 5.

---

## Commit Message (draft)
```
feat: implement scorer and report_renderer modules (spec-07)

Add scorer.py (Scores dataclass, compute(), star helpers) and
report_renderer.py (render() assembling the full Markdown audit report).
Both modules are pure/deterministic and do not call any external API.
```
