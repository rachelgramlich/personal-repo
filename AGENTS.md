# Agent instructions (grocery_wizard)

## Enhancement backlog

- **File (committed):** `src/grocery_wizard/dev/enhancements.jsonl`
- **List open items:** `uv run python -m src.grocery_wizard dev list-enhancements`
- **Implement one item:** `uv run python -m src.grocery_wizard dev work-on-enhancement <ID>`
  - Same as `dev show-enhancement <ID>` — prints the full implementation + ship checklist.
- **Add an item:** `uv run python -m src.grocery_wizard dev add-enhancement --title "…"`

When shipping an enhancement, the agent must set the PR title via `dev enhancement-pr-title <ID>` and run `dev complete-enhancement <ID>` so the backlog records the PR URL. Do not ask the user to run `close-enhancement` or edit the JSONL by hand.

### Cursor slash commands

Committed in **`.cursor/commands/`** (`/add-enhancement`, `/list-enhancements`, `/work-on-enhancement`). Cloud agents can read those files from the repo clone or use the CLI above.

Ingredient UI edit logs remain local-only: `.local/grocery_wizard/ingredient_edits.jsonl` (for `dev suggest-fixes`).
