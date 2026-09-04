# Grocery Wizard

Notion-driven recipe tool: add recipes, plan meals, generate grocery lists.

## What do I run?

All commands run from the repo root:

```shell
uv run python -m src.grocery_wizard.cli <command>
```

### I found a new recipe online

```shell
uv run python -m src.grocery_wizard.cli add-recipe https://example.com/my-recipe
```

Saves the recipe to Notion and scrapes ingredients from the page.

### I need to plan dinners for the week

```shell
uv run python -m src.grocery_wizard.cli plan-recipes
```

Picks dinners interactively and saves your choices to `.local/grocery_wizard/week_plan.json`.

### I want my shopping list

```shell
uv run python -m src.grocery_wizard.cli create-grocery-list
```

Uses your saved week plan. No flags needed — it walks you through:

1. Backfill prompt if any planned recipes are missing ingredients
2. Shows pantry staples it left off (numbered)
3. Lets you paste extra items
4. Lets you add staples back if you need them
5. Prints the final list

**Optional flags** (most people never need these):

| Flag | When to use it |
|------|----------------|
| `--recipes "A,B"` | Skip the week plan and use specific recipe names |
| `--include-staples` | Keep salt, oil, etc. on the list instead of excluding them |
| `--backfill-missing` | Scrape missing ingredients without asking first |
| `--quiet` | Just the list — no excluded-staples display or re-add prompt |

### My pantry staples changed

```shell
uv run python -m src.grocery_wizard.cli edit-pantry
```

Edit `src/grocery_wizard/config/pantry.txt` — items here won't show up on your shopping list.

## Command cheat sheet

| Command | What it does |
|---------|--------------|
| `add-recipe` | Save a new recipe from a URL into Notion |
| `plan-recipes` | Pick dinners for the week (saves week_plan.json) |
| `create-grocery-list` | Build your shopping list from this week's plan |
| `edit-pantry` | Edit what's always in your kitchen (won't appear on shopping list) |

### Dev / maintenance commands

Use when you edit Notion directly, need to refresh ingredient data, or debug schema issues.

| Command | What it does |
|---------|--------------|
| `dev backfill-ingredients` | Fill in missing ingredient lists from recipe links |
| `dev reconcile-ingredients` | Update ingredients where you already have some (keeps your edits) |
| `dev refresh-all-ingredients` | Re-download ingredients for every recipe |
| `dev audit-recipes` | Show which recipes need attention |
| `dev show-schema` | Show how Notion columns are detected |

```shell
# Recipes added in Notion with a link but no ingredients
uv run python -m src.grocery_wizard.cli dev backfill-ingredients

# Preview without writing
uv run python -m src.grocery_wizard.cli dev backfill-ingredients --dry-run

# Reconcile recipes you already edited in Notion
uv run python -m src.grocery_wizard.cli dev reconcile-ingredients

# Nuclear option: re-scrape everything
uv run python -m src.grocery_wizard.cli dev refresh-all-ingredients

# Health check
uv run python -m src.grocery_wizard.cli dev audit-recipes
uv run python -m src.grocery_wizard.cli dev show-schema
```

## Project layout

Grocery Wizard is a package under `src/grocery_wizard/`. Folders group code by **what it does**; tests mirror the same folders under `tests/src/grocery_wizard/`.

### Source (`src/grocery_wizard/`)

| Folder | Key files | Responsibility |
|--------|-----------|----------------|
| `cli/` | `main.py` | Command-line entry (`add-recipe`, `plan-recipes`, `create-grocery-list`, `edit-pantry`, `dev …`) |
| `ui/` | `app.py` | Streamlit app (partial — Plan Meals tab is still a stub) |
| `config/` | `__init__.py`, `pantry.txt` | Env settings, paths, committed pantry staples |
| `integrations/` | `notion.py` | Notion API client and recipe model |
| `recipes/` | `scraper.py`, `classify.py`, `add_recipe.py` | Scrape URLs, classify metadata, save new recipes |
| `ingredients/` | `normalize.py`, `sync.py` | Parse/normalize ingredient lines; sync to Notion |
| `planning/` | `meal_planner.py` | Interactive weeknight dinner planner |
| `shopping/` | `grocery_list.py`, `pantry.py` | Build shopping list; pantry load/match/edit |
| `dev/` | `audit.py` | Recipe health checks |
| `lib/` | `prompts.py` | Shared interactive prompts |

### Tests (`tests/src/grocery_wizard/`)

Same subfolders as source — e.g. `recipes/test_scraper.py` tests `recipes/scraper.py`.

### Local runtime data (gitignored)

| Path | Purpose |
|------|---------|
| `.local/grocery_wizard/week_plan.json` | This week's planned recipe names |
| `.env` | `NOTION_API_KEY`, `NOTION_DATABASE_ID` (see `.env.example`) |

### Entry points

```shell
# CLI (primary)
uv run python -m src.grocery_wizard.cli <command>

# Streamlit (secondary)
just grocery-ui
# or: uv run streamlit run src/grocery_wizard/ui/app.py
```

```
personal-repo/
├── src/grocery_wizard/          # package (table above)
├── tests/src/grocery_wizard/    # tests (mirrors package folders)
└── .local/grocery_wizard/       # your week plan (not committed)
```

## Architecture notes

## How ingredients are stored

Ingredients are scraped **once** and stored in Notion's `Ingredients` column — the full scraped list, including pantry staples:

1. **Add recipe** — scrapes the URL and saves all raw ingredient lines to `Ingredients`
2. **Grocery list** — reads `Ingredients` from Notion; normalizes and excludes pantry staples by default

Normalization and pantry exclusion happen at grocery-list time only — not when adding or syncing to Notion.

## One-time setup

1. Create a [Notion integration](https://www.notion.so/my-integrations) and copy the API key.
2. Share your **Recipes** database with the integration (⋯ → Connections).
3. Copy `.env.example` to `.env` and fill in:
   - `NOTION_API_KEY` — integration secret
   - `NOTION_DATABASE_ID` — your Recipes database ID
4. From repo root: `just setup`
5. Verify: `uv run python -m src.grocery_wizard.cli dev show-schema`

## Meal planning

`plan-recipes` asks how many meals you want (default 7, or `--meals` / `GROCERY_WIZARD_DEFAULT_MEALS`). You can optionally name specific meals first; those are fuzzy-matched and locked in before filters run.

Default filters (override with **Change filters? [y/N]**):

| Filter | Default |
|--------|---------|
| Meal | Dinner |
| Dinner: Weeknight Friendly | yes |

Suggestions maximize variety across **Protein**, **Dinner Category**, and **Cuisine**. Saved plan: `{"recipes": ["Name1", "Name2", ...]}` in `.local/grocery_wizard/week_plan.json`.

## Configuration vs local data

Committed config lives in the package; per-week data stays local:

| Path | Committed? | Purpose |
|------|------------|---------|
| `src/grocery_wizard/config/pantry.txt` | yes | Pantry staples excluded from grocery lists |
| `src/grocery_wizard/config/recurring_weekly_items.txt` | yes | Items added to every grocery list |
| `src/grocery_wizard/config/store_aisles.txt` | yes | Store walk order, aisle labels, and ingredient keywords |
| `src/grocery_wizard/config/__init__.py` | yes | Env vars, Notion IDs, file paths |
| `.local/grocery_wizard/week_plan.json` | no | This week's planned recipes |

## Pantry staples

`edit-pantry` edits `src/grocery_wizard/config/pantry.txt`, grouped by section headers. Interactive options:

- **a** — add an item (pick a section or create one)
- **r** — remove by number or name
- **e** — open `src/grocery_wizard/config/pantry.txt` in `$EDITOR`
- **q** — save and quit

Matching uses phrase boundaries: `kosher salt` matches pantry item `salt`, but `beef` does not match `beef stock`.

## Recurring weekly items

`config/recurring_weekly_items.txt` lists items added every week (berries, bananas, milk, etc.). During `create-grocery-list`, you can accept, edit, or skip them for the current week — and optionally save edits back to the config file for future weeks.

## Grocery list aisle order

`create-grocery-list` sorts items by store walk order and prints aisle section headers. Edit `src/grocery_wizard/config/store_aisles.txt` to change walk order, labels, or keywords — same section-header style as `pantry.txt`:

```text
# --- fruit: Fruit ---
banana
berries

# --- vegetables: Vegetables ---
onion
garlic
...
```

Unmatched items land in **Other** (always last). Longer keyword phrases win over shorter ones (`potato chips` → snacks, not produce).

## Streamlit UI

```shell
just grocery-ui
# or: uv run streamlit run src/grocery_wizard/ui/app.py
```

Tabs: Add Recipe, Plan Meals, Grocery List.

## Supported recipe sources

Most recipe blogs with structured HTML or JSON-LD work well. TikTok and Instagram are **partially supported** — ingredients must appear in the caption text. When scraping fails, paste ingredients manually into Notion or use a blog link.

## Notion database schema (auto-detected)

Key columns:

| Column | Type | Used for |
|--------|------|----------|
| Name | title | Recipe name |
| Link | url | Source URL |
| Ingredients | rich_text | Full raw ingredient lines |
| Meal | select | Breakfast, Lunch, Dinner, … |
| Protein | multi_select | Chicken, Fish, Beans, … |
| Cuisine | multi_select | Italian, Asian, Mexican, … |
| Dinner Category | multi_select | Curry, Pasta, Bowl, … |
| Dinner: Weeknight Friendly | checkbox | Meal-planning filter |

Optional env overrides: `GROCERY_WIZARD_NAME_COLUMN`, `GROCERY_WIZARD_LINK_COLUMN`, `GROCERY_WIZARD_INGREDIENTS_COLUMN`.
