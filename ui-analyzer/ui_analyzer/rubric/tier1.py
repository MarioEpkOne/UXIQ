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
