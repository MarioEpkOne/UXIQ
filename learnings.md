# Pipeline Learnings

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

## Stage only explicitly listed paths at commit time
**Phase affected**: impl
**What happened**: The implementer bundled the working log (`Working Logs/wlog--...md`) into the `feat:` commit because it staged more than the `git add ui-analyzer/` prescribed in the impl plan's Step 11.
**Suggestion**: Add a "Commit discipline" rule to impl.md: when the impl plan prescribes `git add <directory>/`, stage only that path — never use `git add -A` or `git add .` or add any path not listed in the impl plan's "Scope — files in play". Working logs and process artifacts must not appear in feature commits.
