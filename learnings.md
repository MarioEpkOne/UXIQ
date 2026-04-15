# Pipeline Learnings

## Skip spec-creation phase when spec file is passed as pipeline parameter
**Phase affected**: spec (Phase 1)
**What happened**: When the user passes an existing spec file as the pipeline argument, Phase 1 still created a redundant formal spec document. This produced two spec files — only one of which the planner moved to `applied/`, leaving the original orphaned in `specs/`.
**Suggestion**: If the pipeline argument is a path to an existing file in `specs/`, skip Phase 1b (interview) and Phase 1c (write spec) entirely. Pass the provided spec directly to the planner as-is. The planner will then move that single file to `applied/` as normal.

## Disclose all files created in working log
**Phase affected**: impl
**What happened**: The implementer created `ui-analyzer/.gitignore` outside impl plan scope without listing it in "Changes Made" or "Deviations from Plan", making it invisible to the auditor until git diff inspection.
**Suggestion**: Add an explicit rule to impl.md: every file created or modified — even out-of-scope additions — must appear in the working log's "Changes Made" section. Any file outside the impl plan scope must also appear in "Deviations from Plan" with a one-sentence justification. Undisclosed out-of-scope file creation is a RULE_VIOLATION.

## Worktree commit blocked by hook reading main repo CWD
**Phase affected**: impl
**What happened**: The harness hook intercepts `git commit` and runs `git rev-parse --abbrev-ref HEAD` in the hook process's CWD (the main repo, always on master), not in the worktree — so every commit attempt from a worktree branch is treated as a master commit and blocked.
**Suggestion**: Add a note to impl.md that when working in a worktree, the Bash tool's `cd <worktree> && git commit` pattern is blocked by the hook. Instruct the pipeline to note this and have the Phase 6 summary explicitly tell the user to run the commit manually: `git -C <worktree-path> commit -m "..."` from a terminal outside the harness.

## Verify runtime API signatures before reproducing spec code examples
**Phase affected**: impl
**What happened**: The spec contained `page.evaluate(..., timeout=AXE_TIMEOUT_MS)` modeled on the JavaScript Playwright API. The Python `Page.evaluate(self, expression, arg=None)` signature has no `timeout` parameter — passing it raises `TypeError` at runtime, caught silently, causing a spurious `AxeFailure`. The implementer reproduced the spec verbatim without checking the Python API.
**Suggestion**: Add a rule to impl.md: for any external library call shown in the spec (Playwright, httpx, etc.), verify the Python-side method signature matches before implementing. If the spec was clearly written against a different language's API (e.g. JS Playwright docs), note the discrepancy and adapt the call to the Python equivalent.

## Use absolute expected values in logic verification, not tautological assertions
**Phase affected**: impl-plan
**What happened**: The impl plan's logic verification step had the implementer compute the formula and compare against itself (e.g. `assert compute(...) == 5*0.4 + 3*0.35 + 4*0.25`). This is tautological — it cannot catch spec-stated expected values that differ from actual float results (e.g. `4.1` vs `4.0` due to IEEE 754). The audit had to flag the discrepancy.
**Suggestion**: Impl-plan verification steps must assert against the *spec's literal stated value*, not a re-derived formula. Write `assert round(result, 1) == 4.1` (which would *fail* and expose the discrepancy early), not `assert result == 5*0.4 + 3*0.35 + 4*0.25`.

## Stage only explicitly listed paths at commit time
**Phase affected**: impl
**What happened**: The implementer bundled the working log (`Working Logs/wlog--...md`) into the `feat:` commit because it staged more than the `git add ui-analyzer/` prescribed in the impl plan's Step 11.
**Suggestion**: Add a "Commit discipline" rule to impl.md: when the impl plan prescribes `git add <directory>/`, stage only that path — never use `git add -A` or `git add .` or add any path not listed in the impl plan's "Scope — files in play". Working logs and process artifacts must not appear in feature commits.

## Subagent misdiagnoses "no git repo" when EnterWorktree fails
**Phase affected**: impl
**What happened**: The impl-plan subagent attempted `EnterWorktree`, which failed (tool unavailable or returned an error). Rather than diagnosing the actual failure, the subagent concluded the project had no git repository at all — and the implementer inherited this incorrect belief, skipping the commit step entirely. The repo existed and was fully functional throughout.
**Suggestion**: Add a rule to impl.md and impl-plan.md: if `EnterWorktree` fails, verify git repo presence independently with `git rev-parse --show-toplevel` before declaring "no git repo." A worktree creation failure means the tool is unavailable — not that git itself is absent. Work proceeds in the main repo and the commit step must still run.

## Count test functions before publishing test count in impl plan
**Phase affected**: impl-plan
**What happened**: The impl plan stated "13 tests passing" in two places (the verification command and the checklist), but the embedded test file had exactly 12 `def test_` functions. The discrepancy is harmless but erodes trust in the plan's accuracy.
**Suggestion**: Add a rule to impl-plan.md: when embedding a full test file in the plan, count the `def test_` functions explicitly and use that count in every reference to the expected pass count. Do not estimate.

## Spec internal inconsistency caught only by audit, not impl-plan
**Phase affected**: impl-plan
**What happened**: The spec's "axe block logic" section described `axe_result=None` as unconditionally omitting the axe block, but the Success Criteria section added a fourth branch (`None + source_type="url"`) that the logic section never mentioned. The impl plan faithfully followed the logic section, so the implementer never tested the missing branch. The audit caught the inconsistency, triggering a fix loop.
**Suggestion**: Add a rule to impl-plan.md: before finalizing the plan, cross-check every Success Criteria bullet against the logic/design sections of the spec to confirm each criterion has a corresponding implementation path. Flag any criterion with no matching code path as a spec inconsistency before the impl starts.
