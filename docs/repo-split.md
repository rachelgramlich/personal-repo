# Repository split (2026)

**Grocery Wizard** stays in this repository. After merge, rename it on GitHub to **`grocery-wizard`** so issues and history stay put.

Personal snippets live in a separate repo: **[`rg-playground`](https://github.com/rachelgramlich/rg-playground)**.

## After merging the split PR

1. GitHub → **Settings → General → Repository name** → `grocery-wizard`.
2. Create an empty repo **`rg-playground`** (no README/license if you will push an existing tree).
3. Push the playground tree (see `rg-playground` README for layout).
4. Local remotes:
   ```shell
   git remote set-url origin git@github.com:rachelgramlich/grocery-wizard.git
   ```
5. Cursor Cloud environment: point at `grocery-wizard` if it still references the old name.

## What moved to `rg-playground`

| Path | Notes |
| --- | --- |
| `src/python_practice/` | Practice exercises |
| `src/fisher_jenks_natural_breaks/` | Fisher Jenks scratch (not runnable without BigQuery env) |
| `src/color_calendar_events/` | Calendar color helper (JS) |
