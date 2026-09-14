# Add enhancement (local backlog)

Capture a feature idea or improvement in `.local/grocery_wizard/enhancements.jsonl` for later implementation.

## How this relates to other dev logs

| Workflow | Storage | How you pick it up |
|----------|---------|-------------------|
| Ingredient parser fixes | `.local/grocery_wizard/ingredient_edits.jsonl` (UI edits) | `uv run python -m src.grocery_wizard dev suggest-fixes` aggregates patterns for parser work |
| **Enhancement backlog** | `.local/grocery_wizard/enhancements.jsonl` | **Use Cursor:** `/list-enhancements` then `/work-on-enhancement <id>` |

Prefer **`/add-enhancement`** in Cursor over typing `dev add-enhancement` in a terminal; the CLI remains for scripts and non-Cursor environments.

## Your task

The user may put details **after** the command name (title, description, area). Use that text; if anything is missing, ask once, then proceed.

1. **Title** (required): short one-liner.
2. **Description** (optional): longer context, acceptance hints, links.
3. **Area** (optional, default `other`): one of `ui`, `parser`, `shopping`, `recipes`, `cli`, `other`.

4. Append the entry **non-interactively**:

```bash
uv run python -m src.grocery_wizard dev add-enhancement \
  --title "<title>" \
  --description "<description>" \
  --area <area>
```

(Omit `--description` or `--area` when empty / `other`.)

5. Confirm the printed ID (e.g. `enh_003`) and remind the user they can implement later with `/work-on-enhancement <id>`.

Do **not** start implementing the enhancement in this turn unless the user explicitly asks.
