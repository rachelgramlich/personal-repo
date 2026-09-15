# Grocery Wizard config files

Paths and env loading live in `__init__.py`. This folder holds **shared product config** only; personal household data lives in Notion.

## What stays in the repo

| File | Role |
|------|------|
| **`store_aisles.txt`** | Source of truth for store walk order, aisle labels, and ingredient keywords. Edit here and commit — section headers like `# --- Produce ---`. |
| **`__init__.py`** | Notion credentials and database IDs. |

`store_aisles.txt` should **not** move to Notion; it is shared app configuration, not personal household data.

## Personal data (Notion only)

Pantry staples, recurring weekly items, and saved weekly meal plans live in **Notion databases** (same integration as Recipes). They are **not** committed in this repo.

| Data | Notion database | Properties |
|------|-----------------|------------|
| Pantry staples | Pantry | **Name** (title), **Section** (select — store aisle labels from `store_aisles.txt`) |
| Recurring weekly items | Recurring | **Name** (title) only |
| Saved weekly meal plans | Weekly plans | **Name**, **Week start**, **Version**, **Recipes** (relation → Recipes) |

Plan **Name** is the sole identifier (e.g. `2026-09-13_plan_v1`); no slug column.

Current-week session state may still use `.local/grocery_wizard/week_plan.json` (gitignored) until fully Notion-backed for “this session” if needed.

### Recurring items: template vs one run

1. **Template** — default list every grocery run (Notion recurring DB).
2. **This run only** — additions/removals for a single session; must not update the template unless the user explicitly edits defaults.

Pantry edits from the UI similarly distinguish one-off vs changing the saved staple list in Notion.

## Notion env

Required for Grocery Wizard:

- `NOTION_API_KEY`
- `NOTION_RECIPE_DATABASE_ID` (legacy alias `NOTION_DATABASE_ID`)
- `NOTION_PANTRY_DATABASE_ID`
- `NOTION_RECURRING_WEEKLY_DATABASE_ID`
- `NOTION_WEEKLY_MEAL_PLANS_DATABASE_ID`

Cloud agents use the same names as Secrets.

### Pantry `Section` select options

After creating the pantry database (with a **Section** column), sync select options from the committed aisle config:

```bash
uv run python -m src.grocery_wizard dev sync-notion-pantry-sections
```

Use `--dry-run` to preview. The command sets **Section** to a **select** whose options are the display labels in `store_aisles.txt` (e.g. `Fruit`, `Dry goods`, `Other`) and normalizes existing rows to those labels. Re-run whenever you add or rename aisles in `store_aisles.txt`.
