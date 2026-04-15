# Spec: UI Screenshot Analyzer — Claude Tool Use Function

**Date:** 2026-04-15  
**Status:** Ready for implementation  
**Version:** v1 (analysis only — no auto-fixing)

---

## Goal

Build a Claude Tool Use function called `analyze_ui_screenshot` that accepts a screenshot (by URL or file path) of any web UI and returns a structured Markdown report scoring the UI against a 4-tier rubric covering accessibility, visual structure, usability, and domain-specific patterns.

The tool does **not** read source code. It analyzes only what is visually present in the screenshot. It does not make changes. It only surfaces findings and recommendations.

---

## Current State

This is a greenfield project. No existing codebase. The tool will be built as a standalone Python package and exposed as a Claude Tool Use function definition (not a REST API or MCP server in v1).

---

## Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Input: URL or file path | Caller provides either a live URL or a local screenshot path. No base64 in tool params — the tool resolves the image itself. |
| 2 | Integration surface: Claude Tool Use function | Packaged as a tool definition JSON + a Python handler, callable from any Claude agent. |
| 3 | Output: Markdown report | Human-readable. Evidence sections are always included (verbose mode is the default and only mode in v1). |
| 4 | Rubric: 4-tier hybrid framework | Tier 1 WCAG (hard), Tier 2 Gestalt/CRAP (visual), Tier 3 Nielsen/Norman (usability), Tier 4 domain-specific (optional). See Rubric section. |
| 5 | Tier 1 accuracy: axe-core for URLs, advisory fallback for files | When a URL is provided, Playwright captures the screenshot and axe-core computes real WCAG data. When a file path is provided, Claude uses visual estimation with an explicit uncertainty disclaimer. |
| 6 | URL failure: hard fail | If Playwright cannot load/capture the URL (404, timeout, render failure), the tool returns an error. No silent fallback. |
| 7 | App type: required enum | Caller must specify one of: `web_dashboard`, `landing_page`, `onboarding_flow`, `forms`. This activates the relevant Tier 4 domain module and calibrates scoring expectations. |
| 8 | Scoring: per-tier stars + overall | Each tier receives a 1–5 star rating. One weighted overall score is shown at the top. |
| 9 | Single screenshot per call (v1) | One image per invocation. Multi-state or multi-page analysis is done by calling the tool multiple times. |
| 10 | Language: Python | Anthropic Python SDK is most mature for this use case. Playwright and axe-core have strong Python support. |
| 11 | Model: claude-sonnet-4-6 | Best balance of vision quality, reasoning depth, speed, and cost for v1. |
| 12 | Chain-of-thought: describe → detail → judge | The system prompt forces Claude to enumerate elements before scoring, reducing hallucinated findings. This internal reasoning is included in the output as Evidence sections. |
| 13 | Forms as standalone app_type | Forms patterns (label placement, error proximity, required fields) are distinct enough to warrant their own enum value rather than being folded into onboarding_flow. |

---

## Rubric

The rubric consists of four tiers evaluated in sequence. Claude is instructed to apply only what is observable in a static screenshot and must never score criteria that require live interaction.

### TIER 1 — Hard Accessibility Checks
**Source:** WCAG 2.1 AA  
**Scoring:** Binary — Pass / Fail  
**When URL provided:** axe-core computes exact values.  
**When file provided:** Claude estimates with explicit "ESTIMATED" label. Always recommends manual verification.

| Check | Threshold | WCAG Criterion |
|-------|-----------|----------------|
| Text contrast ratio (normal text) | ≥ 4.5:1 | 1.4.3 |
| Text contrast ratio (large text ≥ 18px or 14px bold) | ≥ 3:1 | 1.4.3 |
| UI component / non-text contrast | ≥ 3:1 | 1.4.11 |
| Touch targets | ≥ 24px min, ≥ 44px recommended | 2.5.8 |
| Body text size | ≥ 16px recommended | — |
| Color as sole meaning conveyor | Must not be sole indicator | 1.4.1 |
| Focus indicators | Flag only if a focus state is visible in the screenshot | 2.4.7 |

### TIER 2 — Visual Structure & Organization
**Source:** Gestalt principles + CRAP design principles  
**Scoring:** Severity 1 (minor) / 2 (notable) / 3 (critical)  
**Cite:** Specific element name and location in the screenshot.

| Principle | What to evaluate |
|-----------|-----------------|
| Proximity | Related elements grouped; unrelated elements separated |
| Similarity | Interactive elements share consistent visual treatment |
| Figure/Ground | Primary content has sufficient contrast against background |
| Alignment | Elements align to shared axes / consistent grid |
| Contrast (CRAP) | Visual weight maps to functional importance |
| Repetition | Consistent patterns for buttons, spacing, type scale across the frame |

### TIER 3 — Usability & Affordance Signals
**Source:** Nielsen heuristics #4, #6, #8 + Norman affordance model + cognitive load theory  
**Scoring:** Severity 1 (minor) / 2 (notable) / 3 (critical)  
**Tag:** Each finding with the nearest Nielsen heuristic number.  
**Constraint:** Only evaluate heuristics observable in a static screenshot. Skip all others.

| Criterion | Source | What to evaluate |
|-----------|--------|-----------------|
| Consistency | Nielsen #4 | Button styles, color roles, terminology consistent within visible screen |
| Recognition over Recall | Nielsen #6 | Options and actions visible; user doesn't need to memorize |
| Aesthetic & Minimalist Design | Nielsen #8 | No visual noise; every element earns its presence |
| Norman Signifiers | Norman | Buttons look clickable, inputs look fillable, links are distinguishable |
| Cognitive Load | CLT | Density appropriate; content chunked into scannable units; no competing focal points |
| Visual Hierarchy | — | One dominant CTA; heading levels proportional; attention flow clear |

### TIER 4 — Domain-Specific Patterns
**Source:** Domain conventions  
**Scoring:** Flag only — no severity score. Activated based on `app_type` parameter.

| app_type | Patterns to evaluate |
|----------|---------------------|
| `web_dashboard` | Data-ink ratio, metric hierarchy, chart type appropriateness |
| `landing_page` | Z-pattern CTA alignment, above-fold headline clarity, trust signal placement |
| `onboarding_flow` | Step progression clarity, primary action prominence, progress indicator visibility |
| `forms` | Label-above-field placement, inline error proximity, required field marking |

### Critical Constraint (applies to all tiers)

> Only evaluate what a screenshot can actually show. Do NOT score: system status feedback, undo behavior, error prevention during typing, keyboard navigation, or screen reader compatibility. Scoring unobservable criteria produces hallucinated findings.

---

## Technical Design

### Project Structure

```
ui-analyzer/
├── pyproject.toml
├── .env.example              # ANTHROPIC_API_KEY=
├── ui_analyzer/
│   __init__.py
│   tool_definition.py        # Claude tool JSON schema
│   handler.py                # analyze_ui_screenshot() implementation
│   image_source.py           # URL vs file path resolution
│   axe_runner.py             # Playwright + axe-core → AxeCoreResult dataclass
│   context_events.py         # ContextEvent dataclass, event_to_xml(), thread_to_prompt()
│   prompt_builder.py         # build_thread() — assembles list[ContextEvent] from inputs
│   xml_parser.py             # Parses Claude's <audit_report> XML → AuditReport dataclass
│   scorer.py                 # Per-tier star rating computation from AuditReport
│   report_renderer.py        # Markdown report assembly from AuditReport + scores
│   rubric/
│       __init__.py
│       tier1.py              # WCAG check definitions (as Python dict → serialized to YAML in XML block)
│       tier2.py              # Gestalt/CRAP definitions
│       tier3.py              # Nielsen/Norman definitions
│       output_schema.py      # OUTPUT_SCHEMA_XML constant (the <output_schema> block)
│       tier4/
│           web_dashboard.py
│           landing_page.py
│           onboarding_flow.py
│           forms.py
└── tests/
    fixtures/                 # Sample screenshots for testing
    test_handler.py
    test_axe_runner.py
    test_scorer.py
    test_prompt_builder.py
    test_xml_parser.py        # Parses well-formed and malformed Claude XML responses
    test_context_events.py    # event_to_xml() and thread_to_prompt() output shape
```

### Tool Definition (Claude Tool Use schema)

```python
TOOL_DEFINITION = {
    "name": "analyze_ui_screenshot",
    "description": (
        "Analyzes the visual design and UX of a web UI screenshot. "
        "Returns a structured Markdown report with findings across four tiers: "
        "accessibility (WCAG), visual structure (Gestalt/CRAP), usability "
        "(Nielsen/Norman), and domain-specific patterns. "
        "Does not read source code. Analysis is screenshot-only."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "image_source": {
                "type": "string",
                "description": (
                    "Either a URL (https://...) or an absolute file path to a "
                    "PNG, JPG, or WebP screenshot. If a URL, Playwright captures "
                    "the page and axe-core runs WCAG checks. If a file path, "
                    "Tier 1 results are visually estimated."
                )
            },
            "app_type": {
                "type": "string",
                "enum": ["web_dashboard", "landing_page", "onboarding_flow", "forms"],
                "description": (
                    "The type of web UI being analyzed. Activates the relevant "
                    "Tier 4 domain pattern module and calibrates scoring expectations."
                )
            }
        },
        "required": ["image_source", "app_type"]
    }
}
```

### Data Flow

```
Caller invokes tool
        │
        ▼
image_source.resolve(image_source)
        │
        ├── URL? ──► Playwright.capture(url) ──► screenshot bytes
        │                    │
        │                    ├── axe-core.run(url) ──► AxeCoreResult dataclass
        │                    │
        │                    └── Playwright fails? ──► raise UIAnalyzerError
        │
        └── file path? ──► load image bytes from disk
                                │
                                └── axe_result = None  (advisory mode)
        │
        ▼
prompt_builder.build_thread(screenshot_bytes, axe_result, app_type)
        │
        ├── Assembles list[ContextEvent] in order:
        │     1. ContextEvent(type="analysis_request", data={app_type, source_type, tier1_mode, viewport_width, viewport_height})
        │     2. ContextEvent(type="axe_core_result",  data=axe_result)     ← if axe succeeded
        │        OR ContextEvent(type="axe_unavailable", data={reason, ...}) ← if axe failed
        │        (omitted entirely only when source_type is "file")
        │     3. ContextEvent(type="rubric_tier1",    data=TIER1_DEFINITION)
        │     4. ContextEvent(type="rubric_tier2",    data=TIER2_DEFINITION)
        │     5. ContextEvent(type="rubric_tier3",    data=TIER3_DEFINITION)
        │     6. ContextEvent(type="rubric_tier4",    data=tier4_module.DEFINITION)
        │     7. ContextEvent(type="output_schema",   data=OUTPUT_SCHEMA_XML)
        │
        └── thread_to_prompt(events) → single XML user message string
        │
        ▼
anthropic.messages.create(
    model="claude-sonnet-4-6",
    system="<minimal role + output contract>",
    messages=[{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", ...}},
            {"type": "text",  "text": thread_to_prompt(events)}
        ]
    }]
)
        │
        ▼
Claude response: XML string matching <audit_report> schema
        │
        ▼
xml_parser.parse(response) ──► AuditReport dataclass
        │                        (inventory, structure_observation,
        │                         tier1_findings, tier2_findings,
        │                         tier3_findings, tier4_findings)
        │
        ▼
scorer.compute(audit_report) ──► per-tier star ratings + overall score
        │
        ▼
report_renderer.render(audit_report, scores) ──► Markdown string
        │
        ▼
Return Markdown string to calling agent
```

### Context Assembly (XML thread format)

`prompt_builder.py` does not concatenate strings. It assembles a **context thread**: a list of typed event objects, each serialized to an XML-tagged block, joined into a single user message. This follows the "own your context window" principle — every piece of context is a named, structured block the model can locate and reason about independently.

**Canonical block ordering (must be preserved):**
1. `<analysis_request>` — parameters including viewport dimensions
2. `<axe_core_result>` — if available; OR `<axe_unavailable>` — if axe-core failed
3. `<rubric_tier1>`
4. `<rubric_tier2>`
5. `<rubric_tier3>`
6. `<rubric_tier4>`
7. `<output_schema>`
8. Image attached as vision content

#### Event model

```python
from dataclasses import dataclass
from typing import Literal, Any
import yaml

EventType = Literal[
    "analysis_request",
    "image_source",
    "axe_core_result",
    "axe_unavailable",   # injected when axe-core fails; tells Claude it is in estimated mode
    "rubric_tier1",
    "rubric_tier2",
    "rubric_tier3",
    "rubric_tier4",
    "error",
]

@dataclass
class ContextEvent:
    type: EventType
    data: Any  # dataclass or plain dict — serialized to YAML inside the tag

def event_to_xml(event: ContextEvent) -> str:
    body = event.data if isinstance(event.data, str) else yaml.dump(event.data, default_flow_style=False).strip()
    return f"<{event.type}>\n{body}\n</{event.type}>"

def thread_to_prompt(events: list[ContextEvent]) -> str:
    blocks = "\n\n".join(event_to_xml(e) for e in events)
    return f"Here is everything known about this analysis task:\n\n{blocks}\n\nWhat is the complete audit report?"
```

#### System prompt

The system prompt is a **named constant** defined in `ui_analyzer/prompts.py:SYSTEM_PROMPT`. It must not be assembled inline inside `prompt_builder.py` or any other module. Storing it as a standalone constant makes it diffable, testable, and independently iterable without touching pipeline logic.

The system prompt is minimal — it states the role and the output contract only. All context (rubric definitions, axe data, image, request parameters) is injected as XML blocks in the user message, not embedded in the system prompt.

**Critical rule:** Claude must not compute numeric scores, star ratings, or weighted totals. All scoring arithmetic is performed deterministically by `scorer.py`. The system prompt must reinforce this explicitly.

```
You are a senior UI/UX auditor with deep expertise in accessibility,
Gestalt design principles, and Nielsen's heuristics. You analyze
static screenshots of web UIs and produce structured audit reports.

Follow the analysis protocol defined in the <rubric_*> blocks in the user message.
Apply steps in order: inventory → structure → rubric. Do not skip steps.
Only score what is visible in the screenshot. Never score interactivity,
keyboard behavior, screen reader behavior, or anything requiring a live session.

Do not compute numeric scores, star ratings, or weighted averages.
Output raw findings only — scoring is handled by the calling system.

Respond with well-formed XML matching the schema in <output_schema>.
```

The rubric tier definitions in `rubric/tier*.py` must export **named constants** (e.g. `TIER1_DEFINITION`, `TIER2_DEFINITION`) — not dynamically generated strings — so they are independently testable and diffable.

#### Rubric blocks (one XML block per tier)

Each tier is its own `ContextEvent` so tiers can be updated, reordered, or omitted independently.

```xml
<rubric_tier1>
protocol: "WCAG 2.1 AA"
scoring: "binary — Pass / Fail per check"
source_note: "If <axe_core_result> is present, use those values directly. Do not re-estimate. If absent, estimate visually and mark every finding ESTIMATED."
checks:
  - id: wcag_1_4_3_normal
    criterion: "1.4.3"
    description: "Text contrast ratio (normal text)"
    threshold: ">=4.5:1"
  - id: wcag_1_4_3_large
    criterion: "1.4.3"
    description: "Text contrast ratio (large text >=18px or 14px bold)"
    threshold: ">=3:1"
  - id: wcag_1_4_11
    criterion: "1.4.11"
    description: "UI component / non-text contrast"
    threshold: ">=3:1"
  - id: wcag_2_5_8
    criterion: "2.5.8"
    description: "Touch targets"
    threshold: ">=24px min, >=44px recommended"
  - id: body_text_size
    criterion: "advisory"
    description: "Body text size"
    threshold: ">=16px recommended"
  - id: wcag_1_4_1
    criterion: "1.4.1"
    description: "Color as sole meaning conveyor"
    threshold: "must not be sole indicator"
  - id: wcag_2_4_7
    criterion: "2.4.7"
    description: "Focus indicators"
    threshold: "flag only if focus state is visible in screenshot"
</rubric_tier1>

<rubric_tier2>
protocol: "Gestalt principles + CRAP design principles"
scoring: "severity 1 (minor) / 2 (notable) / 3 (critical)"
instruction: "Cite the specific element name and location for each finding."
principles:
  - proximity: "Related elements grouped; unrelated elements separated"
  - similarity: "Interactive elements share consistent visual treatment"
  - figure_ground: "Primary content has sufficient contrast against background"
  - alignment: "Elements align to shared axes / consistent grid"
  - contrast_crap: "Visual weight maps to functional importance"
  - repetition: "Consistent patterns for buttons, spacing, type scale across the frame"
</rubric_tier2>

<rubric_tier3>
protocol: "Nielsen heuristics #4, #6, #8 + Norman affordance model + cognitive load theory"
scoring: "severity 1 (minor) / 2 (notable) / 3 (critical)"
instruction: "Tag each finding with the nearest Nielsen heuristic number. Only evaluate heuristics observable in a static screenshot."
criteria:
  - id: consistency
    source: "Nielsen #4"
    description: "Button styles, color roles, terminology consistent within visible screen"
  - id: recognition_over_recall
    source: "Nielsen #6"
    description: "Options and actions visible; user does not need to memorize"
  - id: aesthetic_minimalist
    source: "Nielsen #8"
    description: "No visual noise; every element earns its presence"
  - id: norman_signifiers
    source: "Norman"
    description: "Buttons look clickable, inputs look fillable, links are distinguishable"
  - id: cognitive_load
    source: "CLT"
    description: "Density appropriate; content chunked into scannable units; no competing focal points"
  - id: visual_hierarchy
    source: "general"
    description: "One dominant CTA; heading levels proportional; attention flow clear"
</rubric_tier3>
```

Tier 4 block is generated dynamically by the active domain module (e.g. `rubric/tier4/web_dashboard.py`) and serialized as `<rubric_tier4>`.

#### axe-core injection (URL mode)

When axe-core data is available it is added as a dedicated `ContextEvent` — not inlined into the rubric or the image message:

```xml
<axe_core_result>
source: "axe-core — authoritative, do not re-estimate"
findings:
  - criterion: "1.4.3"
    violations:
      - element: ".nav-link"
        ratio: 2.8
        required: 4.5
        result: FAIL
      - element: ".btn-secondary"
        ratio: 3.2
        required: 4.5
        result: FAIL
      - element: ".footer-text"
        ratio: 4.6
        required: 4.5
        result: PASS
  - criterion: "1.4.11"
    violations: []
    result: PASS
  - criterion: "2.5.8"
    violations:
      - element: "#mobile-menu-btn"
        size_px: "18x18"
        required_px: "24x24"
        result: FAIL
  - criterion: "1.4.1"
    violations: []
    result: PASS
</axe_core_result>
```

#### axe_unavailable block (injected when axe-core fails)

When axe-core fails but Playwright succeeded, inject this event **instead of** `<axe_core_result>` so Claude knows it is operating in degraded mode and must caveat all Tier 1 findings:

```xml
<axe_unavailable>
reason: "axe-core JS injection failed"
tier1_mode: "estimated"
instruction: "You do not have authoritative WCAG data. Base all Tier 1 findings on visual estimation only. Mark every Tier 1 finding as ESTIMATED and recommend manual verification."
</axe_unavailable>
```

#### analysis_request block

```xml
<analysis_request>
app_type: "web_dashboard"
image_source_type: "url"
image_source_value: "https://example.com/dashboard"
tier1_mode: "authoritative"  # or "estimated" when no axe_core_result present
viewport_width: 1280
viewport_height: 800
</analysis_request>
```

#### output_schema block

Claude is asked to respond in structured XML so `scorer.py` and `report_renderer.py` parse structured data rather than raw text:

```xml
<output_schema>
Respond with the following XML structure. Do not add prose outside these tags.

<audit_report>
  <confidence level="high|medium|low">
    <!-- Optional reason if medium or low, e.g. "screenshot resolution too low to assess contrast ratios" -->
  </confidence>
  <inventory>
    <!-- Step 1: list every interactive element with label, size, color, position -->
  </inventory>
  <structure_observation>
    <!-- Step 2: layout, columns, type scale, color palette -->
  </structure_observation>
  <tier1_findings>
    <finding criterion="1.4.3" element=".nav-link" result="FAIL" estimated="false">
      <observed>contrast ratio 2.8:1</observed>
      <required>4.5:1 for normal text</required>
      <recommendation>Change text color to #374151 (ratio: 7.6:1)</recommendation>
    </finding>
    <!-- ... -->
  </tier1_findings>
  <tier2_findings>
    <finding principle="proximity" severity="2" element="Metric cards (top row)">
      <issue>Cards have 4px gap but no separator from filter row above; groups blend.</issue>
      <recommendation>Increase gap between filter bar and metric cards to 24px.</recommendation>
      <nielsen_tag>4</nielsen_tag>
    </finding>
    <!-- ... -->
  </tier2_findings>
  <tier3_findings>
    <!-- same structure as tier2_findings, include nielsen_tag -->
  </tier3_findings>
  <tier4_findings>
    <finding pattern="data_ink_ratio" element="Sidebar navigation">
      <issue>6 decorative icons with no text labels at collapsed width; requires memorization.</issue>
      <recommendation>Add persistent text labels or expand sidebar by default.</recommendation>
    </finding>
    <!-- ... -->
  </tier4_findings>
</audit_report>
</output_schema>
```

#### Full assembled user message (URL mode, example)

```
Here is everything known about this analysis task:

<analysis_request>
app_type: "web_dashboard"
image_source_type: "url"
image_source_value: "https://example.com/dashboard"
tier1_mode: "authoritative"
</analysis_request>

<axe_core_result>
... (as above)
</axe_core_result>

<rubric_tier1>
... (as above)
</rubric_tier1>

<rubric_tier2>
... (as above)
</rubric_tier2>

<rubric_tier3>
... (as above)
</rubric_tier3>

<rubric_tier4>
... (generated by active domain module)
</rubric_tier4>

<output_schema>
... (as above)
</output_schema>

[image attached as vision content]

What is the complete audit report?
```

`scorer.py` and `report_renderer.py` receive a parsed `AuditReport` dataclass (parsed from Claude's XML response), not raw text.

### Scoring Computation

```python
def compute_tier1_stars(findings: list[dict]) -> float:
    """% of Tier 1 checks that passed, mapped to 1–5 stars."""
    passes = sum(1 for f in findings if f["severity"] == "Pass")
    total = len(findings)
    ratio = passes / total if total > 0 else 1.0
    # 100% = 5★, 80% = 4★, 60% = 3★, 40% = 2★, <40% = 1★
    return max(1.0, round(ratio * 5, 1))

def compute_tier23_stars(findings: list[dict]) -> float:
    """Avg severity of findings, inverted to stars."""
    if not findings:
        return 5.0
    severities = [f["severity"] for f in findings if isinstance(f["severity"], int)]
    avg = sum(severities) / len(severities) if severities else 0
    # avg 0 = 5★, avg 1 = 4★, avg 2 = 2.5★, avg 3 = 1★
    return max(1.0, 5.0 - (avg * 1.5))

def compute_overall(t1: float, t2: float, t3: float) -> float:
    """Weighted overall. Tier 1 weighted highest (accessibility is non-negotiable)."""
    return round((t1 * 0.4) + (t2 * 0.35) + (t3 * 0.25), 1)
    # Tier 4 is flags only — not included in numerical score
```

### Report Output Structure

```markdown
# UI Analysis Report

**App type:** web_dashboard  
**Input:** https://example.com/dashboard  
**Tier 1 mode:** Authoritative (axe-core)  
**Model:** claude-sonnet-4-6  

---

## Overall Score: ★★★☆☆ (3.1 / 5)

| Tier | Score | Weight |
|------|-------|--------|
| Tier 1 — Accessibility | ★★★☆☆ | 40% |
| Tier 2 — Visual Structure | ★★★★☆ | 35% |
| Tier 3 — Usability | ★★★★★ | 25% |
| Tier 4 — Domain Patterns | 2 flags | — |

---

## Tier 1 — Accessibility (WCAG 2.1 AA)

**Observed:**
- Nav link text #6B7280 on #FFFFFF background
- Secondary button text #9CA3AF on #F3F4F6
- Mobile menu button: 18×18px

**Findings:**

❌ **FAIL** — WCAG 1.4.3  
Element: `.nav-link` — text contrast  
Issue: Contrast ratio 2.8:1 (required 4.5:1 for normal text)  
Recommendation: Change text color to #374151 (ratio: 7.6:1)

❌ **FAIL** — WCAG 2.5.8  
Element: `#mobile-menu-btn`  
Issue: Touch target 18×18px (minimum 24×24px required)  
Recommendation: Increase to at least 24×24px, ideally 44×44px

✅ **PASS** — WCAG 1.4.1  
No information conveyed by color alone.

---

## Tier 2 — Visual Structure (Gestalt / CRAP)

**Observed:**
[Step 1 + 2 inventory appears here]

**Findings:**

⚠️ **Severity 2** — Proximity  
Element: Metric cards (top row)  
Issue: Cards have 4px gap between them but no visual separator from the filter row above; the two groups blend together.  
Recommendation: Increase gap between filter bar and metric cards to 24px.  
Nielsen tag: #4

---

## Tier 3 — Usability & Affordance

...

---

## Tier 4 — Domain Patterns (web_dashboard)

🚩 **Flag** — Data-ink ratio  
Element: Sidebar navigation  
Issue: 6 decorative icons present with no text labels visible at collapsed width; icon-only navigation requires memorization.  
Recommendation: Add persistent text labels or expand sidebar by default.

---

*Generated by ui-analyzer v1 using claude-sonnet-4-6*
```

---

## Edge Cases & Error Handling

This table is authoritative. All behavior described here overrides any code sketch above.

| Scenario | Input | Expected behavior |
|----------|-------|------------------|
| URL returns 404 | `image_source="https://example.com/404"` | Raise `UIAnalyzerError("Could not load URL: HTTP 404. Provide a screenshot file path instead.")` |
| URL times out (>30s) | Playwright timeout | Raise `UIAnalyzerError("URL did not load within 30s. Provide a screenshot file path instead.")` |
| URL loads but JS-heavy SPA renders blank | Playwright captures blank/spinner | Raise `UIAnalyzerError("Page rendered no visible content. Provide a screenshot file path instead.")` |
| File path does not exist | `image_source="/tmp/missing.png"` | Raise `UIAnalyzerError("File not found: /tmp/missing.png")` |
| File is not a supported image type | `.pdf`, `.svg`, `.gif > 1 frame` | Raise `UIAnalyzerError("Unsupported file type. Accepted: PNG, JPG, JPEG, WebP.")` |
| Image does not appear to be a UI | Photo, document scan, blank image | Claude returns report with preamble: `"⚠️ The provided image does not appear to be a web UI screenshot. Analysis may not be meaningful."` — continues with best-effort analysis rather than erroring. |
| axe-core fails but Playwright succeeds | axe JS injection error | Log warning; inject `<axe_unavailable>` ContextEvent so Claude knows to caveat Tier 1 findings; proceed with screenshot-only analysis. Do not hard-fail. |
| Claude returns malformed/incomplete analysis | Missing tiers in `<audit_report>` XML | `xml_parser.py` returns an `AuditReport` with empty findings lists for missing tiers. `scorer.py` scores missing tiers as N/A. `handler.py` returns a Markdown string (not an exception) with available tiers rendered and a `⚠️ Claude returned a malformed response — some tiers may be missing` warning appended. |
| Claude API call exceeds timeout | No response within 60s | Raise `UIAnalyzerError("Anthropic API call timed out after 60s.")` |
| axe-core execution exceeds timeout | No result within 10s | Log warning; inject `<axe_unavailable reason="axe-core timed out">` and proceed in estimated mode. Do not hard-fail. |
| Image too large for Claude context | >8000×8000 or >20MB | Pillow resizes to max 1568px on longest edge before sending to Claude. |
| `app_type` not in enum | Invalid string | Pydantic validation raises before any API call: `"app_type must be one of: web_dashboard, landing_page, onboarding_flow, forms"` |
| Anthropic API key missing | `ANTHROPIC_API_KEY` not set | Raise `UIAnalyzerError("ANTHROPIC_API_KEY environment variable not set.")` at import time. |
| Claude API rate limit / 529 | Anthropic returns 529 | Raise `UIAnalyzerError("Anthropic API rate limit hit. Retry after a moment.")` — no internal retry in v1. |

---

## Constraints & Invariants

1. **Screenshot-only analysis.** The tool must never attempt to fetch or parse source code, CSS, or DOM. If a URL is provided, Playwright is used only for screenshot capture and axe-core execution — not HTML inspection.

2. **No hallucinated findings.** The system prompt explicitly prohibits scoring any criterion not observable in the static screenshot. The chain-of-thought (Steps 1–2) must precede any rubric application (Step 3).

3. **Tier 1 source transparency.** Every Tier 1 finding in the report must state whether it is "Authoritative (axe-core)" or "ESTIMATED — verify manually". This is non-negotiable.

4. **No auto-fixing in v1.** The tool returns analysis only. It must not modify any file, URL, or external resource.

5. **WCAG criterion always cited.** Every Tier 1 finding must reference the specific WCAG 2.1 AA criterion (e.g., "WCAG 1.4.3"), not just "accessibility".

6. **Only observable Nielsen heuristics evaluated.** Heuristics that require live interaction (error prevention, undo, system status feedback) must never appear in Tier 3 findings.

7. **Tier 4 is flags only.** Domain-specific findings never carry a severity number or contribute to the star score.

8. **Image resized before Claude call.** Any image exceeding 1568px on its longest edge is resized by Pillow before being sent. Original file is never modified.

9. **Return type contract.** `analyze_ui_screenshot()` always returns a `str` (Markdown report) on success or degraded completion. It raises `UIAnalyzerError` only on hard failures (URL load failure, missing API key, unsupported file type). It never raises on axe-core failure, malformed XML, or partial Claude output — those produce degraded reports with embedded warnings.

10. **Playwright browser lifecycle.** A new Playwright browser instance is launched and closed for each `analyze_ui_screenshot()` call. Shared browser instances across calls are not permitted — cross-call state isolation (cookies, cached pages, session state) is required. Each call uses an isolated browser context.

11. **Concurrency.** Concurrent calls to `analyze_ui_screenshot()` are supported. Each call creates its own isolated Playwright browser and context. No shared mutable state exists between concurrent invocations.

12. **Prompt and rubric as named constants.** The system prompt lives in `ui_analyzer/prompts.py:SYSTEM_PROMPT`. Each rubric tier module exports a named constant (`TIER1_DEFINITION`, etc.). Neither may be assembled dynamically inside `prompt_builder.py`.

---

## Testing Strategy

### Unit Tests

| Test | What it covers |
|------|---------------|
| `test_image_source_url` | URL input sets mode=URL, returns screenshot bytes |
| `test_image_source_file` | Valid file path loads bytes, sets mode=FILE |
| `test_image_source_missing_file` | Missing path raises `UIAnalyzerError` |
| `test_image_source_bad_ext` | Unsupported extension raises `UIAnalyzerError` |
| `test_context_event_to_xml` | `event_to_xml()` wraps data in correct XML tag; YAML body is well-formed |
| `test_thread_to_prompt_ordering` | `thread_to_prompt()` emits events in declared order; ends with "What is the complete audit report?" |
| `test_prompt_builder_with_axe_data` | `build_thread()` includes `<axe_core_result>` block when axe data provided; `tier1_mode` is "authoritative" |
| `test_prompt_builder_no_axe_data` | `build_thread()` omits `<axe_core_result>` block when axe data is None; `tier1_mode` is "estimated" |
| `test_xml_parser_full_response` | Well-formed `<audit_report>` XML → populated `AuditReport` dataclass |
| `test_xml_parser_missing_tier` | `<audit_report>` with a missing tier block → that tier's findings list is empty, no exception |
| `test_xml_parser_malformed_xml` | Non-XML or truncated response → `scorer.py` receives `AuditReport` with all findings empty, report renders warning |
| `test_scorer_tier1_all_pass` | 100% pass → 5 stars |
| `test_scorer_tier1_mixed` | 60% pass → 3 stars |
| `test_scorer_tier23_no_findings` | No findings → 5 stars |
| `test_scorer_tier23_critical` | All severity-3 → 1 star |
| `test_scorer_overall_weighting` | T1=5, T2=3, T3=4 → 3.85 weighted |
| `test_image_resize` | Image >1568px longest side gets resized |
| `test_prompt_builder_axe_failure` | When axe-core fails, `build_thread()` includes `<axe_unavailable>` block (not `<axe_core_result>`); `tier1_mode` is "estimated" |
| `test_context_event_ordering` | `build_thread()` emits events in canonical order: analysis_request → axe block → tier1 → tier2 → tier3 → tier4 → output_schema |
| `test_analysis_request_includes_viewport` | `<analysis_request>` block contains `viewport_width` and `viewport_height` fields |
| `test_system_prompt_structure` | `SYSTEM_PROMPT` constant contains the three phase markers ("inventory", "structure", "rubric") and the no-scoring instruction |
| `test_handler_returns_string_on_malformed_xml` | When `xml_parser.parse()` fails, `handler.py` returns a `str` containing the malformed-response warning (does not raise) |

### Integration Tests (require Anthropic API key)

| Test | What it covers |
|------|---------------|
| `test_full_analysis_file_path` | Fixture screenshot → valid Markdown report with all 4 tier sections |
| `test_full_analysis_url` | Live URL (use stable test URL) → Tier 1 shows "Authoritative" mode |
| `test_non_ui_image` | Fixture photo → report contains ⚠️ non-UI warning, doesn't error |
| `test_app_type_forms` | Forms screenshot → Tier 4 contains forms-specific flags |

### Fixtures

Provide at minimum:
- `fixtures/dashboard_good.png` — clean SaaS dashboard (few expected issues)
- `fixtures/dashboard_bad.png` — dense, low-contrast dashboard (many expected issues)
- `fixtures/landing_page.png` — marketing page
- `fixtures/form.png` — multi-field form
- `fixtures/not_a_ui.jpg` — photograph (for non-UI edge case)

---

## Open Questions

1. **Playwright viewport for URL capture** — Default is **1280×800 (desktop)**. Viewport dimensions are always captured and included in the `<analysis_request>` ContextEvent so Claude can calibrate touch target and layout scoring. A `viewport` parameter for mobile capture is a v2 candidate.

2. **axe-core rule set** — axe-core supports different rule sets (`wcag2a`, `wcag2aa`, `wcag21aa`, `best-practice`). v1 should use `wcag21aa`. Worth documenting in case the rule set needs to be expanded later.

3. **Report language** — All output is in English in v1. Multi-language output is not scoped.

4. **Caller authentication** — The tool definition itself has no auth. Auth is the responsibility of the agent/host that registers the tool. Not in scope for v1.

5. **Rate of image analysis per session** — Claude context window allows up to 100 images. Multi-call sessions (e.g., analyzing 20 screens) will accumulate cost quickly. A cost estimate utility may be worth adding in v2.

---

*Spec authored: 2026-04-15. Implementing agent should cross-check all edge cases in the Edge Cases table against the Technical Design code sketches before writing code.*
