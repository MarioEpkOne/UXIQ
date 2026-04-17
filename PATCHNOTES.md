<!-- last-commit: 9a7e05aa1bc856ca88aa14cfe85b0cfc75ff3367 -->
# Patch Notes

## v0.12.0 — 2026-04-17

### add subdirectory CLAUDE.md files for ui_analyzer and rubric modules
Drops focused CLAUDE.md files into `ui-analyzer/ui_analyzer/` and `ui-analyzer/ui_analyzer/rubric/` so future agents land in those directories with module-scoped guidance instead of relying solely on the project root. Docs-only change; no runtime effect.

### document WSL2 shell env requirement for uxiq CLI
Adds a WSL2 note to the project CLAUDE.md explaining that `UXIQ_ANTHROPIC_API_KEY` lives in `~/.bashrc` and non-login shells (like Claude Code sessions) do not source it automatically — prefix invocations with `source ~/.bashrc &&` or source it once before using `uxiq analyze`. Prevents a recurring "missing API key" footgun for CLI users running in non-interactive shells.

### authoritative Tier 1 data — eliminate ESTIMATED flags for contrast & text size
Replaces estimated Tier 1 contrast/text-size evidence with authoritative data captured at DOM time. The Playwright DOM extractor now broadens its selector (p/span/li/label/caption with a direct-text filter), emits per-element computed styles (font_size_px, font_weight, color, effective_bg_color, border_color, border_width_px), and pre-computes WCAG contrast ratios in JS (`text_contrast_ratio`, `ui_contrast_ratio`) so Claude no longer has to estimate them from a screenshot. Axe rule map is fixed (drops 3 IDs absent from the bundle; adds `link-in-text-block → 1.4.1`), the Tier 1 rubric is rescoped (body-text-size + 1.4.11 become authoritative, 1.4.1 narrows to link-in-text-block, 2.4.7 is removed as untestable from a static screenshot), and SYSTEM_PROMPT gains a Style-data subsection with evidence-gated criteria. `max_elements` default raised 300 → 500 to absorb the broadened selector. Covered by new unit + integration tests including literal WCAG contrast assertions (5.74 for #666-on-#fff, 1.61 for #ccc-on-#fff).

## v0.11.0 — 2026-04-17

### add CLI model selection — --model flag and uxiq model subcommand
Adds per-run model override via `uxiq analyze --model <alias>` and a persistent `uxiq model [set <alias>]` subcommand backed by `~/.uxiq/config.json`. Hardcoded model constants are removed from `handler.py` and `verifier.py`, which now resolve the model at call time through the new `config.py`. Default behavior (claude-sonnet-4-6) is preserved for existing callers.

### fix: 1 audit error resolved — _cmd_model_show now calls get_model_with_source()
`_cmd_model_show` now delegates to a new `get_model_with_source()` in `config.py` instead of duplicating the JSON-read logic, so the corrupt/unknown-alias stderr warning fires when the user runs `uxiq model`. Fixes a quiet fallback that hid config problems from the CLI.

### harden SYSTEM_PROMPT and VERIFIER_PROMPT for evidence-grounded findings
Rewrites `SYSTEM_PROMPT` to enforce observation-only rules — no pattern completion, no inferred text, an explicit out-of-scope list for static screenshots, and a per-finding quality bar (element + criterion + justification). Restructures `VERIFIER_PROMPT` around a six-item review checklist with a `<blocking_issues>` escape hatch for incomplete inventories or widespread hallucination, making the verifier's rejections more predictable.

### add 10 bug investigation reports for 2026-04-16
Adds investigation docs for prompt injection, SSRF in the Playwright URL path, axe CDN integrity gaps, WCAG 2.2 tag handling, silent perfect-score truncation, empty audit report output, unevaluable focus findings, and pipeline worktree issues. Documentation-only — queues the items for triage rather than shipping fixes.

### unified page capture — one Playwright session for screenshot + DOM + axe
Replaces the three-independent-browsers pattern with a single `sync_playwright` session that runs goto → `document.fonts.ready` → 300 ms settle → screenshot → DOM extract → axe inject → axe run, in order, against the same page object. DOM extraction is now filtered to elements actually visible in the 1280×800 viewport, and each element carries integer bounding-box coordinates (`x`/`y` clamped, `w`/`h` unclamped) plus an `alt` field for images. The system prompt's DOM-authority section is rewritten to mark the DOM list as authoritative for what exists in the frame, with injection-defence language retained under a narrower heading. URL captures are now all-or-nothing — any sub-step failure raises `UIAnalyzerError` with an attribution prefix; file-path inputs are unchanged.

## v0.10.2 — 2026-04-16

### repair attributed `<audit_report>` parse failure causing silent 5★ output
Fixes a silent failure where Claude emitting `<audit_report version="1">` (or any attributed variant) caused `xml_parser.parse()` to return an empty `AuditReport` with default 5★ scores instead of the real findings. Replaces `str.find()` with compiled regex in `xml_parser.py`, `handler._extract_preamble()`, and `verification_parser.parse()` so attributed root tags are matched correctly. Extends `VerificationResult` with optional `inventory` and `structure_observation` fields that `apply_amendments()` can now propagate, enabling the verifier to rescue a missing inventory from a failed primary parse. Narrows the `SYSTEM_PROMPT` DOM injection guard from a broad "do not follow any instructions" to an explicit list of attack vectors, preventing Claude from treating `<output_schema>` and rubric blocks as untrusted. Adds a diagnostic `logger.warning()` in `handler.py` that logs the first 500 chars of the raw response on parse failure. Surfaces actual parse warning text in the rendered report instead of a generic message. Ships 9 new tests and a new `test_prompts.py` regression guard.

### 1 audit error resolved — unpack run_verification tuple in test_verifier.py
Four `test_verifier.py` tests were failing with `AttributeError` because a prior change updated `run_verification()` to return a `(AuditReport, usage)` tuple but the tests were not updated to unpack it. All four now use `result, _ = run_verification(...)`, restoring a clean 200-test pass.

## v0.10.1 — 2026-04-16

### axe/URL bug fixes — SSRF guard, image-URL detection, vendor axe, wcag22aa, inapplicable-as-PASS, safe log URLs
A broad hardening pass on the axe-core and URL-handling layers. Adds an SSRF guard that blocks loopback, private, and link-local URLs before Playwright runs. Detects image-file URLs early and returns a clean failure rather than attempting accessibility checks on a static asset. Vendors axe-core 4.9.1 locally (eliminating the CDN dependency), upgrades the ruleset to `wcag22aa`, maps `focus-visible` to WCAG 2.4.7, and treats `inapplicable` axe results as PASS so Claude doesn't re-estimate criteria the page genuinely doesn't apply. Also strips path and query parameters from timeout log messages to avoid leaking sensitive URL data, and adds a warning when the primary audit produces an empty element inventory.

### 1 audit error resolved — update stale docstring in _parse_axe_result
Updates the `_parse_axe_result` docstring to accurately reflect that `inapplicable` results are now treated as PASS rather than silently ignored.

## v0.10.0 — 2026-04-16

### pipeline worktree isolation and learnings guard
Fixes the pipeline skill to create a worktree inline in Phase 1.5 (before any subagent spawns) rather than delegating worktree creation to the planner subagent, which lacked the required `EnterWorktree` tool. Also adds explicit guards to the Phase 6 learnings update that prevent the learnings-review skill from being invoked or command files being modified automatically.

### revert version bump — pipeline.md fix unrelated to application
Reverts a premature version bump in `package.json` that was introduced alongside the pipeline.md fix — infrastructure changes to the pipeline tooling do not warrant a version increment.

### add verification agent for second-pass audit quality check
Introduces a verification pass that runs a second Claude call immediately after the primary audit, acting as an automated peer reviewer. The verifier can add missed findings, remove hallucinated ones, and correct misapplied rubric labels. Prompt caching keeps the overhead to roughly 10–15% above a single-call run. Verification is enabled by default; callers can opt out with `verify=False`.

### 3 audit errors resolved
Corrects the verifier's rate-limit warning message from "API timeout" to "API rate limit", updates the `handler.py` module docstring to document the new `verify` parameter, and extends the integration test suite with a cache-token assertion.

### update README for URL-only input and verification agent
Updates the README to reflect that `image_source` now only accepts HTTP/HTTPS URLs (file paths are no longer supported), and documents the verification agent's role in the pipeline and how to disable it.

### track token usage and estimated cost per run
Adds a `RunUsage` dataclass that aggregates input and output token counts across the primary and verifier API calls, computes an estimated USD cost, and appends a summary table to each per-run debug file in `runs/`. Token data flows from both API responses through `verifier.run_verification` (which now returns a tuple) and up to `handler.analyze_ui_screenshot`.

### add real-time progress output to uxiq analyze
Adds a `--quiet` / `-q` CLI flag to suppress console output. When not suppressed, the CLI fires stage-start and stage-end callbacks at image load, axe-core check, Claude analysis, and verification pass, writing human-readable progress lines to stderr. Stdout carries only the final Markdown report, keeping the tool composable in pipelines. Library callers are unaffected — `progress=None` is the unchanged default.

### 1 audit error resolved — update stale module docstring in handler.py
Updates the `handler.py` module-level docstring to reflect the `progress` callback parameter added in the previous commit.

### block real API calls in tests — add pytest-socket and tests/CLAUDE.md
Installs `pytest-socket` as a dev dependency and sets `--disable-socket` in pytest's `addopts`, causing any test that opens a real network socket to fail immediately with `SocketBlockedError`. Also creates `ui-analyzer/tests/CLAUDE.md` with explicit rules and the correct mock pattern for agents writing tests. Removes the integration tests that were hitting the real Anthropic API and real network during the default `pytest` run.

### XML-escape DOM values in prompt_builder to prevent attribute injection
Applies `html.escape(quote=True)` to all six `DomElement` fields before f-string interpolation in `prompt_builder.py`, preventing malicious web pages from breaking the `<dom_elements>` XML structure or injecting instructions into the Claude prompt. Also adds an untrusted-content warning to `SYSTEM_PROMPT` and two new unit tests covering special-character escaping and prompt-injection containment.

## v0.9.0 — 2026-04-16

### DOM injection, URL-only input, and per-run debug files
The most significant update since the initial implementation. Three coordinated changes ship together: (1) `image_source` is restricted to HTTP/HTTPS URLs — file-path inputs now raise `pydantic.ValidationError` before any Playwright call, eliminating conditional branches throughout the pipeline. (2) A new `dom_extractor.py` module uses Playwright to extract interactive DOM elements (buttons, links, inputs, elements with ARIA roles) from the live page and injects them as a `<dom_elements>` event at position 3 in Claude's prompt, anchoring its visual inventory to real DOM nodes instead of screenshot inference alone. (3) A new `run_writer.py` module writes a per-run Markdown debug file to `runs/` after every analysis — containing Claude's confidence rating, element inventory, structure observation, and the full rendered report — so operators can manually verify that Claude's perception matches the actual UI.

### 1 audit error resolved — add runs/ file assertions to integration test
The integration test for URL-based analysis was updated to assert that a debug file is written to `runs/` and that it contains the `## What Claude Sees` and `## Full Analysis` section headers, closing the gap between the spec's Testing Strategy and the actual test coverage.

### raise max_tokens to 16 384, guard against truncation, sanitize bare & in XML
Raises the Claude API `max_tokens` ceiling to 16 384 to prevent truncated audit responses on complex pages. Adds a post-call truncation guard that detects `stop_reason == "max_tokens"` and raises `UIAnalyzerError` with a clear message before the malformed XML reaches the parser. Also sanitizes unescaped `&` characters in raw HTML attributes that were causing the XML parser to fail on axe-core output.

### add README
Adds `README.md` with installation instructions, CLI usage examples, Python API usage, app-type reference, and notes on the `runs/` debug file format and Playwright setup.

### remove pipeline artifacts from remote, add to .gitignore
Pipeline artifacts (implementation plans, retros, working logs, specs, and `learnings.md`) are no longer tracked in version control. A `.gitignore` block excludes these directories so future pipeline runs do not accumulate in the repository.

### add CLAUDE.md, response-robustness spec, and bug report
Commits the project-level `CLAUDE.md` with architecture notes and key invariants for the Claude Code agent, alongside a bug report for the truncation issue and a response-robustness spec that drove the `max_tokens` / truncation-guard fix.

### clear learnings — 6 pipeline improvements applied to impl/impl-plan/fix/pipeline commands
Clears six previously recorded pipeline learnings after applying them to the pipeline command files, keeping `learnings.md` focused on unaddressed improvements.

## v0.8.0 — 2026-04-16

### add uxiq CLI entry point with analyze, list-app-types, and --version
Introduces `ui_analyzer/cli.py` — a full `argparse`-based CLI registered as the `uxiq` script in `pyproject.toml`. Running `uxiq analyze <image> --app-type <type>` invokes the full audit pipeline and prints the Markdown report to stdout (or writes it to a file with `-o`). Two utility subcommands ship alongside it: `uxiq list-app-types` prints the four valid app-type identifiers, and `uxiq --version` prints the installed package version. As part of this change, the import-time API key guard is moved from `__init__.py` into `analyze_ui_screenshot()` so non-analyze commands work without `UXIQ_ANTHROPIC_API_KEY` set.

### correct env var name and test suite regressions from fix loops
Corrects two audit-loop regressions: `handler.py` was checking `ANTHROPIC_API_KEY` instead of the correct `UXIQ_ANTHROPIC_API_KEY`, and the `cli.py` argparse `choices=` constraint caused invalid `--app-type` values to exit 2 instead of the spec-required exit 1 with a custom error message. Also adds an autouse `conftest.py` fixture that injects a dummy `UXIQ_ANTHROPIC_API_KEY` for all non-integration tests, restoring the 100-test baseline that was broken when the env guard moved to `handler.py`.

## v0.7.0 — 2026-04-16

### pass Claude preamble through to final Markdown output
When Claude prepends explanatory prose before the `<audit_report>` XML block (e.g. a disclaimer that the image is not a UI screenshot), that text was previously discarded by the XML parser and never reached the caller. This adds `_extract_preamble()` to `handler.py` to capture any text before the XML block and prepend it to the rendered Markdown report with a blank-line separator. Whitespace-only preambles are suppressed; responses with no `<audit_report>` at all have their entire content surfaced as the preamble. Three new unit tests cover these paths and the existing preamble assertion is fully restored.

## v0.6.0 — 2026-04-15

### add tool_definition and handler — public surface of ui_analyzer
Adds the two user-facing modules that complete the public API: `tool_definition.py` exposes the Claude Tool Use JSON schema so callers can register the analyzer as a Claude tool, and `handler.py` implements `analyze_ui_screenshot()` — the single orchestration entry point that chains all 10 pipeline stages (validate → resolve → axe-core → build_thread → API call → parse → compute → render). Also ships `test_handler.py` with 12 unit tests covering all spec scenarios.

### move spec-08 to applied
Housekeeping commit moving the tool-definition-and-handler spec into the `applied/` directory now that it is fully implemented.

### add full unit test suite for all ui_analyzer modules
Fills the remaining test gap: adds `test_axe_runner.py`, `test_context_events.py`, `test_prompt_builder.py`, `test_scorer.py`, and `test_report_renderer.py`, and extends `test_handler.py` with the missing preamble unit test and four integration tests. All unit tests run without internet access or an API key; integration tests are automatically skipped when `ANTHROPIC_API_KEY` is unset.

### rewrite test_overall_weighting to call compute() end-to-end
Corrects `test_overall_weighting` in `test_scorer.py` to call `compute()` with controlled fixture inputs (T1=5.0, T2=3.5, T3=3.5) and assert `scores.overall == 4.1`, replacing the previous tautological formula check that verified arithmetic against itself rather than exercising the real scorer function.

## v0.5.0 — 2026-04-15

### implement scorer and report_renderer modules (spec-07)
Adds `scorer.py` and `report_renderer.py` — two pure, deterministic modules that convert parsed `AuditReport` data into a scored result and a fully-formatted Markdown audit report. The scorer computes per-tier star ratings and an overall `Scores` dataclass; the renderer assembles the complete output document with severity icons, estimated-finding labels, Nielsen heuristic tags, and conditional sections for empty tiers.

### add context_events, prompts, and prompt_builder modules
Introduces the three modules responsible for assembling the structured user message sent to Claude: `context_events.py` (a `ContextEvent` dataclass with XML serialization that renders dicts as YAML and strings verbatim), `prompts.py` (the `SYSTEM_PROMPT` constant), and `prompt_builder.py` (`build_thread()` which produces the canonical ordered event list for every analysis call).

### inject axe_unavailable event when axe_result=None and source_type=url
Fixes a missing branch in `build_thread()`: when axe-core was attempted on a URL source but returned no result (`axe_result=None`), the function was silently omitting the axe block instead of injecting an `axe_unavailable` event. Claude now receives an explicit estimated-mode instruction in this scenario, preventing silent degradation to visual-only analysis.

### pipeline artifacts for spec-05 context events and prompt assembly
Records the implementation plan, audit retro, working log, and fixer log for the context events and prompt assembly pipeline run.

## v0.4.0 — 2026-04-15

### implement xml_parser and AuditReport dataclasses
Adds `xml_parser.py`, which deserializes the LLM's structured XML audit output into typed Python dataclasses (`AuditReport`, `Finding`, `Tier4Finding`). Handles all four tier variants, extracts Nielsen heuristic and WCAG criterion metadata, and surfaces parse warnings for malformed or partially-valid XML rather than raising hard errors. Includes 384-line test suite covering happy paths, malformed inputs, and edge cases across all tier types.

### move spec-03 to applied subfolder
Moves `spec-03-axe-core-runner.md` into `specs/applied/` to mark the axe-core runner spec as complete and keep the active specs directory uncluttered.

## v0.3.0 — 2026-04-15

### implement image_source.py with URL capture and file loading
Adds `image_source.py` as the first data-ingestion module, handling both URL screenshots (via Playwright Chromium) and local file paths (PNG/JPG/WebP). Images with a longest edge over 1568px are automatically downsampled with Pillow LANCZOS before passing downstream. Also establishes the test fixtures directory with five synthetic images and 11 unit tests covering all file-mode and URL error paths.

### pipeline artifacts for spec-02 image-source-resolution
Commits the implementation plan, working log, and retro for spec-02; moves the spec to `specs/applied/` to mark it complete.

### implement axe_runner.py with WCAG 2.1 AA axe-core integration
Adds `axe_runner.py`, which launches a dedicated Playwright browser per call, injects axe-core 4.9.1 from CDN, and runs WCAG 2.1 AA checks. Maps four axe rules to WCAG criteria (1.4.3, 1.4.11, 2.5.8, 1.4.1), extracts contrast ratios and touch-target sizes from node data, and returns soft `AxeFailure` on any error rather than raising — keeping the pipeline fault-tolerant when axe-core is unavailable.

### enforce axe-core timeout via Promise.race (remove invalid page.evaluate timeout kwarg)
Playwright's Python `page.evaluate()` does not accept a `timeout` keyword argument; the previous implementation silently ignored the intended 10-second limit. Replaced with a JS-side `Promise.race` + `setTimeout(10000)` to properly enforce the cutoff. Also adds `browser.close()` on all early-return failure paths to prevent browser leaks.

### spec-03 pipeline artifacts (axe-core runner impl plan, audit, learnings)
Commits the full spec-03 pipeline paper trail: implementation plan, audit report, fixer log, and learnings additions. Includes the spec-03 spec file.

### add rubric definition modules (spec-04)
Creates the `ui_analyzer/rubric/` package with all static tier definition constants used by the prompt builder: WCAG/Gestalt/Nielsen rubric dicts for Tiers 1–3, four app-type-specific Tier 4 dicts, and the raw `OUTPUT_SCHEMA_XML` string for verbatim injection into the LLM user message. None of these generate content dynamically — they are pure data modules that can be diffed and iterated independently of pipeline logic.

### wrap-up pipeline artifacts for spec-04 rubric definitions
Commits the spec-04 implementation plan and audit retro to the repository.

## v0.2.0 — 2026-04-15

### initial commit (specs only)
Added the full specification suite for the `ui-analyzer` tool — a parent spec plus nine child specs covering every module from project bootstrap through the final test suite. This establishes the complete design blueprint before any implementation begins.

### bootstrap ui-analyzer package scaffold
Created the `ui-analyzer` Python package skeleton: `pyproject.toml` with hatchling build backend, runtime dependencies (anthropic, playwright, pillow, pyyaml, pydantic), dev dependencies (pytest, pytest-asyncio, pytest-mock), the `UIAnalyzerError` exception class, and an `ANTHROPIC_API_KEY` guard that raises at import time when the key is absent. All downstream specs depend on this foundation.

### wrap-up pipeline artifacts for spec-01 project bootstrap
Committed the full pipeline paper trail for the project-bootstrap spec: implementation plan, working log, fixer log, audit report (with re-audit), and `learnings.md`. Also moved `spec-01-project-bootstrap.md` to `specs/applied/` to mark it as complete.
