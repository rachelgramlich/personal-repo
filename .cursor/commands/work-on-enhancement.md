# Work on enhancement

Pick up one backlog item and implement it end-to-end. **You** handle the PR and UAT handoff — GitHub closes linked issues on merge; the user should not edit backlog metadata by hand.

## Context

- Backlog: GitHub Issues with the **`grocery-wizard`** label (legacy title matches still work during migration).
- New issues use the **Grocery Wizard enhancement** form (label + expected behavior / manual test hints).
- **`dev suggest-fixes`** + `ingredient_edits.jsonl` = data-driven parser fix hints from UI edits.
- **Enhancements** = intentional backlog; primary UX is this command (not ad-hoc CLI).

## Your task

### 1. Resolve issue number

- If the user typed a number after the command (e.g. `/work-on-enhancement 96`), use it.
- Otherwise run `uv run python -m src.grocery_wizard dev list-enhancements`, show open items, and ask which issue # to use. Stop until they pick one.

### 2. Load full instructions

Run and **follow** the printed prompt (includes title, description, area, files, branch, ship steps):

```bash
uv run python -m src.grocery_wizard dev work-on-enhancement <issue-number>
```

### 3. Implement

- `git fetch origin main` and create the branch named in the `work-on-enhancement` output (pattern `cursor/<slug>-21af` off `main`).
- Read the listed files and any other code needed for the area.
- Keep scope aligned with the enhancement description; match existing project style.
- If you change Python: `uv run ruff check` on touched paths; run relevant tests when they exist.

### 4. Ship (PR title, template, merge-time close)

PR **title** must use the standard format (issue number first):

```bash
PR_TITLE="$(uv run python -m src.grocery_wizard dev enhancement-pr-title <issue-number>)"
```

- Commit with a clear message referencing `#<issue-number>`.
- Push the branch.
- Create or update the GitHub PR:
  - **Title:** exactly `$PR_TITLE` (e.g. `#96: Notion-backed pantry, recurring items, and weekly meal plans`).
  - **Body:** use the repo PR template (`.github/pull_request_template.md`). Fill **Manual verification** (surface, where, steps, expected behavior, regression). Include `Closes #<issue-number>` — the issue closes when the PR **merges**, not when the PR is opened.
- If the PR already exists but the title is wrong, update it to `$PR_TITLE`.

### 5. Manual verification handoff

- Tell the user **concisely** to run the **Manual verification** section from the PR description (echo the steps — do not make them hunt in the diff).
- Wait for them to confirm manual passed in chat (or report failures and fix).

When the user confirms manual verification passed, post sign-off on the PR:

```bash
uv run python -m src.grocery_wizard dev record-manual-verification <issue-number>
```

(Optional `--note "…"` for extra context; `--pr-url` if not on the PR branch.)

Summarize what you changed and give the user the PR link. Do not ask them to close the issue manually — merge with `Closes #N` handles that.
