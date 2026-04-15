# Pipeline Learnings

## Disclose all files created in working log
**Phase affected**: impl
**What happened**: The implementer created `ui-analyzer/.gitignore` outside impl plan scope without listing it in "Changes Made" or "Deviations from Plan", making it invisible to the auditor until git diff inspection.
**Suggestion**: Add an explicit rule to impl.md: every file created or modified — even out-of-scope additions — must appear in the working log's "Changes Made" section. Any file outside the impl plan scope must also appear in "Deviations from Plan" with a one-sentence justification. Undisclosed out-of-scope file creation is a RULE_VIOLATION.

## Stage only explicitly listed paths at commit time
**Phase affected**: impl
**What happened**: The implementer bundled the working log (`Working Logs/wlog--...md`) into the `feat:` commit because it staged more than the `git add ui-analyzer/` prescribed in the impl plan's Step 11.
**Suggestion**: Add a "Commit discipline" rule to impl.md: when the impl plan prescribes `git add <directory>/`, stage only that path — never use `git add -A` or `git add .` or add any path not listed in the impl plan's "Scope — files in play". Working logs and process artifacts must not appear in feature commits.
