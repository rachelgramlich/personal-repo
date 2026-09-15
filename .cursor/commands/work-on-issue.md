# Work on issue

Pick up **one GitHub issue** (backlog enhancement or bug) and implement end-to-end. **You** handle the PR and UAT handoff.

## Context

- Backlog: issues with **`grocery-wizard`** label (list via **`/list-enhancements`**).
- Bugs: **`bug`** label (not in backlog list; user gives the issue #).
- **`dev suggest-fixes`** + ingredient edit log = parser fix hints from UI edits.

## Your task

### 1. Resolve issue number

- If the user typed a number (e.g. `/work-on-issue 96`), use it.
- Otherwise run `uv run python -m src.grocery_wizard dev list-enhancements`, show open backlog items, and ask which # to use.

### 2. Load full instructions

```bash
uv run python -m src.grocery_wizard dev work-on-issue <issue-number>
```

Follow the printed prompt (title, description, area/files, branch, ship steps).

### 3. Implement

- `git fetch origin main` and create the branch named in the output (pattern `cursor/<slug>-21af` off `main`).
- Match existing project style; `uv run ruff check` on touched Python.

### 4. Ship

```bash
PR_TITLE="$(uv run python -m src.grocery_wizard dev enhancement-pr-title <issue-number>)"
```

(Use a sensible `fix: …` title for bugs if `enhancement-pr-title` does not apply.)

- PR body: repo template, **Manual verification**, `Closes #<issue-number>`.

### 5. Manual verification handoff

Echo **Manual verification** from the PR for the user. When they confirm:

```bash
uv run python -m src.grocery_wizard dev record-manual-verification <issue-number>
```

Summarize changes and share the PR link.
