# Spec 04 — Rubric Definitions

**Parent spec:** spec--2026-04-15--15-30--ui-screenshot-analyzer.md  
**Status:** Ready for implementation  
**Depends on:** Spec 01 (package scaffold only)  
**Blocks:** Spec 05 (prompt builder imports these constants)

---

## Goal

Implement all rubric definition modules under `ui_analyzer/rubric/`. Each module exports a named constant that `prompt_builder.py` serializes into the corresponding XML block in the user message.

These constants are **static data** — they are not generated dynamically, not configurable at runtime, and not assembled inside `prompt_builder.py`. They live here so they are independently diffable, testable, and iterable without touching pipeline logic.

---

## Scope

Files created by this spec:

```
ui_analyzer/
└── rubric/
    ├── __init__.py          ← empty
    ├── tier1.py             ← TIER1_DEFINITION
    ├── tier2.py             ← TIER2_DEFINITION
    ├── tier3.py             ← TIER3_DEFINITION
    ├── output_schema.py     ← OUTPUT_SCHEMA_XML (a raw string, not YAML)
    └── tier4/
        ├── __init__.py      ← empty
        ├── web_dashboard.py ← TIER4_DEFINITION
        ├── landing_page.py  ← TIER4_DEFINITION
        ├── onboarding_flow.py ← TIER4_DEFINITION
        └── forms.py         ← TIER4_DEFINITION
```

All Tier 1–3 constants are Python dicts. All Tier 4 constants are also Python dicts. `output_schema.py` exports a raw XML string constant.

---

## tier1.py

```python
TIER1_DEFINITION = {
    "protocol": "WCAG 2.1 AA",
    "scoring": "binary — Pass / Fail per check",
    "source_note": (
        "If <axe_core_result> is present, use those values directly. "
        "Do not re-estimate. If absent, estimate visually and mark every finding ESTIMATED."
    ),
    "checks": [
        {
            "id": "wcag_1_4_3_normal",
            "criterion": "1.4.3",
            "description": "Text contrast ratio (normal text)",
            "threshold": ">=4.5:1",
        },
        {
            "id": "wcag_1_4_3_large",
            "criterion": "1.4.3",
            "description": "Text contrast ratio (large text >=18px or 14px bold)",
            "threshold": ">=3:1",
        },
        {
            "id": "wcag_1_4_11",
            "criterion": "1.4.11",
            "description": "UI component / non-text contrast",
            "threshold": ">=3:1",
        },
        {
            "id": "wcag_2_5_8",
            "criterion": "2.5.8",
            "description": "Touch targets",
            "threshold": ">=24px min, >=44px recommended",
        },
        {
            "id": "body_text_size",
            "criterion": "advisory",
            "description": "Body text size",
            "threshold": ">=16px recommended",
        },
        {
            "id": "wcag_1_4_1",
            "criterion": "1.4.1",
            "description": "Color as sole meaning conveyor",
            "threshold": "must not be sole indicator",
        },
        {
            "id": "wcag_2_4_7",
            "criterion": "2.4.7",
            "description": "Focus indicators",
            "threshold": "flag only if focus state is visible in screenshot",
        },
    ],
}
```

---

## tier2.py

```python
TIER2_DEFINITION = {
    "protocol": "Gestalt principles + CRAP design principles",
    "scoring": "severity 1 (minor) / 2 (notable) / 3 (critical)",
    "instruction": "Cite the specific element name and location for each finding.",
    "principles": [
        {"proximity": "Related elements grouped; unrelated elements separated"},
        {"similarity": "Interactive elements share consistent visual treatment"},
        {"figure_ground": "Primary content has sufficient contrast against background"},
        {"alignment": "Elements align to shared axes / consistent grid"},
        {"contrast_crap": "Visual weight maps to functional importance"},
        {"repetition": "Consistent patterns for buttons, spacing, type scale across the frame"},
    ],
}
```

---

## tier3.py

```python
TIER3_DEFINITION = {
    "protocol": "Nielsen heuristics #4, #6, #8 + Norman affordance model + cognitive load theory",
    "scoring": "severity 1 (minor) / 2 (notable) / 3 (critical)",
    "instruction": (
        "Tag each finding with the nearest Nielsen heuristic number. "
        "Only evaluate heuristics observable in a static screenshot."
    ),
    "criteria": [
        {
            "id": "consistency",
            "source": "Nielsen #4",
            "description": "Button styles, color roles, terminology consistent within visible screen",
        },
        {
            "id": "recognition_over_recall",
            "source": "Nielsen #6",
            "description": "Options and actions visible; user does not need to memorize",
        },
        {
            "id": "aesthetic_minimalist",
            "source": "Nielsen #8",
            "description": "No visual noise; every element earns its presence",
        },
        {
            "id": "norman_signifiers",
            "source": "Norman",
            "description": "Buttons look clickable, inputs look fillable, links are distinguishable",
        },
        {
            "id": "cognitive_load",
            "source": "CLT",
            "description": "Density appropriate; content chunked into scannable units; no competing focal points",
        },
        {
            "id": "visual_hierarchy",
            "source": "general",
            "description": "One dominant CTA; heading levels proportional; attention flow clear",
        },
    ],
}
```

---

## Tier 4 modules

Each Tier 4 module exports `TIER4_DEFINITION`. The `app_type` field in each dict matches the enum value that activates it.

### tier4/web_dashboard.py

```python
TIER4_DEFINITION = {
    "app_type": "web_dashboard",
    "scoring": "Flag only — no severity score. Not included in numerical score.",
    "patterns": [
        {
            "id": "data_ink_ratio",
            "description": "Data-ink ratio: chart elements should serve data, not decoration",
        },
        {
            "id": "metric_hierarchy",
            "description": "Metric hierarchy: key KPIs visually dominant over secondary metrics",
        },
        {
            "id": "chart_type_appropriateness",
            "description": "Chart type appropriateness: chart type matches the data relationship shown",
        },
    ],
}
```

### tier4/landing_page.py

```python
TIER4_DEFINITION = {
    "app_type": "landing_page",
    "scoring": "Flag only — no severity score. Not included in numerical score.",
    "patterns": [
        {
            "id": "z_pattern_cta",
            "description": "Z-pattern CTA alignment: primary CTA placed at expected Z-path endpoint",
        },
        {
            "id": "above_fold_headline",
            "description": "Above-fold headline clarity: value proposition legible without scrolling",
        },
        {
            "id": "trust_signal_placement",
            "description": "Trust signal placement: logos, testimonials, or social proof near primary CTA",
        },
    ],
}
```

### tier4/onboarding_flow.py

```python
TIER4_DEFINITION = {
    "app_type": "onboarding_flow",
    "scoring": "Flag only — no severity score. Not included in numerical score.",
    "patterns": [
        {
            "id": "step_progression",
            "description": "Step progression clarity: current step position in flow is unambiguous",
        },
        {
            "id": "primary_action_prominence",
            "description": "Primary action prominence: next/continue action is the most prominent element",
        },
        {
            "id": "progress_indicator",
            "description": "Progress indicator visibility: user can see how far along they are",
        },
    ],
}
```

### tier4/forms.py

```python
TIER4_DEFINITION = {
    "app_type": "forms",
    "scoring": "Flag only — no severity score. Not included in numerical score.",
    "patterns": [
        {
            "id": "label_placement",
            "description": "Label-above-field placement: labels positioned above inputs, not beside or as placeholders",
        },
        {
            "id": "error_proximity",
            "description": "Inline error proximity: error messages appear directly below the relevant field",
        },
        {
            "id": "required_field_marking",
            "description": "Required field marking: required fields are consistently marked (e.g. asterisk with legend)",
        },
    ],
}
```

---

## output_schema.py

This exports a raw XML string. It is NOT serialized to YAML — it is injected verbatim as the `<output_schema>` block body.

```python
OUTPUT_SCHEMA_XML = """\
Respond with the following XML structure. Do not add prose outside these tags.

<audit_report>
  <confidence level="high|medium|low">
    <!-- Optional reason if medium or low -->
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
  </tier1_findings>
  <tier2_findings>
    <finding principle="proximity" severity="2" element="Metric cards (top row)">
      <issue>Cards have 4px gap but no separator from filter row above; groups blend.</issue>
      <recommendation>Increase gap between filter bar and metric cards to 24px.</recommendation>
      <nielsen_tag>4</nielsen_tag>
    </finding>
  </tier2_findings>
  <tier3_findings>
    <!-- same structure as tier2_findings, include nielsen_tag -->
  </tier3_findings>
  <tier4_findings>
    <finding pattern="data_ink_ratio" element="Sidebar navigation">
      <issue>6 decorative icons with no text labels at collapsed width; requires memorization.</issue>
      <recommendation>Add persistent text labels or expand sidebar by default.</recommendation>
    </finding>
  </tier4_findings>
</audit_report>"""
```

---

## Tier 4 Dispatch

The handler (Spec 08) imports the correct Tier 4 module based on `app_type`. The rubric package does not do the dispatch — it just exports constants.

```python
# In handler.py (Spec 08):
from ui_analyzer.rubric.tier4 import web_dashboard, landing_page, onboarding_flow, forms

TIER4_MODULES = {
    "web_dashboard": web_dashboard.TIER4_DEFINITION,
    "landing_page": landing_page.TIER4_DEFINITION,
    "onboarding_flow": onboarding_flow.TIER4_DEFINITION,
    "forms": forms.TIER4_DEFINITION,
}
```

---

## Constraints

- All constants are defined at module level. No function returns them. No dynamic generation.
- `OUTPUT_SCHEMA_XML` is a string constant, not a dict. It is injected verbatim, not serialized via YAML.
- Tier 4 modules are all in `rubric/tier4/` and all export the same name: `TIER4_DEFINITION`.
- Adding or modifying a tier definition never requires touching `prompt_builder.py`.

---

## Success Criteria

- [ ] All 9 modules (`tier1`, `tier2`, `tier3`, `output_schema`, 4× tier4) import without errors
- [ ] `TIER1_DEFINITION["checks"]` has exactly 7 entries matching the rubric in the parent spec
- [ ] `OUTPUT_SCHEMA_XML` contains the `<audit_report>` root tag and all 6 child tags
- [ ] Each Tier 4 module's `TIER4_DEFINITION["app_type"]` matches its enum value
- [ ] No Tier 4 module has a `scoring` field with a numeric severity — flags only
