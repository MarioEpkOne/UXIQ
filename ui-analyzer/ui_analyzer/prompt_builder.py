"""prompt_builder.py — assemble the ordered list of ContextEvents for one analysis call."""
from __future__ import annotations

import html
from typing import Literal

from ui_analyzer.axe_runner import AxeCoreResult, AxeFailure
from ui_analyzer.dom_extractor import DomElements, DomFailure
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
    dom_result: DomElements | DomFailure | None = None,
) -> list[ContextEvent]:
    """Assemble the ordered list of ContextEvents for this analysis call.

    axe_result values:
        AxeCoreResult  — axe succeeded; inject <axe_core_result>
        AxeFailure     — axe failed (URL mode); inject <axe_unavailable> with AxeFailure.reason
        None + "url"   — axe returned no result (URL mode); inject <axe_unavailable> with reason
        None + "file"  — source_type is "file"; omit axe block entirely

    Canonical event order (must be preserved):
        1. analysis_request
        2. axe_core_result  — if axe_result is AxeCoreResult
           axe_unavailable  — if axe_result is AxeFailure or (axe_result is None and source_type == "url")
           (omitted entirely — if axe_result is None and source_type == "file")
        3. dom_elements     — if dom_result is DomElements (including empty list)
           dom_unavailable  — if dom_result is DomFailure or dom_result is None
        4. rubric_tier1
        5. rubric_tier2
        6. rubric_tier3
        7. rubric_tier4
        8. output_schema
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
    elif axe_result is None and source_type == "url":
        events.append(ContextEvent(type="axe_unavailable", data={
            "reason": "axe-core returned no result",
            "tier1_mode": "estimated",
            "instruction": (
                "You do not have authoritative WCAG data. Base all Tier 1 findings on "
                "visual estimation only. Mark every Tier 1 finding as ESTIMATED and "
                "recommend manual verification."
            ),
        }))
    # If axe_result is None and source_type == "file": omit axe block entirely

    # 3. DOM elements block
    if isinstance(dom_result, DomElements):
        # Serialize elements as XML string for verbatim injection.
        # String attributes are HTML-escaped; integer attributes are emitted verbatim.
        element_lines = [
            f'  <element tag="{html.escape(el.tag, quote=True)}" '
            f'role="{html.escape(el.role, quote=True)}" '
            f'text="{html.escape(el.text, quote=True)}" '
            f'aria_label="{html.escape(el.aria_label, quote=True)}" '
            f'alt="{html.escape(el.alt, quote=True)}" '
            f'placeholder="{html.escape(el.placeholder, quote=True)}" '
            f'input_type="{html.escape(el.input_type, quote=True)}" '
            f'x="{el.x}" y="{el.y}" w="{el.w}" h="{el.h}"/>'
            for el in dom_result.elements
        ]
        dom_xml = (
            f'<dom_elements count="{len(dom_result.elements)}" '
            f'viewport_width="1280" viewport_height="800">\n'
            + "\n".join(element_lines)
            + "\n</dom_elements>"
        )
        events.append(ContextEvent(type="dom_elements", data=dom_xml))
    else:
        # dom_result is DomFailure or None — inject dom_unavailable
        reason = dom_result.reason if isinstance(dom_result, DomFailure) else "DOM extraction was not attempted"
        dom_unavailable_xml = (
            f"<dom_unavailable>\n"
            f"  <reason>{reason}</reason>\n"
            f"  <instruction>DOM element data is unavailable. Base your inventory on visual analysis of the screenshot alone.</instruction>\n"
            f"</dom_unavailable>"
        )
        events.append(ContextEvent(type="dom_unavailable", data=dom_unavailable_xml))

    # 4–8. Rubric events
    events.append(ContextEvent(type="rubric_tier1", data=tier1.TIER1_DEFINITION))
    events.append(ContextEvent(type="rubric_tier2", data=tier2.TIER2_DEFINITION))
    events.append(ContextEvent(type="rubric_tier3", data=tier3.TIER3_DEFINITION))
    events.append(ContextEvent(type="rubric_tier4", data=TIER4_DEFINITIONS[app_type]))
    events.append(ContextEvent(type="output_schema", data=output_schema.OUTPUT_SCHEMA_XML))

    return events
