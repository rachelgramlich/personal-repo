# Work on enhancement

Pick up one backlog item and implement it end-to-end.

## Context

- Backlog: `.local/grocery_wizard/enhancements.jsonl`.
- **`dev suggest-fixes`** + `ingredient_edits.jsonl` = data-driven parser fix hints from UI edits.
- **Enhancements** = intentional backlog; primary UX is this command (not ad-hoc CLI).

## Your task

### 1. Resolve enhancement ID

- If the user typed an ID after the command (e.g. `/work-on-enhancement enh_002`), use it.
- Otherwise run `uv run python -m src.grocery_wizard dev list-enhancements`, show open items, and ask which ID to use. Stop until they pick one.

### 2. Load full instructions

Run and **follow** the printed prompt (includes title, description, area, files, branch name, close command):

```bash
uv run python -m src.grocery_wizard dev show-enhancement <ID>
```

Do **not** pass `--close` until the enhancement is actually shipped.

### 3. Implement

- `git fetch origin main` and create the branch named in the show-enhancement output (pattern `cursor/<slug>-21af` off `main`).
- Read the listed files and any other code needed for the area.
- Keep scope aligned with the enhancement description; match existing project style.
- If you change Python: `uv run ruff check` on touched paths; run relevant tests when they exist.

### 4. Ship

- Commit with a clear message referencing the enhancement ID.
- Push the branch and open or update a GitHub PR; mention `<ID>` and title in the PR body.

### 5. Close the backlog entry

When the work is merged or complete:

```bash
uv run python -m src.grocery_wizard dev close-enhancement <ID>
```

Summarize what you changed and link the PR for the user.
