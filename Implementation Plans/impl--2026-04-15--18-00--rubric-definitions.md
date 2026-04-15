# Implementation Plan: Rubric Definitions

## Header
- **Spec**: specs/applied/spec-04-rubric-definitions.md  ← moved here after planning
- **Worktree**: `/mnt/c/Users/Epkone/UXIQ-spec-04`  (branch: `spec-04-rubric-definitions`)
- **Scope — files in play** (agent must not touch files not listed here):
  - `ui-analyzer/ui_analyzer/rubric/__init__.py`
  - `ui-analyzer/ui_analyzer/rubric/tier1.py`
  - `ui-analyzer/ui_analyzer/rubric/tier2.py`
  - `ui-analyzer/ui_analyzer/rubric/tier3.py`
  - `ui-analyzer/ui_analyzer/rubric/output_schema.py`
  - `ui-analyzer/ui_analyzer/rubric/tier4/__init__.py`
  - `ui-analyzer/ui_analyzer/rubric/tier4/web_dashboard.py`
  - `ui-analyzer/ui_analyzer/rubric/tier4/landing_page.py`
  - `ui-analyzer/ui_analyzer/rubric/tier4/onboarding_flow.py`
  - `ui-analyzer/ui_analyzer/rubric/tier4/forms.py`
- **Reading list** (read these before starting, nothing else):
  1. `ui-analyzer/ui_analyzer/__init__.py` — verify package root
  2. `ui-analyzer/pyproject.toml` — confirm dev deps (pytest, pytest-asyncio) are declared

## Environment Assumptions Verified

- `pytest>=8.0` and `pytest-asyncio>=0.23` are declared in `pyproject.toml` under `[project.optional-dependencies] dev`. Verified in this session from `/mnt/c/Users/Epkone/UXIQ/ui-analyzer/pyproject.toml`.
- `asyncio_mode = "auto"` is set in `[tool.pytest.ini_options]`. The rubric modules are pure sync — no asyncio is involved; this setting has no impact here.
- All new files are **greenfield** — no existing baseline to verify. The `rubric/` directory does not exist.
- The package is installed editable; after creating the files, `python -c "from ui_analyzer.rubric import ..."` will work without reinstall.

---

## Steps

### Step 1: Create `ui_analyzer/rubric/__init__.py`
**File**: `ui-analyzer/ui_analyzer/rubric/__init__.py`  
**Action**: Create new empty file (marks directory as a Python package)

**Content**:
```python
```
(Empty file — zero bytes.)

**Verification**: File exists at the path above.

---

### Step 2: Create `ui_analyzer/rubric/tier1.py`
**File**: `ui-analyzer/ui_analyzer/rubric/tier1.py`  
**Action**: Create new file with `TIER1_DEFINITION` constant

**Content**:
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

**Verification**: `len(TIER1_DEFINITION["checks"]) == 7`

---

### Step 3: Create `ui_analyzer/rubric/tier2.py`
**File**: `ui-analyzer/ui_analyzer/rubric/tier2.py`  
**Action**: Create new file with `TIER2_DEFINITION` constant

**Content**:
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

**Verification**: `len(TIER2_DEFINITION["principles"]) == 6`

---

### Step 4: Create `ui_analyzer/rubric/tier3.py`
**File**: `ui-analyzer/ui_analyzer/rubric/tier3.py`  
**Action**: Create new file with `TIER3_DEFINITION` constant

**Content**:
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

**Verification**: `len(TIER3_DEFINITION["criteria"]) == 6`

---

### Step 5: Create `ui_analyzer/rubric/output_schema.py`
**File**: `ui-analyzer/ui_analyzer/rubric/output_schema.py`  
**Action**: Create new file with `OUTPUT_SCHEMA_XML` string constant

**Content**:
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

**Verification**:
- `"<audit_report>" in OUTPUT_SCHEMA_XML` is True
- All 6 child tags are present: `confidence`, `inventory`, `structure_observation`, `tier1_findings`, `tier2_findings`, `tier3_findings`, `tier4_findings`

---

### Step 6: Create `ui_analyzer/rubric/tier4/__init__.py`
**File**: `ui-analyzer/ui_analyzer/rubric/tier4/__init__.py`  
**Action**: Create new empty file (marks subdirectory as a Python package)

**Content**: (Empty file — zero bytes.)

**Verification**: File exists at the path above.

---

### Step 7: Create `ui_analyzer/rubric/tier4/web_dashboard.py`
**File**: `ui-analyzer/ui_analyzer/rubric/tier4/web_dashboard.py`  
**Action**: Create new file with `TIER4_DEFINITION` constant

**Content**:
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

**Verification**: `TIER4_DEFINITION["app_type"] == "web_dashboard"` and `len(TIER4_DEFINITION["patterns"]) == 3`

---

### Step 8: Create `ui_analyzer/rubric/tier4/landing_page.py`
**File**: `ui-analyzer/ui_analyzer/rubric/tier4/landing_page.py`  
**Action**: Create new file with `TIER4_DEFINITION` constant

**Content**:
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

**Verification**: `TIER4_DEFINITION["app_type"] == "landing_page"` and `len(TIER4_DEFINITION["patterns"]) == 3`

---

### Step 9: Create `ui_analyzer/rubric/tier4/onboarding_flow.py`
**File**: `ui-analyzer/ui_analyzer/rubric/tier4/onboarding_flow.py`  
**Action**: Create new file with `TIER4_DEFINITION` constant

**Content**:
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

**Verification**: `TIER4_DEFINITION["app_type"] == "onboarding_flow"` and `len(TIER4_DEFINITION["patterns"]) == 3`

---

### Step 10: Create `ui_analyzer/rubric/tier4/forms.py`
**File**: `ui-analyzer/ui_analyzer/rubric/tier4/forms.py`  
**Action**: Create new file with `TIER4_DEFINITION` constant

**Content**:
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

**Verification**: `TIER4_DEFINITION["app_type"] == "forms"` and `len(TIER4_DEFINITION["patterns"]) == 3`

---

### Step 11: Verify all imports succeed
**Action**: Run the following import smoke-test from inside `ui-analyzer/`:

```bash
cd /mnt/c/Users/Epkone/UXIQ-spec-04/ui-analyzer && \
ANTHROPIC_API_KEY=dummy python -c "
from ui_analyzer.rubric.tier1 import TIER1_DEFINITION
from ui_analyzer.rubric.tier2 import TIER2_DEFINITION
from ui_analyzer.rubric.tier3 import TIER3_DEFINITION
from ui_analyzer.rubric.output_schema import OUTPUT_SCHEMA_XML
from ui_analyzer.rubric.tier4.web_dashboard import TIER4_DEFINITION as T4_WD
from ui_analyzer.rubric.tier4.landing_page import TIER4_DEFINITION as T4_LP
from ui_analyzer.rubric.tier4.onboarding_flow import TIER4_DEFINITION as T4_OF
from ui_analyzer.rubric.tier4.forms import TIER4_DEFINITION as T4_F
assert len(TIER1_DEFINITION['checks']) == 7, f'Expected 7 checks, got {len(TIER1_DEFINITION[\"checks\"])}'
assert '<audit_report>' in OUTPUT_SCHEMA_XML
assert T4_WD['app_type'] == 'web_dashboard'
assert T4_LP['app_type'] == 'landing_page'
assert T4_OF['app_type'] == 'onboarding_flow'
assert T4_F['app_type'] == 'forms'
for t4 in [T4_WD, T4_LP, T4_OF, T4_F]:
    assert 'severity' not in t4['scoring'] or 'no severity' in t4['scoring'], \
        f'Tier 4 module {t4[\"app_type\"]} must not have numeric severity in scoring'
print('ALL ASSERTIONS PASSED')
"
```

Expected output: `ALL ASSERTIONS PASSED`

---

### Step 12: Run the test suite (baseline — no new tests in this spec)
**Action**: Confirm that the existing test suite still passes after adding the new package.

```bash
cd /mnt/c/Users/Epkone/UXIQ-spec-04/ui-analyzer && \
ANTHROPIC_API_KEY=dummy python -m pytest --tb=short -q 2>&1
```

If `tests/` directory does not exist yet (it is not created until spec-09), this command will report "no tests ran" — that is acceptable. The key outcome is that pytest exits without a collection error.

---

### Step 13: Commit
**Action**: Stage and commit all new files.

```bash
cd /mnt/c/Users/Epkone/UXIQ-spec-04 && \
git add ui-analyzer/ui_analyzer/rubric/ && \
git commit -m "$(cat <<'EOF'
feat: add rubric definition modules (spec-04)

Creates ui_analyzer/rubric/ with all static tier definition constants:
- TIER1_DEFINITION (WCAG 2.1 AA, 7 checks)
- TIER2_DEFINITION (Gestalt + CRAP, 6 principles)
- TIER3_DEFINITION (Nielsen + Norman + CLT, 6 criteria)
- OUTPUT_SCHEMA_XML (raw XML string for prompt injection)
- TIER4_DEFINITION in 4 app-type modules (web_dashboard, landing_page,
  onboarding_flow, forms)

These constants are static data only; no dynamic generation or runtime
configuration. Prompt builder (spec-05) imports them directly.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Post-Implementation Checklist

- [ ] All 10 files exist under `ui-analyzer/ui_analyzer/rubric/` (2 `__init__.py` + 8 modules)
- [ ] `TIER1_DEFINITION["checks"]` has exactly 7 entries
- [ ] `OUTPUT_SCHEMA_XML` is a `str`, not a `dict`, and starts with `"Respond with"`
- [ ] `OUTPUT_SCHEMA_XML` contains `<audit_report>` root tag
- [ ] All 6 child tags present in `OUTPUT_SCHEMA_XML`: `confidence`, `inventory`, `structure_observation`, `tier1_findings`, `tier2_findings`, `tier3_findings`, `tier4_findings`
- [ ] Each Tier 4 module's `TIER4_DEFINITION["app_type"]` matches its filename/enum value
- [ ] No Tier 4 module's `scoring` field contains a numeric severity scale (all must say "Flag only — no severity score")
- [ ] All 9 data modules + 2 `__init__.py` import without errors (Step 11 passes)
- [ ] `pytest` exits 0 or "no tests ran" with no collection errors (Step 12)
- [ ] Commit landed on branch `spec-04-rubric-definitions`

## Verification Approach

All verification is done via the Python interpreter — no external tools required:

1. After each `Write` step (Steps 1–10): confirm the file exists by running `python -c "import <module>"` if desired, or batch-verify in Step 11.
2. Step 11 is the canonical smoke test — run it once after all 10 files are created.
3. Step 12 is the regression guard — ensures no import side-effect breaks existing package loading.
4. If any assertion in Step 11 fails, re-read the relevant file and fix the discrepancy before committing.

**Testing strategy note**: The spec's Testing Strategy (Success Criteria) has no dedicated test files — verification is done via the import smoke-test in Step 11. Spec-09 will add the formal test suite. There is no test gap to flag: the spec explicitly defers testing to spec-09; the smoke-test in Step 11 covers every success criterion stated in the spec.

## Commit Message (draft)

```
feat: add rubric definition modules (spec-04)

Creates ui_analyzer/rubric/ with all static tier definition constants:
TIER1_DEFINITION (7 WCAG checks), TIER2_DEFINITION (6 Gestalt/CRAP
principles), TIER3_DEFINITION (6 Nielsen/Norman/CLT criteria),
OUTPUT_SCHEMA_XML (raw XML string), and TIER4_DEFINITION in 4 app-type
modules. Static data only — no dynamic generation.
```
