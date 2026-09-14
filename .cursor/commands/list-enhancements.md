# List enhancements

Show open items from the GitHub enhancement backlog.

## Context

- Backlog: GitHub Issues with label **`grocery-wizard`** (optional `gw-area-*` labels). Legacy imports may still carry **`grocery-wizard-enhancement`**.
- Ingredient edit logs (`.local/grocery_wizard/ingredient_edits.jsonl`) feed **`dev suggest-fixes`** for automatic parser suggestions; enhancements are **manual feature/fix ideas** you implement when you have time via **`/work-on-enhancement`**.

## Your task

1. Run (requires **`gh`**):

```bash
uv run python -m src.grocery_wizard dev list-enhancements
```

2. If the user asked for closed/done items too:

```bash
uv run python -m src.grocery_wizard dev list-enhancements --all
```

3. Present the CLI output clearly (issue #, ID, area, title, status, links).

4. If there are open items, note: **`/work-on-enhancement <id>`** (e.g. `/work-on-enhancement enh_005` or `/work-on-enhancement 84`) to implement one.

Do not implement anything unless the user chooses an ID and asks you to work on it in this chat.
