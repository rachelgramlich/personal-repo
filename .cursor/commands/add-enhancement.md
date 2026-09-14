# Add enhancement (GitHub issue)

**Scope: backlog capture only.** Create one GitHub issue with **Grocery Wizard** in the title and stop. Implementation is **`/work-on-enhancement <issue-number>`**, not this command.

## Do not explore or implement

In this turn you must **not**:

- Search, grep, or read the codebase (no `src/`, `tests/`, configs, or other repo files).
- Run `dev work-on-enhancement`, `dev show-enhancement`, `dev list-enhancements`, or any command except `dev add-enhancement`.
- Create branches, commits, pull requests, or todos for implementation work.
- Start coding, planning implementation, or summarizing how the feature would be built.

The only required action is the **`dev add-enhancement`** CLI below (plus at most one clarifying question if the title is missing). Requires **`gh`** authenticated for this repo.

## How this relates to other dev logs

| Workflow | Storage | How you pick it up |
|----------|---------|-------------------|
| Ingredient parser fixes | `.local/grocery_wizard/ingredient_edits.jsonl` (UI edits) | `uv run python -m src.grocery_wizard dev suggest-fixes` aggregates patterns for parser work |
| **Enhancement backlog** | GitHub Issues (`Grocery Wizard` in title) | `/list-enhancements` then `/work-on-enhancement <issue-number>` |

Prefer **`/add-enhancement`** in Cursor over typing `dev add-enhancement` in a terminal; the CLI remains for scripts and non-Cursor environments.

## Your task

The user may put details **after** the command name (title, description, area). Use that text; if the title is missing, ask once for a short title, then proceed.

1. **Title** (required): short one-liner (CLI adds `[Grocery Wizard]` if missing).
2. **Description** (optional): longer context, acceptance hints, expected behavior / manual test steps (same fields as the GitHub **Grocery Wizard enhancement** issue template).
3. **Area** (optional, default `other`): one of `ui`, `parser`, `shopping`, `recipes`, `cli`, `other`.

4. Create the issue **non-interactively** (this is the only command you run):

```bash
uv run python -m src.grocery_wizard dev add-enhancement \
  --title "<title>" \
  --description "<description>" \
  --area <area>
```

(Omit `--description` or `--area` when empty / `other`.)

5. Reply briefly: confirm the GitHub issue number, the issue URL, and that they can implement later with `/work-on-enhancement <issue-number>`.

Do **not** implement the enhancement in this turn unless the user explicitly asks you to switch to implementation after the issue exists.
