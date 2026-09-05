## Summary

The formatted grocery list copy output is out of store walk order and contains duplicates — especially when recurring/extra items are pasted from checklists.

## Example (actual output)

```
Grocery List
- [ ] Apple cider
- [ ] Apples
- [ ] Bananas
- [ ] Berries
...
- bananas
- berries
- fruit
- 1 jalapeño
- 1/2 red onions
- 2 carrots
- [ ] Asparagus
...
- milk
- [ ] Crusty bread for freezer
...
- [ ] Flowers
- Mexican crema
```

Problems visible here:
1. **Wrong order** — not grouped by store aisle walk order (fruit, vegetables, dairy, etc.)
2. **Duplicates** — `Bananas` / `bananas`, `Berries` / `berries`, `Milk` / `milk`
3. **Checklist junk** — `[ ]` prefix still on many lines

## Expected behavior

Items should be sorted by store aisle config (`src/grocery_wizard/config/store_aisles.txt`) then alphabetically within each aisle — same as `sort_grocery_items()` is designed to do.

Optionally, show aisle headers in the formatted output for easier in-store use:

```
Grocery List

Fruit
- Apple cider
- Apples
- Bananas
...

Vegetables
- Asparagus
- Carrots
...
```

## Likely root causes

### 1. Checklist prefix breaks classification & dedup
Recurring/extra items pasted as `- [ ] Bananas` are stored literally as `[ ] Bananas`.

- `classify_aisle()` uses `ingredient_name()` which does **not** strip `[ ]` → item lands in **Other** instead of Fruit
- Dedup in `_compute_grocery_drafts()` compares `item.lower()` → `[ ] bananas` ≠ `bananas` → duplicates

**Fix: implement #33 first** — import/share its strip helper; do not duplicate strip logic here.

### 2. Recurring items bypass ingredient normalization
Recipe ingredients are normalized via `normalize_ingredient()` / `format_grocery_item()` during collection. Recurring weekly items and extra items are appended as raw strings with only `.lower()` dedup — no normalization, no aisle-friendly display name.

### 3. Sort may not run on fully merged list
`_compute_grocery_drafts()` calls `sort_grocery_items()` at the end, but if items retain `[ ]` prefixes the sort key `(aisle_rank, item.lower())` groups all checklist items incorrectly.

### 4. Wrong aisle keywords (separate issue)
Even after strip + sort, many items land in the wrong aisle (apple cider → fruit, jam → fruit, etc.). Track keyword/walk-order fixes in **#36**.

## Proposed fix

1. **Normalize all list items before merge, dedup, and sort**
   - Strip checklist/bullet prefixes (**#33 shared helper**)
   - Run through `normalize_ingredient()` or `ingredient_name()` for consistent display
   - Dedup on normalized key, not raw string

2. **Ensure single sort pass on the final merged list**
   - Recipe items + recurring + extras + re-added pantry → one list → `sort_grocery_items()`

3. **Consider aisle headers in formatted output**
   - Use existing `group_grocery_items_by_aisle()` in `format_meals_and_grocery_list()`
   - Makes walk order obvious even when items are correct

## Relevant files

- `src/grocery_wizard/ui/app.py` — `_parse_line_items()`, `_compute_grocery_drafts()`
- `src/grocery_wizard/shopping/grocery_list.py` — `build_grocery_list()`, `format_meals_and_grocery_list()`
- `src/grocery_wizard/shopping/store_aisles.py` — `sort_grocery_items()`, `group_grocery_items_by_aisle()`, `classify_aisle()`

## Related

- **#33 — prerequisite** (checklist stripping, extra items before creation, regenerate button)
- **#36** — aisle misclassifications and walk order (after strip works)
- **#37** — unexplained items on list not visible in recipe

## Acceptance criteria

- [ ] Depends on #33 strip helper being implemented first
- [ ] Final grocery list follows store aisle walk order
- [ ] No duplicate items that differ only by checklist prefix or capitalization
- [ ] Recurring and extra items classify into the correct aisle (not all dumped in Other)
- [ ] Copy/download output matches the sorted order shown in the UI
- [ ] Tests for sort + dedup with checklist-prefixed and mixed-case inputs

## Out of scope

- Store aisle keyword config changes (see #36)
- Pantry matching rules
