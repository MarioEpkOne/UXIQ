# Rubric Module — Context for Claude

## File structure

Each tier is a Python module exporting a single constant (`TIER1_DEFINITION`, `TIER2_DEFINITION`, etc.) that is a dict or string injected verbatim into the Claude prompt via `prompt_builder.py`.

- `tier1.py` — WCAG 2.1 AA checks (binary Pass/Fail per criterion)
- `tier2.py` — Gestalt + CRAP visual design principles (severity 1–3)
- `tier3.py` — Usability & affordance principles (severity 1–3)
- `tier4/` — Domain-specific pattern checks, one file per `app_type` (`web_dashboard`, `landing_page`, `onboarding_flow`, `forms`)
- `output_schema.py` — XML schema string that tells Claude exactly what structure to emit in `<audit_report>`

## Tier → star rating mapping

Scoring lives in `scorer.py`, not here. The rubric files define what Claude evaluates; the scorer translates findings into ratings.

| Tier | Rating basis |
|------|-------------|
| Tier 1 | % of checks that PASS (binary) |
| Tier 2 | Severity-weighted finding count |
| Tier 3 | Severity-weighted finding count |
| Tier 4 | Finding count (unweighted) |

## Naming conventions

- Tier 1 check IDs: `wcag_<criterion_underscored>` (e.g. `wcag_1_4_3_normal`)
- Tier 2/3 principles: lowercase snake_case matching the principle name (e.g. `proximity`, `figure_ground`)
- Tier 4 patterns: lowercase snake_case domain pattern ID (e.g. `data_density`, `cta_hierarchy`)

## Invariants

- Never import from `handler.py` or any module outside `rubric/` — these are pure data definitions
- `output_schema.py` defines the XML contract between the rubric and `xml_parser.py`; changes here must be mirrored in `xml_parser.py` dataclasses
- Adding a new tier 4 app type requires: new file in `tier4/`, entry in `prompt_builder.TIER4_DEFINITIONS`, and corresponding `app_type` literal in `handler.AnalyzeRequest`
