## Summary

Improve the grocery list flow in the Streamlit UI: let users enter extra items **before** creating the list, clean up pasted checklist/markdown formatting, and add a way to **regenerate** the list after edits.

**This issue owns checklist/bullet stripping.** #35 and #36 depend on the shared normalizer from here.

## Current behavior

On **Create weekly plan → 2. Grocery list**:

1. **Before** creating: "Grocery list options" expander has sync/pantry toggles and **Recurring weekly items** only
2. User clicks **Create grocery list**
3. **After** creation: "Customize list" expander has pantry re-add multiselect and **Extra items (one per line)** — too late in the flow

Extra items are parsed via `_parse_line_items()` in `src/grocery_wizard/ui/app.py`, which strips simple bullet prefixes (`-`, `•`, `*`) but **not** markdown checklist syntax.

Pasting from Notion or a task list:
```
- [ ] Flowers
- [x] Milk
```
currently becomes something like `[ ] Flowers` instead of `Flowers`.

There is also no explicit action to regenerate/rebuild the list after customizing (re-adding pantry staples or pasting extra items). The only post-creation action is **Edit meals**, which clears the whole grocery result.

## Proposed changes

### 1. Move extra items before list creation

Add **Extra items (one per line)** to the **Grocery list options** expander, alongside recurring weekly items — visible **before** the **Create grocery list** button.

```
▼ Grocery list options
  ☐ Sync ingredients first
  ☐ Exclude pantry items
  Recurring weekly items: [text area]
  Extra items:            [text area]   ← new, same step
[ Create grocery list ]
```

Pass extra items into `_run_grocery_list_generation()` / `_compute_grocery_drafts()` at build time so they appear in the initial list.

Keep the post-creation customize expander for tweaking (re-add pantry staples, edit extras), but default extras from the pre-creation field.

### 2. Strip checklist / markdown dashes from pasted lines

Extend `_parse_line_items()` (or a shared helper) to normalize common pasted formats:

| Input | Output |
|-------|--------|
| `- [ ] Flowers` | `Flowers` |
| `- [x] Milk` | `Milk` |
| `[ ] Eggs` | `Eggs` |
| `- Flowers` | `Flowers` (already works) |

Suggested regex patterns to strip before item extraction:
- Optional leading `-`, `*`, or `•`
- Optional `[ ]`, `[x]`, `[X]` checkbox markers
- Trailing whitespace

Apply to **recurring weekly items**, **extra items**, and any other line-pasted lists using `_parse_line_items()`.

Export the helper so #35 (dedup/sort) and #36 (aisle classification) can reuse it — do not duplicate strip logic.

### 3. Add regenerate / update list action

After the grocery list is created, add a button to refresh the output without losing the meal plan:

| Button | Behavior |
|--------|----------|
| **Update list** (or **Regenerate list**) | Recompute final list from cached base items + current customize settings (re-add selections, extra items text). No re-scrape unless user opts in. |
| **Regenerate from recipes** (optional, secondary) | Re-run full `build_grocery_list()` with current plan + pre-creation options, preserving extra/recurring text fields |

Minimum viable: **Update list** so pasting extra items in Customize and clicking the button refreshes copy/download output.

### 4. Clear Streamlit widget keys when tearing down a list

Extra items persist across rebuilds because Streamlit keeps `grocery_additional_items` (and `grocery_readd`) in session state even when `grocery_result` is cleared. The text area ignores `value=` once the widget key exists.

Add `_clear_grocery_result()` that pops `grocery_result` **and** widget keys (`grocery_additional_items`, `grocery_readd`, `grocery_final_list`). Call it on Edit meals, plan rebuild/swap/regenerate, `_invalidate_stale_grocery_result()`, and before creating a new list.

## Relevant files

- `src/grocery_wizard/ui/app.py` — `_parse_line_items()`, `_compute_grocery_drafts()`, `_run_grocery_list_generation()`, `_render_grocery_result()`, `render_create_weekly_plan()`

## Related

- #35 — sort order + dedup (uses strip helper from this issue)
- #36 — aisle keyword fixes (classification requires stripped item names)
- #37 — unexplained items on list not visible in recipe

## Acceptance criteria

- [ ] Extra items field appears in Grocery list options **before** Create grocery list
- [ ] Extra items entered pre-creation are included in the initial generated list
- [ ] Pasted checklist lines like `- [ ] Flowers` normalize to `Flowers`
- [ ] User can regenerate/update the list after editing extras or re-adding pantry items
- [ ] Edit meals still works and clears grocery result as today
- [ ] Tests for `_parse_line_items()` checklist stripping
- [ ] Strip helper is shared/importable for #35 and #36

## Out of scope

- Changing pantry matching logic
- CLI grocery list flow (UI-only unless shared helper is reused)
