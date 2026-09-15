# Create GitHub issue(s)

**Scope: issue capture only.** Turn one or more user notes into the right number of GitHub issues, then stop. Implementation is **`/work-on-issue <number>`** later.

## Use This Mac (local agent)

**Before creating issues**, tell the user:

> Issue creation works best on **This Mac** (local agent). If this chat is a **Cloud** agent, switch to **This Mac** and run **`/create-issues`** again.

- If Cloud (or unsure), **stop after the reminder** until the user confirms This Mac.
- Requires **`gh`** authenticated for this repo.

## Do not implement in this turn

- Do not open PRs, branches, or code changes unless the user asks **after** issues exist.
- Do not run `dev work-on-issue` in this turn.

## Your task

1. Collect **all** notes the user gave (bullets, paragraphs, voice-dump). Ask for missing detail only if you cannot classify or group.

2. **Plan** (you may skim `src/grocery_wizard/dev/issue_planning.py` and `AREA_FILES` in `enhancement_log.py` to refine areas — optional but helpful for ambiguous notes):

```bash
uv run python -m src.grocery_wizard dev create-issues --dry-run \
  --item "note one" \
  --item "note two"
```

   Or paste notes on stdin (blank line between paragraphs):

```bash
printf '%s\n\n%s\n' "first note" "second note" | \
  uv run python -m src.grocery_wizard dev create-issues --dry-run
```

3. **Explain the plan** to the user in plain language:
   - How many issues and why (merge notes that share **kind** + **code area** so they can ship in one PR; split when area or bug vs feature differs).
   - Which become **enhancement backlog** (`grocery-wizard` label) vs **bug** (`bug` label).

4. If the user agrees (or gave a clear “create them”), create:

```bash
uv run python -m src.grocery_wizard dev create-issues --item "…" --item "…"
```

   For a reviewed JSON plan from `--dry-run --json`:

```bash
uv run python -m src.grocery_wizard dev create-issues --plan-file /tmp/plan.json
```

5. Reply with issue numbers, URLs, and kind. Note **`/work-on-issue <n>`** for backlog items; bugs use the same command for the fix brief.

## Overrides

If auto-planning is wrong, edit the JSON from `--dry-run --json` (set `kind`, `area`, `title`, fields) and use `--plan-file`.
