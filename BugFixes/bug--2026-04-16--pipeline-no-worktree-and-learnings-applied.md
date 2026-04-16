# Bug: Pipeline Commits Directly to Master and Auto-Applies Learnings

**Date**: 2026-04-16
**Status**: Open

---

## Issue 1 — Worktree never created; all commits land on master

### Symptom

Every pipeline run commits directly to master instead of an isolated worktree branch.

### Root Cause

`EnterWorktree` is a deferred tool available only in the top-level harness session. When the pipeline spawns the impl-plan phase as a general-purpose `Agent()` subagent, the subagent starts with a fresh context and does not inherit the parent session's deferred tool registry. The subagent attempts `ToolSearch select:EnterWorktree`, finds nothing, and falls through to the graceful degradation path in `impl-plan.md`:

> *"If EnterWorktree is unavailable, verify git is present and proceed in the main repo."*

The resulting impl plan has no `**Worktree:**` field. The impl subagent reads the plan, hits `impl.md` Phase 2 ("No worktree field → proceed from current working directory"), and runs everything on master. All commits land there directly.

### Suggested Fix

Insert a new **Phase 1.5** in `pipeline.md` — running inline in the main session (not as a subagent) — that creates the worktree before any subagent is spawned. Pass the resulting worktree path into both the impl-plan and impl subagent prompts.

**Phase 1.5 to add between the Phase 1 and Phase 2 banners:**

```
## Phase 1.5 — Create Worktree

Print this banner:

══════════════════════════════════════════════════════════════
  PIPELINE PHASE 1.5 — WORKTREE
  Creating isolated branch for this pipeline run...
══════════════════════════════════════════════════════════════

Derive a slug from the spec filename: lowercase, hyphens only, max 30 chars.
Example: spec--2026-04-16--18-00--perception-verification-and-dom-injection.md → perception-verification-dom

Load the EnterWorktree schema:
  ToolSearch query="select:EnterWorktree"

Call: EnterWorktree name='<slug>'

**If EnterWorktree fails for any reason: STOP the pipeline. Report the error.
Do not fall back to working on master. Tell the user to resolve the issue and rerun.**

Note the worktree path returned — you will pass it to Phase 2 and Phase 3.
```

**Add to the top of the Phase 2 subagent prompt:**

```
A worktree has already been created at: [WORKTREE_PATH]

When you reach Phase 4 (Create Worktree) in impl-plan.md: SKIP IT. The worktree already exists.
In the plan's Header section, write exactly: **Worktree**: [WORKTREE_PATH]
```

**Add to the top of the Phase 3 subagent prompt:**

```
The worktree for this work is at: [WORKTREE_PATH]
All file edits and commits must happen inside this worktree, not on master.
```

**Only `pipeline.md` needs to change.** `impl-plan.md` and `impl.md` are untouched — the subagents consume a path that already exists rather than trying to create one themselves.

---

## Issue 2 — Learnings applied automatically; command file changes invisible

### Symptom

After a pipeline run, entries are cleared from `learnings.md` and pipeline command files (`~/.claude/commands/impl.md`, `impl-plan.md`, etc.) are modified without the user reviewing or approving what changed. The only visible evidence is a `chore: clear learnings` commit that deletes the learnings entries — the actual diffs to the command files are not in this repo and cannot be inspected.

### Root Cause

The pipeline command files live in `~/.claude/commands/`, outside this git repo. Changes to them produce no diff here. At some point (either a previous version of `pipeline.md` that included a `learnings-review` step, or a separate session), the `learnings-review` skill was invoked, applied all pending learnings directly to the command files, and then `learnings.md` was cleared. The commit records only the clearing — not what was changed.

The current Phase 6 instruction does not explicitly forbid applying learnings or invoking `learnings-review`, leaving the door open for this to happen again.

### Suggested Fix

Two changes to `pipeline.md` Phase 6:

**1. Move the learnings step to after merge and patch notes** (user requested: record after committing and merging):

Current order:
1. Artifact paths
2. **Update learnings.md** ← currently here
3. Report remaining issues / suggest next steps
4. Merge worktree to master
5. Update patch notes

New order:
1. Artifact paths
2. Report remaining issues / suggest next steps
3. Merge worktree to master
4. Update patch notes
5. **Update learnings.md** ← move here

**2. Replace the "Update learnings.md" instruction with this version:**

```
### Update learnings.md

Reflect on the pipeline run across all phases. Write only entries that are actionable improvements
to the pipeline process itself — not code patterns or project-specific observations.

Format each entry as:
## [Short title]
**Phase affected**: [spec / impl-plan / impl / audit / fix]
**What happened**: [one sentence — the slowdown or friction observed]
**Suggestion**: [concrete change to the pipeline prompt or process]

Then:
- If learnings.md does not exist: create it with a `# Pipeline Learnings` header
- Append any new entries

**IMPORTANT — DO NOT apply these learnings:**
- Do NOT invoke the learnings-review skill
- Do NOT modify any files under ~/.claude/commands/ or ~/.claude/skills/
- Do NOT clear or delete existing entries from learnings.md
- The sole purpose of this step is to record observations for future human review
```

---

## Files to Change

| File | Change |
|---|---|
| `/home/epkone/.claude/commands/pipeline.md` | Insert Phase 1.5; add worktree path to Phase 2 and Phase 3 prompts; reorder Phase 6; replace learnings instruction |
