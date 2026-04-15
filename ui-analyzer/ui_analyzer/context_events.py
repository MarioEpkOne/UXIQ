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
