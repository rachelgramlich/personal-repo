# Work on enhancement

Pick up one backlog item and implement it end-to-end. **You** handle backlog completion and PR linking — the user should not run `close-enhancement` or edit `enhancements.jsonl` by hand.

## Context

- Backlog: `src/grocery_wizard/dev/enhancements.jsonl` (committed).
- **`dev suggest-fixes`** + `ingredient_edits.jsonl` = data-driven parser fix hints from UI edits.
- **Enhancements** = intentional backlog; primary UX is this command (not ad-hoc CLI).

## Your task

### 1. Resolve enhancement ID

- If the user typed an ID after the command (e.g. `/work-on-enhancement enh_002`), use it.
- Otherwise run `uv run python -m src.grocery_wizard dev list-enhancements`, show open items, and ask which ID to use. Stop until they pick one.

### 2. Load full instructions

Run and **follow** the printed prompt (includes title, description, area, files, branch, ship steps):

```bash
uv run python -m src.grocery_wizard dev work-on-enhancement <ID>
```

(`dev show-enhancement <ID>` is equivalent; do **not** pass `--close`.)

### 3. Implement

- `git fetch origin main` and create the branch named in the show-enhancement output (pattern `cursor/<slug>-21af` off `main`).
- Read the listed files and any other code needed for the area.
- Keep scope aligned with the enhancement description; match existing project style.
- If you change Python: `uv run ruff check` on touched paths; run relevant tests when they exist.

### 4. Ship (PR title + backlog link)

PR **title** must use the standard format (enhancement ID first):

```bash
PR_TITLE="$(uv run python -m src.grocery_wizard dev enhancement-pr-title <ID>)"
```

- Commit with a clear message referencing `<ID>`.
- Push the branch.
- Create or update the GitHub PR:
  - **Title:** exactly `$PR_TITLE` (e.g. `enh_002: Per-week recurring overrides + UI to edit default recurring list`).
  - **Body:** short summary, test plan, and the enhancement description as needed.
- If the PR already exists but the title is wrong, update it to `$PR_TITLE`.

### 5. Complete the backlog entry (required)

After the PR exists for this branch, link it and mark the enhancement done:

```bash
uv run python -m src.grocery_wizard dev complete-enhancement <ID>
```

This reads the PR URL from `gh pr view` on the current branch. If that fails, pass `--pr-url <url>` explicitly.

Confirm with:

```bash
uv run python -m src.grocery_wizard dev list-enhancements --all
```

The entry should show `[done]` and the PR URL.

Summarize what you changed and give the user the PR link. Do not ask them to run `close-enhancement`.
