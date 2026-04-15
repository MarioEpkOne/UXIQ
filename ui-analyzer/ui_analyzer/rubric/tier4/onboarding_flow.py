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
