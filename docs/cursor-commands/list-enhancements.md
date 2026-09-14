# List enhancements

Show open items from the local enhancement backlog.

## Context

- Backlog file: `.local/grocery_wizard/enhancements.jsonl` (gitignored; local only).
- Ingredient edit logs (`.local/grocery_wizard/ingredient_edits.jsonl`) feed **`dev suggest-fixes`** for automatic parser suggestions; enhancements are **manual feature/fix ideas** you implement when you have time via **`/work-on-enhancement`**.

## Your task

1. Run:

```bash
uv run python -m src.grocery_wizard dev list-enhancements
```

2. If the user asked for closed/done items too:

```bash
uv run python -m src.grocery_wizard dev list-enhancements --all
```

3. Present the CLI output clearly (ID, area, title, status).

4. If there are open items, note: **`/work-on-enhancement <id>`** (e.g. `/work-on-enhancement enh_001`) to implement one.

Do not implement anything unless the user chooses an ID and asks you to work on it in this chat.
