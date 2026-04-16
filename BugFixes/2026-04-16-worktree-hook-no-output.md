# Bug Fix: WorktreeCreate hook produces no stdout on non-pnpm projects

**Date:** 2026-04-16
**Symptom:** `EnterWorktree` failed with `WorktreeCreate hook failed: no successful output` when running the pipeline in the UXIQ project.
**Root cause:** `~/.claude/settings.json` WorktreeCreate hook — `cd "$WORKTREE_PATH" && [ -f pnpm-lock.yaml ] && pnpm install --prefer-offline 2>&1 || true`. On projects without `pnpm-lock.yaml`, the condition short-circuits and `|| true` exits 0 silently. `EnterWorktree` requires at least one byte of stdout to consider the hook successful.
**Confidence at diagnosis:** 96%
**Fix:** Wrapped the pnpm block in a subshell and appended `&& echo "worktree ready"` so the hook always emits output regardless of whether pnpm-lock.yaml exists.
**Files changed:** `~/.claude/settings.json`
**Tests:** N/A — infrastructure config, not app code. Verified by re-running `/pipeline`.
**Note:** The bug was latent — it only surfaced today because pipeline.md was updated (18:25) to add Phase 1.5 which calls `EnterWorktree` for the first time in this project.
