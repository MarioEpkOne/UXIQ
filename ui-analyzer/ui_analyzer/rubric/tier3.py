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
