TIER4_DEFINITION = {
    "app_type": "web_dashboard",
    "scoring": "Flag only — no severity score. Not included in numerical score.",
    "patterns": [
        {
            "id": "data_ink_ratio",
            "description": "Data-ink ratio: chart elements should serve data, not decoration",
        },
        {
            "id": "metric_hierarchy",
            "description": "Metric hierarchy: key KPIs visually dominant over secondary metrics",
        },
        {
            "id": "chart_type_appropriateness",
            "description": "Chart type appropriateness: chart type matches the data relationship shown",
        },
    ],
}
