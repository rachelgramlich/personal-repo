# Agent instructions (grocery_wizard)

## Enhancement backlog

- **Storage:** GitHub Issues whose title contains **Grocery Wizard** (new issues get a `[Grocery Wizard]` prefix). No labels or `enh_NNN` IDs required.
- **List open items:** `uv run python -m src.grocery_wizard dev list-enhancements`
- **Implement one item:** `uv run python -m src.grocery_wizard dev work-on-enhancement <issue-number>`
  - Same as `dev show-enhancement <issue-number>` — prints the full implementation + ship checklist.
  - Use the GitHub issue number (`96` / `#96`).
- **Add an item:** `uv run python -m src.grocery_wizard dev add-enhancement --title "…"` (requires `gh`).

When shipping an enhancement, the agent must set the PR title via `dev enhancement-pr-title <issue-number>` and run `dev complete-enhancement <issue-number>` to close the issue and link the PR. Do not ask the user to close issues by hand.

Legacy JSONL (if any) can be imported once: `dev migrate-enhancements-to-github`.

### Cursor slash commands

Committed in **`.cursor/commands/`** (`/add-enhancement`, `/list-enhancements`, `/work-on-enhancement`). Cloud agents can read those files from the repo clone or use the CLI above.

Ingredient UI edit logs remain local-only: `.local/grocery_wizard/ingredient_edits.jsonl` (for `dev suggest-fixes`).
