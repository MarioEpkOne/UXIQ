"""tool_definition.py — Claude Tool Use JSON schema for analyze_ui_screenshot."""

TOOL_DEFINITION = {
    "name": "analyze_ui_screenshot",
    "description": (
        "Analyzes the visual design and UX of a web UI screenshot. "
        "Returns a structured Markdown report with findings across four tiers: "
        "accessibility (WCAG), visual structure (Gestalt/CRAP), usability "
        "(Nielsen/Norman), and domain-specific patterns. "
        "Does not read source code. Analysis is screenshot-only."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "image_source": {
                "type": "string",
                "description": (
                    "Either a URL (https://...) or an absolute file path to a "
                    "PNG, JPG, or WebP screenshot. If a URL, Playwright captures "
                    "the page and axe-core runs WCAG checks. If a file path, "
                    "Tier 1 results are visually estimated."
                ),
            },
            "app_type": {
                "type": "string",
                "enum": ["web_dashboard", "landing_page", "onboarding_flow", "forms"],
                "description": (
                    "The type of web UI being analyzed. Activates the relevant "
                    "Tier 4 domain pattern module and calibrates scoring expectations."
                ),
            },
        },
        "required": ["image_source", "app_type"],
    },
}
