# ui_analyzer Module — Context for Claude

## Pipeline stages (handler.py)

`analyze_ui_screenshot()` runs these stages in order. Stages marked **hard** raise `UIAnalyzerError`; stages marked **soft** degrade gracefully and never raise.

| # | Stage | File | Failure mode |
|---|-------|------|-------------|
| 0 | Input validation (Pydantic) | `handler.py` | Raises `pydantic.ValidationError` |
| 0b | SSRF guard | `handler.py` | Hard — raises `UIAnalyzerError` |
| 1 | API key check | `handler.py` | Hard — raises `UIAnalyzerError` |
| 2 | Image resolve (Playwright screenshot) | `image_source.py` | Hard — raises `UIAnalyzerError` |
| 3 | axe-core accessibility scan | `axe_runner.py` | Soft — returns `AxeFailure`; pipeline continues in estimated mode |
| 3b | DOM extraction | `dom_extractor.py` | Soft — returns `DomFailure`; pipeline continues without DOM data |
| 4 | Build context event thread | `prompt_builder.py` | No failure path |
| 5 | Serialize events to user message text | `context_events.py` | No failure path |
| 6 | Base64-encode screenshot | `handler.py` | No failure path |
| 7 | Primary Claude API call | `handler.py` | Hard — raises `UIAnalyzerError` on timeout or rate limit |
| 8 | Extract preamble (text before `<audit_report>`) | `handler.py` | Soft — returns `''` if no XML found |
| 9 | Parse XML response | `xml_parser.py` | Soft — returns partially empty `AuditReport` with `parse_warnings` |
| 9.5 | Verification pass (second Claude call) | `verifier.py` | Soft — skipped if `verify=False`; returns original report on failure |
| 10 | Compute tier scores | `scorer.py` | No failure path |
| 11 | Render Markdown report | `report_renderer.py` | No failure path |
| 12b | Write per-run debug file | `run_writer.py` | Soft — never raises |
| 13 | Prepend preamble | `handler.py` | No failure path |

## Preamble passthrough rule

Any prose Claude emits before the `<audit_report>` XML tag is extracted by `_extract_preamble()` and prepended to the final Markdown output. This is intentional — it preserves Claude's reasoning notes when present.

## prompt_builder.py — event thread assembly

`build_thread()` assembles `ContextEvent` objects in canonical order:
1. `analysis_request` — metadata (app_type, source_type, viewport dimensions, tier1_mode)
2. `axe_core_result` or `axe_unavailable` — conditional on axe outcome; omitted entirely for file sources
3. `dom_elements` or `dom_unavailable` — conditional on DOM extraction outcome
4. `rubric_tier1` through `rubric_tier4` — injected from `rubric/` module constants
5. `output_schema` — XML schema that tells Claude what structure to emit

The canonical event order is a contract — do not reorder without updating `prompts.py` instructions.

## xml_parser.py — deserialization contract

`parse()` is a soft-failure function: it never raises. It extracts the `<audit_report>` block using regex (not ET.fromstring on the full response), sanitizes bare `&`, then parses with ElementTree.

Typed output dataclasses: `Tier1Finding`, `Tier2Finding`, `Tier3Finding`, `Tier4Finding`, `AuditReport`.

Changes to the XML schema in `rubric/output_schema.py` must be mirrored in these dataclasses.

## prompts.py — SYSTEM_PROMPT contract

`SYSTEM_PROMPT` instructs Claude to:
- Produce findings grounded in evidence visible in the screenshot or axe/DOM data
- Emit a single `<audit_report>` XML block matching the schema in `output_schema.py`
- Mark Tier 1 findings as `ESTIMATED` when axe data is unavailable

The system prompt is sent with `cache_control: ephemeral` so the verifier call can reuse cached tokens.
