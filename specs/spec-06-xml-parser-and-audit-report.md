# Spec 06 — XML Parser & AuditReport Dataclass

**Parent spec:** spec--2026-04-15--15-30--ui-screenshot-analyzer.md  
**Status:** Ready for implementation  
**Depends on:** Spec 01 (UIAnalyzerError — not raised here, but package must be importable)  
**Blocks:** Spec 07 (scorer and renderer consume AuditReport), Spec 08 (handler calls parse())

---

## Goal

Implement `ui_analyzer/xml_parser.py`. This module:
1. Defines the `AuditReport` dataclass — the structured representation of Claude's response
2. Implements `parse(response_text: str) -> AuditReport` — extracts findings from Claude's XML output

This module follows the soft-failure contract: it **never raises** an exception on malformed or incomplete Claude output. Missing tiers produce empty finding lists; completely unparseable XML produces a fully-empty `AuditReport`.

---

## Scope

Files created by this spec:

```
ui_analyzer/
└── xml_parser.py
```

---

## AuditReport Dataclass

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
    nielsen_tag: int | None = None  # Present in tier2 per the output schema

@dataclass
class Tier3Finding:
    # Same shape as Tier2Finding
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
    confidence_level: str = "unknown"      # "high", "medium", "low", or "unknown"
    confidence_reason: str = ""
    inventory: str = ""                    # Raw text from <inventory>
    structure_observation: str = ""        # Raw text from <structure_observation>
    tier1_findings: list[Tier1Finding] = field(default_factory=list)
    tier2_findings: list[Tier2Finding] = field(default_factory=list)
    tier3_findings: list[Tier3Finding] = field(default_factory=list)
    tier4_findings: list[Tier4Finding] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)  # Records parse issues
```

---

## parse()

```python
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)

def parse(response_text: str) -> AuditReport:
    """Parse Claude's <audit_report> XML response into an AuditReport.

    Never raises. Returns AuditReport with empty findings on any parse failure.
    parse_warnings accumulates issues encountered during parsing.
    """
```

### Extraction strategy

Claude's response may include prose before or after the XML block. Extract the `<audit_report>` block using a simple boundary approach:

```python
start = response_text.find("<audit_report>")
end = response_text.find("</audit_report>")
if start == -1 or end == -1:
    report = AuditReport()
    report.parse_warnings.append("No <audit_report> block found in response.")
    return report
xml_fragment = response_text[start:end + len("</audit_report>")]
```

Then parse with `ET.fromstring(xml_fragment)`. Wrap in try/except — any `ET.ParseError` returns an empty `AuditReport` with a warning.

### Confidence

```python
confidence_el = root.find("confidence")
if confidence_el is not None:
    report.confidence_level = confidence_el.get("level", "unknown")
    report.confidence_reason = (confidence_el.text or "").strip()
```

### Inventory and structure_observation

```python
inv = root.find("inventory")
report.inventory = (inv.text or "").strip() if inv is not None else ""

struct = root.find("structure_observation")
report.structure_observation = (struct.text or "").strip() if struct is not None else ""
```

### Tier 1 findings

```python
tier1_el = root.find("tier1_findings")
if tier1_el is not None:
    for f in tier1_el.findall("finding"):
        try:
            report.tier1_findings.append(Tier1Finding(
                criterion=f.get("criterion", ""),
                element=f.get("element", ""),
                result=f.get("result", ""),
                estimated=f.get("estimated", "false").lower() == "true",
                observed=_text(f, "observed"),
                required=_text(f, "required"),
                recommendation=_text(f, "recommendation"),
            ))
        except Exception as e:
            report.parse_warnings.append(f"Skipped malformed tier1 finding: {e}")
```

### Tier 2 findings

```python
tier2_el = root.find("tier2_findings")
if tier2_el is None:
    report.parse_warnings.append("Missing <tier2_findings> in Claude response.")
else:
    for f in tier2_el.findall("finding"):
        try:
            report.tier2_findings.append(Tier2Finding(
                principle=f.get("principle", ""),
                severity=int(f.get("severity", "1")),
                element=f.get("element", ""),
                issue=_text(f, "issue"),
                recommendation=_text(f, "recommendation"),
                nielsen_tag=_int_or_none(f, "nielsen_tag"),
            ))
        except Exception as e:
            report.parse_warnings.append(f"Skipped malformed tier2 finding: {e}")
```

### Tier 3 findings

Same pattern as Tier 2. The XML attribute for the principle column is `principle` in tier3 as well (per the output schema — tier3 uses the same `<finding>` structure as tier2).

### Tier 4 findings

```python
tier4_el = root.find("tier4_findings")
if tier4_el is not None:
    for f in tier4_el.findall("finding"):
        try:
            report.tier4_findings.append(Tier4Finding(
                pattern=f.get("pattern", ""),
                element=f.get("element", ""),
                issue=_text(f, "issue"),
                recommendation=_text(f, "recommendation"),
            ))
        except Exception as e:
            report.parse_warnings.append(f"Skipped malformed tier4 finding: {e}")
```

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

## Failure Scenarios & Behavior

| Scenario | `parse()` behavior |
|----------|-------------------|
| Well-formed XML, all tiers present | All findings populated, no warnings |
| Missing `<tier2_findings>` block | `tier2_findings=[]`, `parse_warnings` gets `"Missing <tier2_findings> in Claude response."` |
| `<audit_report>` not found in response | All findings empty, warning added |
| Malformed XML (unclosed tag etc.) | All findings empty, warning added |
| Individual `<finding>` missing required attribute | Finding skipped, warning added, others extracted |
| Extra tags Claude invented | Silently ignored — only known tags extracted |

**Missing tier rule:** Every tier block (`tier1_findings`, `tier2_findings`, `tier3_findings`, `tier4_findings`) must add a warning to `parse_warnings` when absent from an otherwise valid `<audit_report>`. The same `if tier_el is None: report.parse_warnings.append(...)` pattern applies to all four tiers.

**No exception is ever raised from `parse()`.** The handler (Spec 08) checks `parse_warnings` to decide whether to append the malformed-response warning to the report.

---

## Constraints

- Use `xml.etree.ElementTree` (stdlib). No third-party XML library.
- Do not use `lxml` — it is not in the dependency list.
- `Tier3Finding` uses `principle` for the attribute name (same shape as Tier2) even though Tier 3 is semantically different. This matches the output schema defined in Spec 04.
- The `parse_warnings` list is not surfaced in the Markdown report directly — it is used by the handler to decide whether to prepend a warning message.
- `severity` in Tier2/Tier3 defaults to `1` when unparseable. It does not raise.

---

## Success Criteria

Covered by tests in Spec 09. Key assertions:

- [ ] Well-formed full `<audit_report>` → all 4 finding lists populated correctly
- [ ] `<audit_report>` missing `<tier2_findings>` → `tier2_findings=[]`, warning in `parse_warnings`
- [ ] Non-XML / truncated response → `AuditReport` with all empty lists, warning in `parse_warnings`
- [ ] `parse()` never raises any exception on any input
- [ ] `estimated="true"` attribute → `Tier1Finding.estimated=True`
- [ ] `estimated="false"` attribute → `Tier1Finding.estimated=False`
- [ ] Missing optional `<nielsen_tag>` → `nielsen_tag=None`
