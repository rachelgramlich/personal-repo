# Agent instructions (grocery_wizard)

## Enhancement backlog

- **Storage:** GitHub Issues with the **`grocery-wizard`** label (clean titles; no required prefix). Legacy issues may still match **Grocery Wizard** in the title until backfilled.
- **List open items:** `uv run python -m src.grocery_wizard dev list-enhancements`
- **Implement one item:** `uv run python -m src.grocery_wizard dev work-on-enhancement <issue-number>`
  - Same as `dev show-enhancement <issue-number>` — prints the full implementation + ship checklist.
  - Use the GitHub issue number (`96` / `#96`).
- **Add backlog item:** `uv run python -m src.grocery_wizard dev add-enhancement --title "…" --expected-behavior "…"` (applies **`grocery-wizard`** label; requires `gh`).
- **Backfill labels (once):** `uv run python -m src.grocery_wizard dev backfill-enhancement-labels` (optional `--strip-title-prefix`).
- **Report a bug:** `uv run python -m src.grocery_wizard dev report-bug …` (template **Bug report**; not the backlog).
- **Issue forms:** `.github/ISSUE_TEMPLATE/grocery_wizard_enhancement.yml`, `bug_report.yml`.

When shipping an enhancement, the agent must:

1. Set the PR title via `dev enhancement-pr-title <issue-number>`.
2. Fill the PR template **Manual verification** section and include `Closes #<issue-number>` in the PR body (GitHub closes the issue when the PR merges).
3. Ask the user to run manual verification (echo the PR section); when they confirm, run `dev record-manual-verification <issue-number>`.

Do not close backlog issues with `gh issue close` or ask the user to close issues by hand — merge the PR with `Closes #N`.

Legacy JSONL (if any) can be imported once: `dev migrate-enhancements-to-github`.

### Cursor slash commands

Committed in **`.cursor/commands/`** (`/add-enhancement`, `/list-enhancements`, `/work-on-enhancement`). Cloud agents can read those files from the repo clone or use the CLI above.

Ingredient UI edit logs remain local-only: `.local/grocery_wizard/ingredient_edits.jsonl` (for `dev suggest-fixes`).

After `just setup`, Streamlit’s `developing-with-streamlit` agent skill is available under `.cursor/skills/` for UI work.
