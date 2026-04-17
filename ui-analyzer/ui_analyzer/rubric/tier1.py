TIER1_DEFINITION = {
    "protocol": "WCAG 2.1 AA",
    "scoring": "binary — Pass / Fail per check",
    "source_note": (
        "Authoritative data sources: axe-core (for criteria below that cite a "
        "DOM-level rule) and per-element computed styles in <dom_elements> "
        "(font_size_px, text_contrast_ratio, ui_contrast_ratio). Findings "
        "grounded in either source must NOT be marked estimated=\"true\"."
    ),
    "checks": [
        {
            "id": "wcag_1_4_3_normal",
            "criterion": "1.4.3",
            "description": "Text contrast ratio (normal text)",
            "threshold": ">=4.5:1",
            "evidence": "axe color-contrast OR element text_contrast_ratio",
        },
        {
            "id": "wcag_1_4_3_large",
            "criterion": "1.4.3",
            "description": "Text contrast ratio (large text >=18px or 14px bold)",
            "threshold": ">=3:1",
            "evidence": (
                "axe color-contrast OR element text_contrast_ratio "
                "(use element font_size_px and font_weight to decide large/normal)"
            ),
        },
        {
            "id": "wcag_1_4_11",
            "criterion": "1.4.11",
            "description": "UI component / non-text contrast",
            "threshold": ">=3:1",
            "evidence": (
                "element ui_contrast_ratio. Absent value means the element "
                "is not a UI-component boundary candidate — do not generate "
                "a 1.4.11 finding for it."
            ),
        },
        {
            "id": "wcag_2_5_8",
            "criterion": "2.5.8",
            "description": "Touch targets",
            "threshold": ">=24px min, >=44px recommended",
            "evidence": "axe target-size. Element w/h attributes may corroborate.",
        },
        {
            "id": "body_text_size",
            "criterion": "advisory",
            "description": "Body text size",
            "threshold": ">=16px recommended for body; >=14px minimum for labels/footer",
            "evidence": "element font_size_px (authoritative).",
        },
        {
            "id": "wcag_1_4_1",
            "criterion": "1.4.1",
            "description": "Links in body text distinguished by more than colour",
            "threshold": (
                ">=3:1 contrast between link and surrounding text, "
                "OR underline/weight differentiator"
            ),
            "evidence": (
                "axe link-in-text-block. For non-link uses of colour "
                "(required-field indicators, status colour codes, graph "
                "legends), there is no authoritative data — omit the "
                "finding rather than estimate."
            ),
        },
        # 2.4.7 removed — not testable from a single static screenshot.
    ],
}
