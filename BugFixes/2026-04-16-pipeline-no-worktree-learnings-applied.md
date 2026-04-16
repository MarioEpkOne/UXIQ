# Bug Fix: Pipeline no-worktree and auto-applied learnings

**Date:** 2026-04-16
**Symptom:** Every pipeline run committed directly to master instead of an isolated worktree branch. Additionally, learnings were applied automatically (modifying ~/.claude/commands/ files) without user review.
**Root cause:**
- Issue 1: `EnterWorktree` is a deferred tool not available in subagent sessions. The impl-plan subagent hit the graceful degradation path ("proceed in the main repo") and produced a plan with no Worktree field. The impl subagent then worked directly on master.
- Issue 2: The `Update learnings.md` section in Phase 6 lacked explicit guards, leaving the door open for the learnings-review skill to be invoked and command files modified without user visibility.
**Confidence at diagnosis:** 95%
**Fix:**
- Issue 1: Inserted Phase 1.5 in `pipeline.md` that calls `EnterWorktree` inline (main session, not a subagent) before any subagent spawns. Fail-hard if EnterWorktree errors — no master fallback. Threads the resulting worktree path into Phase 2 and Phase 3 subagent prompts.
- Issue 2: Replaced the `Update learnings.md` section with a guarded version that explicitly forbids invoking learnings-review, modifying ~/.claude/commands/ or ~/.claude/skills/, and clearing existing entries.
**Files changed:**
- `/home/epkone/.claude/commands/pipeline.md`
**Tests:** No automated tests cover pipeline.md (it is a prompt file). Changes verified by reading the final state of all affected sections.
