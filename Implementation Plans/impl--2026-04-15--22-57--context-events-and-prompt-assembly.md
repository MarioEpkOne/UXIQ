# Implementation Plan: Context Events & Prompt Assembly

## Header
- **Spec**: specs/applied/spec-05-context-events-and-prompt-assembly.md
- **Worktree**: .claude/worktrees/context-events-and-prompt-assembly/
- **Scope — files in play** (agent must not touch files not listed here):
  - ui-analyzer/ui_analyzer/context_events.py  ← new file
  - ui-analyzer/ui_analyzer/prompts.py          ← new file
  - ui-analyzer/ui_analyzer/prompt_builder.py   ← new file
- **Reading list** (read these in order before starting, nothing else):
  1. ui-analyzer/ui_analyzer/axe_runner.py
  2. ui-analyzer/ui_analyzer/rubric/tier1.py
  3. ui-analyzer/ui_analyzer/rubric/tier2.py
  4. ui-analyzer/ui_analyzer/rubric/tier3.py
  5. ui-analyzer/ui_analyzer/rubric/output_schema.py
  6. ui-analyzer/ui_analyzer/rubric/tier4/web_dashboard.py
  7. ui-analyzer/ui_analyzer/rubric/tier4/landing_page.py
  8. ui-analyzer/ui_analyzer/rubric/tier4/onboarding_flow.py
  9. ui-analyzer/ui_analyzer/rubric/tier4/forms.py
  10. ui-analyzer/ui_analyzer/rubric/__init__.py
  11. ui-analyzer/ui_analyzer/rubric/tier4/__init__.py
  12. ui-analyzer/ui_analyzer/__init__.py
  13. ui-analyzer/pyproject.toml
  14. ui-analyzer/tests/conftest.py

## Environment Assumptions Verified
- `pyyaml` 6.0.1 is installed (`pip show pyyaml` confirmed)
- `pytest-asyncio` 1.3.0 is installed
- `pytest-mock` 3.15.1 is installed
- `pyproject.toml` has `asyncio_mode = "auto"` and `testpaths = ["tests"]`
- `conftest.py` sets `ANTHROPIC_API_KEY = "test-key-unit-tests"` before any ui_analyzer import

---

## Steps

### Step 1: Create `context_events.py`
**File**: `ui-analyzer/ui_analyzer/context_events.py`
**Action**: Create new file

**Full file content**:
```python
"""context_events.py — ContextEvent dataclass, XML serialization, thread assembly."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Literal

import yaml

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


@dataclass
class ContextEvent:
    type: EventType
    data: Any  # dict or str — serialized to YAML (dicts) or injected verbatim (str)


def _to_dict(value: Any) -> Any:
    """Convert a dataclass to a dict; return non-dataclass values as-is."""
    if hasattr(value, "__dataclass_fields__"):
        return dataclasses.asdict(value)
    return value


def event_to_xml(event: ContextEvent) -> str:
    """Serialize a ContextEvent to an XML-tagged block.

    - If event.data is a str: inject verbatim as the block body.
    - If event.data is a dict or dataclass: serialize to YAML with default_flow_style=False.
    """
    if isinstance(event.data, str):
        body = event.data
    else:
        data = _to_dict(event.data)
        body = yaml.dump(data, default_flow_style=False).strip()
    return f"<{event.type}>\n{body}\n</{event.type}>"


def thread_to_prompt(events: list[ContextEvent]) -> str:
    """Join serialized events into a single user message text block."""
    blocks = "\n\n".join(event_to_xml(e) for e in events)
    return f"Here is everything known about this analysis task:\n\n{blocks}\n\nWhat is the complete audit report?"
```

**What it does**: Defines the `ContextEvent` dataclass and the two serialization functions. `event_to_xml()` dispatches on str vs. dict/dataclass and produces XML-tagged blocks. `thread_to_prompt()` joins blocks with double newlines and wraps them in a fixed preamble and closing question.

**Verification**: `python -c "from ui_analyzer.context_events import ContextEvent, event_to_xml, thread_to_prompt; print('OK')"` must print `OK`.

---

### Step 2: Create `prompts.py`
**File**: `ui-analyzer/ui_analyzer/prompts.py`
**Action**: Create new file

**Full file content**:
```python
"""prompts.py — module-level system prompt constant."""

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

**What it does**: Exposes `SYSTEM_PROMPT` as a module-level constant. Contains the three phase markers ("inventory", "structure", "rubric") and the no-scoring instruction. No rubric content belongs here.

**Verification**: `python -c "from ui_analyzer.prompts import SYSTEM_PROMPT; assert 'inventory' in SYSTEM_PROMPT; assert 'structure' in SYSTEM_PROMPT; assert 'rubric' in SYSTEM_PROMPT; assert 'numeric scores' in SYSTEM_PROMPT; print('OK')"` must print `OK`.

---

### Step 3: Create `prompt_builder.py`
**File**: `ui-analyzer/ui_analyzer/prompt_builder.py`
**Action**: Create new file

**Full file content**:
```python
"""prompt_builder.py — assemble the ordered list of ContextEvents for one analysis call."""
from __future__ import annotations

from typing import Literal

from ui_analyzer.axe_runner import AxeCoreResult, AxeFailure
from ui_analyzer.context_events import ContextEvent
from ui_analyzer.rubric import tier1, tier2, tier3, output_schema
from ui_analyzer.rubric.tier4 import web_dashboard, landing_page, onboarding_flow, forms

TIER4_DEFINITIONS: dict[str, object] = {
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
    events: list[ContextEvent] = []

    # 1. analysis_request
    analysis_request_data = {
        "app_type": app_type,
        "image_source_type": source_type,
        "image_source_value": image_source_value,
        "tier1_mode": "authoritative" if isinstance(axe_result, AxeCoreResult) else "estimated",
        "viewport_width": viewport_width,
        "viewport_height": viewport_height,
    }
    events.append(ContextEvent(type="analysis_request", data=analysis_request_data))

    # 2. axe block (conditional)
    if isinstance(axe_result, AxeCoreResult):
        events.append(ContextEvent(type="axe_core_result", data=axe_result))
    elif isinstance(axe_result, AxeFailure):
        events.append(ContextEvent(type="axe_unavailable", data={
            "reason": axe_result.reason,
            "tier1_mode": "estimated",
            "instruction": (
                "You do not have authoritative WCAG data. Base all Tier 1 findings on "
                "visual estimation only. Mark every Tier 1 finding as ESTIMATED and "
                "recommend manual verification."
            ),
        }))
    # If axe_result is None (source_type == "file"): omit axe block entirely

    # 3–7. Rubric events
    events.append(ContextEvent(type="rubric_tier1", data=tier1.TIER1_DEFINITION))
    events.append(ContextEvent(type="rubric_tier2", data=tier2.TIER2_DEFINITION))
    events.append(ContextEvent(type="rubric_tier3", data=tier3.TIER3_DEFINITION))
    events.append(ContextEvent(type="rubric_tier4", data=TIER4_DEFINITIONS[app_type]))
    events.append(ContextEvent(type="output_schema", data=output_schema.OUTPUT_SCHEMA_XML))

    return events
```

**What it does**: `build_thread()` constructs the canonical event list. It sets `tier1_mode` to `"authoritative"` only when `axe_result` is `AxeCoreResult`. It propagates `AxeFailure.reason` into the `axe_unavailable` block. It does NOT import `prompts.py` and does NOT call `thread_to_prompt()`.

**Critical constraint**: This file must NOT import `ui_analyzer.prompts`. The handler (Spec 08) assembles the system prompt separately.

**Verification**: `python -c "from ui_analyzer.prompt_builder import build_thread; print('OK')"` must print `OK`.

---

### Step 4: Verify canonical event ordering for all three axe_result branches

After creating all three files, run the following verification in a Python REPL or a quick script to confirm the canonical ordering is preserved:

**axe_result = AxeCoreResult (URL mode, axe succeeded)**:
```python
from ui_analyzer.axe_runner import AxeCoreResult
from ui_analyzer.prompt_builder import build_thread

events = build_thread(
    app_type="web_dashboard",
    source_type="url",
    image_source_value="https://example.com",
    viewport_width=1280,
    viewport_height=800,
    axe_result=AxeCoreResult(),
)
types = [e.type for e in events]
assert types == ["analysis_request", "axe_core_result", "rubric_tier1", "rubric_tier2", "rubric_tier3", "rubric_tier4", "output_schema"], types
print("Branch 1 OK:", types)
```

**axe_result = AxeFailure (URL mode, axe failed)**:
```python
from ui_analyzer.axe_runner import AxeFailure
from ui_analyzer.prompt_builder import build_thread

events = build_thread(
    app_type="landing_page",
    source_type="url",
    image_source_value="https://example.com",
    viewport_width=1280,
    viewport_height=800,
    axe_result=AxeFailure(reason="axe-core timed out"),
)
types = [e.type for e in events]
assert types == ["analysis_request", "axe_unavailable", "rubric_tier1", "rubric_tier2", "rubric_tier3", "rubric_tier4", "output_schema"], types
print("Branch 2 OK:", types)
```

**axe_result = None (file mode)**:
```python
from ui_analyzer.prompt_builder import build_thread

events = build_thread(
    app_type="forms",
    source_type="file",
    image_source_value="/tmp/screenshot.png",
    viewport_width=1280,
    viewport_height=800,
    axe_result=None,
)
types = [e.type for e in events]
assert types == ["analysis_request", "rubric_tier1", "rubric_tier2", "rubric_tier3", "rubric_tier4", "output_schema"], types
assert events[1].type == "rubric_tier1", events[1].type  # no axe event
print("Branch 3 OK:", types)
```

**Verification**: All three assertions pass with no `AssertionError`.

---

### Step 5: Verify `event_to_xml()` with dict data and str data

**Dict data** (YAML serialization):
```python
from ui_analyzer.context_events import ContextEvent, event_to_xml

e = ContextEvent(type="analysis_request", data={"app_type": "web_dashboard", "viewport_width": 1280})
result = event_to_xml(e)
assert result.startswith("<analysis_request>"), result
assert result.endswith("</analysis_request>"), result
assert "app_type: web_dashboard" in result, result
print("Dict test OK")
```

**Str data** (verbatim injection, no YAML):
```python
from ui_analyzer.context_events import ContextEvent, event_to_xml

e = ContextEvent(type="output_schema", data="<audit_report>\n  ...\n</audit_report>")
result = event_to_xml(e)
assert "<audit_report>" in result, result
assert "audit_report:" not in result, "YAML-serialized str — should be verbatim!"
print("Str test OK")
```

**AxeCoreResult dataclass** (dataclass → dict → YAML):
```python
from ui_analyzer.axe_runner import AxeCoreResult
from ui_analyzer.context_events import ContextEvent, event_to_xml

axe = AxeCoreResult()
e = ContextEvent(type="axe_core_result", data=axe)
result = event_to_xml(e)
assert "<axe_core_result>" in result, result
assert "source:" in result or "findings:" in result, result  # YAML fields present
print("Dataclass test OK")
```

**Verification**: All three assertions pass.

---

### Step 6: Verify `thread_to_prompt()` closing line

```python
from ui_analyzer.context_events import ContextEvent, thread_to_prompt

events = [ContextEvent(type="analysis_request", data="hello")]
result = thread_to_prompt(events)
assert result.endswith("What is the complete audit report?"), repr(result[-60:])
assert result.startswith("Here is everything known about this analysis task:"), repr(result[:60])
print("thread_to_prompt OK")
```

**Verification**: Assertion passes. The closing line is exactly `"What is the complete audit report?"` — no trailing whitespace, no newline after.

---

### Step 7: Verify `analysis_request` block contains `viewport_width` and `viewport_height`

```python
from ui_analyzer.context_events import event_to_xml
from ui_analyzer.prompt_builder import build_thread

events = build_thread(
    app_type="web_dashboard",
    source_type="url",
    image_source_value="https://example.com",
    viewport_width=1440,
    viewport_height=900,
    axe_result=None,
)
xml = event_to_xml(events[0])
assert "viewport_width: 1440" in xml, xml
assert "viewport_height: 900" in xml, xml
print("Viewport fields OK")
```

**Verification**: Both assertions pass.

---

### Step 8: Verify `SYSTEM_PROMPT` content requirements

```python
from ui_analyzer.prompts import SYSTEM_PROMPT

assert "inventory" in SYSTEM_PROMPT
assert "structure" in SYSTEM_PROMPT
assert "rubric" in SYSTEM_PROMPT
assert "Do not compute numeric scores" in SYSTEM_PROMPT
assert "star ratings" in SYSTEM_PROMPT
assert "weighted averages" in SYSTEM_PROMPT
# Confirm no rubric content is embedded
assert "TIER" not in SYSTEM_PROMPT
assert "1.4.3" not in SYSTEM_PROMPT
print("SYSTEM_PROMPT OK")
```

**Verification**: All assertions pass.

---

### Step 9: Verify `prompt_builder.py` does NOT import `prompts.py`

```python
import ast, pathlib

src = pathlib.Path("ui-analyzer/ui_analyzer/prompt_builder.py").read_text()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        if isinstance(node, ast.ImportFrom) and node.module and "prompts" in node.module:
            raise AssertionError(f"prompt_builder.py imports prompts: {node.module}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "prompts" in alias.name:
                    raise AssertionError(f"prompt_builder.py imports prompts: {alias.name}")
print("No prompts import — OK")
```

**Verification**: No `AssertionError` raised.

---

### Step 10: Verify `output_schema` event body is injected verbatim (not YAML-serialized)

```python
from ui_analyzer.rubric.output_schema import OUTPUT_SCHEMA_XML
from ui_analyzer.context_events import ContextEvent, event_to_xml

e = ContextEvent(type="output_schema", data=OUTPUT_SCHEMA_XML)
result = event_to_xml(e)
# The body must contain the literal string from OUTPUT_SCHEMA_XML (verbatim)
assert OUTPUT_SCHEMA_XML in result, "OUTPUT_SCHEMA_XML was not injected verbatim"
# Must NOT have been YAML-serialized (YAML would turn it into a quoted string)
assert "audit_report:" not in result, "output_schema body was YAML-serialized"
print("output_schema verbatim injection OK")
```

**Verification**: Both assertions pass.

---

### Step 11: Verify `tier1_mode` field in `analysis_request`

**When axe_result is AxeCoreResult — must be "authoritative"**:
```python
from ui_analyzer.axe_runner import AxeCoreResult
from ui_analyzer.context_events import event_to_xml
from ui_analyzer.prompt_builder import build_thread

events = build_thread("web_dashboard", "url", "https://x.com", 1280, 800, AxeCoreResult())
xml = event_to_xml(events[0])
assert "tier1_mode: authoritative" in xml, xml
print("tier1_mode=authoritative OK")
```

**When axe_result is None — must be "estimated"**:
```python
from ui_analyzer.context_events import event_to_xml
from ui_analyzer.prompt_builder import build_thread

events = build_thread("web_dashboard", "file", "/tmp/img.png", 1280, 800, None)
xml = event_to_xml(events[0])
assert "tier1_mode: estimated" in xml, xml
print("tier1_mode=estimated OK")
```

**Verification**: Both assertions pass.

---

## Post-Implementation Checklist
- [ ] `context_events.py` imports without error
- [ ] `prompts.py` imports without error
- [ ] `prompt_builder.py` imports without error
- [ ] `event_to_xml()` with dict data → YAML body wrapped in correct XML tags
- [ ] `event_to_xml()` with str data → body injected verbatim (no YAML serialization)
- [ ] `event_to_xml()` with `AxeCoreResult` dataclass → converted via `dataclasses.asdict()`, YAML serialized
- [ ] `thread_to_prompt()` output ends with exactly `"What is the complete audit report?"`
- [ ] `thread_to_prompt()` output starts with `"Here is everything known about this analysis task:"`
- [ ] `build_thread()` with `AxeCoreResult` → events[1].type == "axe_core_result"
- [ ] `build_thread()` with `AxeFailure` → events[1].type == "axe_unavailable", reason propagated from `AxeFailure.reason`
- [ ] `build_thread()` with `axe_result=None, source_type="file"` → events[1].type == "rubric_tier1" (no axe event, 6 total events)
- [ ] Canonical event ordering correct in all three branches (Steps 4 verification)
- [ ] `analysis_request` block contains `viewport_width` and `viewport_height` fields
- [ ] `SYSTEM_PROMPT` contains "inventory", "structure", "rubric", and no-scoring instruction
- [ ] `SYSTEM_PROMPT` contains no rubric content (no tier data, no WCAG criterion IDs)
- [ ] `prompt_builder.py` does NOT import `prompts.py`
- [ ] `build_thread()` returns `list[ContextEvent]`, does NOT call `thread_to_prompt()`
- [ ] `output_schema` event body is `OUTPUT_SCHEMA_XML` injected verbatim (not YAML-serialized)
- [ ] `tier1_mode` is `"authoritative"` when `axe_result` is `AxeCoreResult`, `"estimated"` otherwise

## Verification Approach

This is a pure-Python project with no build step. After each file is created:

1. Run `python -c "from ui_analyzer.<module> import <symbol>; print('OK')"` to verify the import is clean.
2. Run the inline verification snippets in each step (Steps 4–11) to assert correctness.
3. After all files are created, run `cd ui-analyzer && pytest tests/ -v` to confirm no existing tests are broken.

No Unity, no TypeScript, no compilation required. All verification is via Python assertions and the existing pytest suite.

---

## Commit Message (draft)
```
feat: add context_events, prompts, and prompt_builder modules

Implements the three modules that assemble the structured user message
sent to Claude: ContextEvent dataclass with XML serialization, the
SYSTEM_PROMPT constant, and build_thread() which assembles the ordered
ContextEvent list for each analysis call.
```
