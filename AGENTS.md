# Agent instructions (grocery_wizard)

## Enhancement backlog

Backlog items are **GitHub Issues**, not a committed JSONL file (`enhancements.jsonl` was removed in [#88](https://github.com/rachelgramlich/personal-repo/pull/88)).

- **Storage:** GitHub Issues with label `grocery-wizard` (optional area labels `gw-area-*`). Legacy imports may still carry `grocery-wizard-enhancement`.
- **List open items:** `uv run python -m src.grocery_wizard dev list-enhancements`
- **Implement one item:** `uv run python -m src.grocery_wizard dev work-on-enhancement <ID>`
  - Same as `dev show-enhancement <ID>` — prints the full implementation + ship checklist.
  - `<ID>` is `enh_001` style or a GitHub issue number (`84` / `#84`).
- **Add an item:** `uv run python -m src.grocery_wizard dev add-enhancement --title "…"` (requires `gh`).

When shipping an enhancement, the agent must set the PR title via `dev enhancement-pr-title <ID>` and run `dev complete-enhancement <ID>` to close the issue and link the PR. Do not ask the user to close issues by hand.

Legacy JSONL (if any) can be imported once: `dev migrate-enhancements-to-github`.

### Cursor slash commands

Committed in **`.cursor/commands/`** (`/add-enhancement`, `/list-enhancements`, `/work-on-enhancement`). Cloud agents can read those files from the repo clone or use the CLI above.

Ingredient UI edit logs remain local-only: `.local/grocery_wizard/ingredient_edits.jsonl` (for `dev suggest-fixes`).
