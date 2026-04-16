# Spec — XML Parser & AuditReport Dataclass
**Date:** 2026-04-15  
**Source spec:** spec-06-xml-parser-and-audit-report.md  
**Status:** Ready for implementation

---

## Goal

Implement `ui_analyzer/xml_parser.py`. This module:
1. Defines the `AuditReport` dataclass — the structured representation of Claude's response
2. Implements `parse(response_text: str) -> AuditReport` — extracts findings from Claude's XML output

This module follows the soft-failure contract: it **never raises** an exception on malformed or incomplete Claude output. Missing tiers produce empty finding lists; completely unparseable XML produces a fully-empty `AuditReport`.

---

## Current State

The `ui_analyzer` package has only:
- `__init__.py` — imports `UIAnalyzerError`, checks for API key
- `exceptions.py` — defines `UIAnalyzerError`

`xml_parser.py` does not exist. This spec creates it.

---

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| XML library | `xml.etree.ElementTree` (stdlib) | No lxml or third-party dependency allowed |
| Failure mode | Never raise — accumulate warnings | Downstream handler checks `parse_warnings` |
| Missing tier behavior | Add warning to `parse_warnings`, leave list empty | Consistent with soft-failure contract |
| `severity` default | `1` when unparseable | Avoids raising, sensible default |
| `Tier3Finding` attribute name | `principle` (same as Tier2) | Matches output schema defined in Spec 04 |

---

## Technical Design

### Dataclasses

```python
from dataclasses import dataclass, field

@dataclass
class Tier1Finding:
    criterion: str          # e.g. "1.4.3"
    element: str            # CSS selector or description
    result: str             # "PASS" or "FAIL"
    estimated: bool         # True if Claude estimated (not axe-core authoritative)
    observed: str           # What Claude observed
    required: str           # What the threshold requires
    recommendation: str     # What to change

@dataclass
class Tier2Finding:
    principle: str          # Gestalt/CRAP principle name
    severity: int           # 1, 2, or 3
    element: str            # Element name + location
    issue: str              # Description of the problem
    recommendation: str
    nielsen_tag: int | None = None

@dataclass
class Tier3Finding:
    principle: str          # criterion id (e.g. "consistency")
    severity: int
    element: str
    issue: str
    recommendation: str
    nielsen_tag: int | None = None

@dataclass
class Tier4Finding:
    pattern: str            # Domain pattern id
    element: str
    issue: str
    recommendation: str

@dataclass
class AuditReport:
    confidence_level: str = "unknown"
    confidence_reason: str = ""
    inventory: str = ""
    structure_observation: str = ""
    tier1_findings: list[Tier1Finding] = field(default_factory=list)
    tier2_findings: list[Tier2Finding] = field(default_factory=list)
    tier3_findings: list[Tier3Finding] = field(default_factory=list)
    tier4_findings: list[Tier4Finding] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)
```

### `parse()` function

1. Find `<audit_report>` boundaries using `str.find()`
2. If not found → return empty `AuditReport` with warning
3. Parse with `ET.fromstring()` — wrap in try/except `ET.ParseError`
4. Extract confidence, inventory, structure_observation
5. Extract each tier's findings with per-finding try/except
6. Add warning when any tier block is missing from an otherwise valid `<audit_report>`

### Private helpers

```python
def _text(el: ET.Element, tag: str) -> str:
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""

def _int_or_none(el: ET.Element, tag: str) -> int | None:
    child = el.find(tag)
    if child is None or not child.text:
        return None
    try:
        return int(child.text.strip())
    except ValueError:
        return None
```

---

## Edge Cases & Error Handling

| Scenario | Behavior |
|----------|----------|
| Well-formed XML, all tiers present | All findings populated, no warnings |
| Missing `<tier2_findings>` block | `tier2_findings=[]`, warning added |
| `<audit_report>` not found | All empty, warning added |
| Malformed XML | All empty, warning added |
| Individual `<finding>` missing required attribute | Finding skipped, warning added |
| Extra tags Claude invented | Silently ignored |
| `estimated="true"` | `Tier1Finding.estimated=True` |
| `estimated="false"` | `Tier1Finding.estimated=False` |
| Missing `<nielsen_tag>` | `nielsen_tag=None` |
| Unparseable `severity` | Default to `1`, no raise |

**Missing tier rule:** All four tiers (`tier1_findings`, `tier2_findings`, `tier3_findings`, `tier4_findings`) must add a warning when absent from an otherwise valid `<audit_report>`.

---

## Constraints & Invariants

- Use `xml.etree.ElementTree` (stdlib only). No `lxml`.
- `parse()` **never raises** any exception on any input.
- `Tier3Finding` uses `principle` attribute name (same shape as Tier2).
- `parse_warnings` is not surfaced directly in Markdown — handler uses it.
- `severity` defaults to `1` when unparseable.

---

## Testing Strategy

Tests are defined in Spec 09. Key assertions:
- Well-formed full `<audit_report>` → all 4 lists populated correctly
- Missing `<tier2_findings>` → `tier2_findings=[]`, warning in `parse_warnings`
- Non-XML / truncated response → `AuditReport` with all empty lists, warning
- `parse()` never raises on any input
- `estimated="true"` → `Tier1Finding.estimated=True`
- `estimated="false"` → `Tier1Finding.estimated=False`
- Missing optional `<nielsen_tag>` → `nielsen_tag=None`

---

## Open Questions

None — spec is complete and ready for implementation.
