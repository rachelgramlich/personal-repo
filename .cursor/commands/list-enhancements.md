# List enhancements

Show open items from the GitHub enhancement backlog.

## Context

- Backlog: GitHub Issues with the **`grocery-wizard`** label (legacy title matches still listed during migration).
- Ingredient edit logs (`.local/grocery_wizard/ingredient_edits.jsonl`) feed **`dev suggest-fixes`** for automatic parser suggestions; backlog items are implemented via **`/work-on-issue`**.

## Your task

1. Run (requires **`gh`**):

```bash
uv run python -m src.grocery_wizard dev list-enhancements
```

2. If the user asked for closed/done items too:

```bash
uv run python -m src.grocery_wizard dev list-enhancements --all
```

3. Present the CLI output clearly (issue #, area, title, status, links).

4. If there are open items, note: **`/work-on-issue <issue-number>`** (e.g. `/work-on-issue 96`) to implement one.

Do not implement anything unless the user chooses an issue number and asks you to work on it in this chat.
