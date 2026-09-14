# Grocery Wizard config files

Paths and env loading live in `__init__.py`. This folder mixes **repo-backed product config** with **personal lists** that are moving off git.

## What stays in the repo

| File | Role |
|------|------|
| **`store_aisles.txt`** | Source of truth for store walk order, aisle labels, and ingredient keywords. Edit here and commit — same section-header style as `pantry.txt`. |
| **`__init__.py`** | Notion credentials, optional future Notion database IDs, and paths to the files below. |

`store_aisles.txt` should **not** move to Notion; it is shared app configuration, not personal household data.

## Personal data (pantry, recurring, weekly plans)

These change often. Committing them forces manual PRs and does not help cloud agents (they have secrets and Notion, not your laptop’s `.local/`).

**Direction:** keep recipes in the existing Notion **Recipes** database; add separate Notion databases (or equivalent pages) for:

| Data | Today (code) | Target |
|------|----------------|--------|
| Pantry staples | `pantry.txt` (committed) | Notion pantry database; **Name** (+ optional **Section**). |
| Recurring weekly items | `recurring_weekly_items.txt` (committed) | Notion recurring database; one row per item (**Name**, optional **Active** / **Sort**). |
| Saved weekly meal plans | `saved_weekly_plans.csv` (committed) | Notion weekly-plans database; **Name** (e.g. `2026-09-14_plan_v1`), **Week start**, **Version**, **Recipes** (relation or text). No separate slug — name is the id. |
| Current week (session) | `.local/grocery_wizard/week_plan.json` | Latest plan for the current week in Notion, or optional local cache only. |

Until Notion backends exist, the app reads the committed `.txt` / `.csv` files. Those files may remain as **empty or example fallbacks** for clones without extra Notion database IDs.

### Recurring items: template vs one run

Two scopes (do not conflate):

1. **Template** — default list every grocery run (today: `recurring_weekly_items.txt`; future: Notion recurring DB).
2. **This run only** — additions/removals for a single session; must not update the template unless the user explicitly edits defaults.

Pantry edits from the UI similarly distinguish one-off vs changing the saved staple list.

## File formats (current)

- **`pantry.txt`** — one item per line; `#` comments; `# --- section: Label ---` headers for grouped display.
- **`recurring_weekly_items.txt`** — one item per line; `#` comments ignored; checklist prefixes stripped on load.
- **`saved_weekly_plans.csv`** — columns `date`, `version`, `name`, `slug`, `recipes` (`|`‑separated recipe names). `slug` duplicates `name` and should be dropped when plans move to Notion.

## Notion env (recipes today; more when implemented)

Required today: `NOTION_API_KEY`, `NOTION_RECIPE_DATABASE_ID` (Recipes). `NOTION_DATABASE_ID` is still accepted as a legacy alias.

Optional (Notion backends for #96): `NOTION_PANTRY_DATABASE_ID`, `NOTION_RECURRING_WEEKLY_DATABASE_ID`, `NOTION_WEEKLY_MEAL_PLANS_DATABASE_ID` — same integration as recipes.
