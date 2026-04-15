TIER4_DEFINITION = {
    "app_type": "forms",
    "scoring": "Flag only — no severity score. Not included in numerical score.",
    "patterns": [
        {
            "id": "label_placement",
            "description": "Label-above-field placement: labels positioned above inputs, not beside or as placeholders",
        },
        {
            "id": "error_proximity",
            "description": "Inline error proximity: error messages appear directly below the relevant field",
        },
        {
            "id": "required_field_marking",
            "description": "Required field marking: required fields are consistently marked (e.g. asterisk with legend)",
        },
    ],
}
