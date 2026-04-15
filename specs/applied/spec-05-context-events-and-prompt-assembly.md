# Spec 05 — Context Events & Prompt Assembly

**Parent spec:** spec--2026-04-15--15-30--ui-screenshot-analyzer.md  
**Status:** Ready for implementation  
**Depends on:** Spec 01 (package), Spec 03 (AxeCoreResult), Spec 04 (rubric constants)  
**Blocks:** Spec 08 (handler calls build_thread and thread_to_prompt)

---

## Goal

Implement the three modules that assemble the structured user message sent to Claude:

1. **`context_events.py`** — `ContextEvent` dataclass, `event_to_xml()`, `thread_to_prompt()`
2. **`prompts.py`** — `SYSTEM_PROMPT` named constant
3. **`prompt_builder.py`** — `build_thread()` — assembles the ordered list of `ContextEvent` objects

Together these produce:
- The `system` string passed to `anthropic.messages.create()`
- The `text` block in the user message content list

---

## Scope

Files created by this spec:

```
ui_analyzer/
├── context_events.py
├── prompts.py           ← SYSTEM_PROMPT named constant
└── prompt_builder.py
```

---

## context_events.py

### EventType

```python
from typing import Literal

EventType = Literal[
    "analysis_request",
    "axe_core_result",
    "axe_unavailable",
    "rubric_tier1",
    "rubric_tier2",
    "rubric_tier3",
    "rubric_tier4",
    "output_schema",
    "error",
]
```

### ContextEvent dataclass

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class ContextEvent:
    type: EventType
    data: Any  # dict or str — serialized to YAML (dicts) or injected verbatim (str)
```

### event_to_xml()

```python
import yaml

def event_to_xml(event: ContextEvent) -> str:
    """Serialize a ContextEvent to an XML-tagged block.

    - If event.data is a str: inject verbatim as the block body.
    - If event.data is a dict or dataclass: serialize to YAML with default_flow_style=False.
    """
    if isinstance(event.data, str):
        body = event.data
    else:
        # Convert dataclass to dict if needed
        data = _to_dict(event.data)
        body = yaml.dump(data, default_flow_style=False).strip()
    return f"<{event.type}>\n{body}\n</{event.type}>"
```

`_to_dict()` is a private helper: if the value has a `__dataclass_fields__` attribute, convert via `dataclasses.asdict()`; otherwise return as-is.

### thread_to_prompt()

```python
def thread_to_prompt(events: list[ContextEvent]) -> str:
    """Join serialized events into a single user message text block."""
    blocks = "\n\n".join(event_to_xml(e) for e in events)
    return f"Here is everything known about this analysis task:\n\n{blocks}\n\nWhat is the complete audit report?"
```

The closing line `"What is the complete audit report?"` is a fixed string — it must not be altered.

---

## prompts.py

```python
SYSTEM_PROMPT = """\
You are a senior UI/UX auditor with deep expertise in accessibility,
Gestalt design principles, and Nielsen's heuristics. You analyze
static screenshots of web UIs and produce structured audit reports.

Follow the analysis protocol defined in the <rubric_*> blocks in the user message.
Apply steps in order: inventory → structure → rubric. Do not skip steps.
Only score what is visible in the screenshot. Never score interactivity,
keyboard behavior, screen reader behavior, or anything requiring a live session.

Do not compute numeric scores, star ratings, or weighted averages.
Output raw findings only — scoring is handled by the calling system.

Respond with well-formed XML matching the schema in <output_schema>.\
"""
```

**Critical rules:**
- `SYSTEM_PROMPT` is a module-level constant — never assembled inline anywhere else.
- It contains the three phase markers: "inventory", "structure", "rubric".
- It contains the no-scoring instruction: "Do not compute numeric scores, star ratings, or weighted averages."
- It is intentionally minimal. No rubric content belongs here — all rubric data goes in the user message.

---

## prompt_builder.py

### build_thread()

```python
from typing import Literal
from ui_analyzer.axe_runner import AxeCoreResult, AxeFailure
from ui_analyzer.rubric import tier1, tier2, tier3, output_schema
from ui_analyzer.rubric.tier4 import web_dashboard, landing_page, onboarding_flow, forms
from ui_analyzer.context_events import ContextEvent

TIER4_DEFINITIONS = {
    "web_dashboard": web_dashboard.TIER4_DEFINITION,
    "landing_page": landing_page.TIER4_DEFINITION,
    "onboarding_flow": onboarding_flow.TIER4_DEFINITION,
    "forms": forms.TIER4_DEFINITION,
}

def build_thread(
    app_type: str,
    source_type: Literal["url", "file"],
    image_source_value: str,
    viewport_width: int,
    viewport_height: int,
    axe_result: AxeCoreResult | AxeFailure | None,
) -> list[ContextEvent]:
    """Assemble the ordered list of ContextEvents for this analysis call.

    axe_result values:
        AxeCoreResult  — axe succeeded; inject <axe_core_result>
        AxeFailure     — axe failed (URL mode); inject <axe_unavailable> with AxeFailure.reason
        None           — source_type is "file"; omit axe block entirely

    Canonical event order (must be preserved):
        1. analysis_request
        2. axe_core_result  — if axe_result is AxeCoreResult
           axe_unavailable  — if axe_result is AxeFailure
           (omitted entirely — if axe_result is None)
        3. rubric_tier1
        4. rubric_tier2
        5. rubric_tier3
        6. rubric_tier4
        7. output_schema
    """
```

### analysis_request block

```python
analysis_request_data = {
    "app_type": app_type,
    "image_source_type": source_type,
    "image_source_value": image_source_value,
    "tier1_mode": "authoritative" if isinstance(axe_result, AxeCoreResult) else "estimated",
    "viewport_width": viewport_width,
    "viewport_height": viewport_height,
}
```

### axe block logic

```python
if isinstance(axe_result, AxeCoreResult):
    events.append(ContextEvent(type="axe_core_result", data=axe_result))
elif isinstance(axe_result, AxeFailure):
    # axe was attempted (URL mode) but failed — tell Claude it's in estimated mode
    events.append(ContextEvent(type="axe_unavailable", data={
        "reason": axe_result.reason,   # propagate specific failure reason from AxeFailure
        "tier1_mode": "estimated",
        "instruction": (
            "You do not have authoritative WCAG data. Base all Tier 1 findings on "
            "visual estimation only. Mark every Tier 1 finding as ESTIMATED and "
            "recommend manual verification."
        ),
    }))
# If axe_result is None (source_type == "file"): omit axe block entirely
```

### Rubric events

```python
events.append(ContextEvent(type="rubric_tier1", data=tier1.TIER1_DEFINITION))
events.append(ContextEvent(type="rubric_tier2", data=tier2.TIER2_DEFINITION))
events.append(ContextEvent(type="rubric_tier3", data=tier3.TIER3_DEFINITION))
events.append(ContextEvent(type="rubric_tier4", data=TIER4_DEFINITIONS[app_type]))
events.append(ContextEvent(type="output_schema", data=output_schema.OUTPUT_SCHEMA_XML))
```

---

## Canonical Event Ordering (invariant)

```
analysis_request
axe_core_result  OR  axe_unavailable  OR  (nothing)
rubric_tier1
rubric_tier2
rubric_tier3
rubric_tier4
output_schema
```

This order is fixed. Tests in Spec 09 assert it explicitly.

---

## Constraints

- `prompt_builder.py` must NOT import `prompts.py` — the system prompt is passed separately by the handler (Spec 08), not embedded in the thread.
- `build_thread()` returns a `list[ContextEvent]` — it does NOT call `thread_to_prompt()`. The handler does both: `events = build_thread(...)` then `text = thread_to_prompt(events)`.
- `event_to_xml()` must not fail on `AxeCoreResult` dataclass input — the `_to_dict()` helper handles dataclass conversion.
- The `output_schema` event body is `OUTPUT_SCHEMA_XML` (a str constant), so it is injected verbatim — not YAML-serialized.
- The assembled user message text (output of `thread_to_prompt()`) is **intentionally not valid XML**. It is a plain text string containing XML-like blocks. It is never parsed as XML by any module in this project — only Claude reads it as text. Do not attempt to validate or parse the full assembled message as XML.
- `OUTPUT_SCHEMA_XML` contains nested XML tags (e.g. `<audit_report>`) inside the `<output_schema>` block. This is correct and expected. The outer `<output_schema>` wrapper and its inner XML content are both rendered as plain text to Claude.

---

## Success Criteria

Covered by tests in Spec 09. Key assertions:

- [ ] `event_to_xml()` with dict data → wraps YAML body in correct XML tags
- [ ] `event_to_xml()` with str data → injects verbatim (no YAML serialization)
- [ ] `thread_to_prompt()` output ends with `"What is the complete audit report?"`
- [ ] `build_thread()` with `axe_result=AxeCoreResult(...)` → events[1].type == "axe_core_result"
- [ ] `build_thread()` with `axe_result=None, source_type="url"` → events[1].type == "axe_unavailable"
- [ ] `build_thread()` with `axe_result=None, source_type="file"` → events[1].type == "rubric_tier1" (no axe event)
- [ ] Event ordering matches the canonical order in every combination
- [ ] `<analysis_request>` block contains `viewport_width` and `viewport_height`
- [ ] `SYSTEM_PROMPT` contains "inventory", "structure", "rubric", and no-scoring instruction
