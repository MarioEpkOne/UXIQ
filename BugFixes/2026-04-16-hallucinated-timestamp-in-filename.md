# Bug Fix: Hallucinated timestamp in spec/log filenames

**Date:** 2026-04-16
**Symptom:** Spec file `spec--2026-04-16--16-45--response-robustness.md` had `16:45` in its filename, but the file was written at `03:42` and committed at `04:08` Prague time.
**Root cause:** `spec.md:31` (and equivalent lines in 6 other commands) instructed Claude to use "Prague timezone" for the timestamp, but Claude has no tool to check the actual current time. It only receives a date from memory injection (`currentDate`), never a time. Without a real clock source, Claude fabricates a plausible-looking time.
**Confidence at diagnosis:** 95%
**Fix:** Replaced the "use Prague timezone" instruction in all 7 affected commands with an explicit `date '+%Y-%m-%d--%H-%M'` shell command that Claude must run before writing the file. This forces a real clock lookup.
**Files changed:**
- `/home/epkone/.claude/commands/spec.md`
- `/home/epkone/.claude/commands/impl-plan.md`
- `/home/epkone/.claude/commands/impl-plan-ui.md`
- `/home/epkone/.claude/commands/impl.md`
- `/home/epkone/.claude/commands/fix.md`
- `/home/epkone/.claude/commands/audit-plan.md`
- `/home/epkone/.claude/commands/audit-implementation.md`
**Tests:** N/A — command files, not code.
