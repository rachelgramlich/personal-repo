## Summary

Grocery list items are landing in the wrong store aisles — both from bad keyword coverage and from ingredient normalization leaving trailing prep text that prevents keyword matches. Update `store_aisles.txt` and classification logic so lists match an actual store walk.

Reproduced while testing a Crispy Potato Quesadillas plan + recurring/extra items (see #35).

**Prerequisite: #33** — aisle keywords cannot match until `- [ ]` / bullet prefixes are stripped (e.g. `[ ] Apple cider` → `Apple cider`).

## Misclassifications to fix

| Item | Current aisle | Should be |
|------|---------------|-----------|
| Apple cider | Fruit | **Drinks** (not fruit) |
| Canned peaches | Fruit | **Canned goods** |
| Raspberry jam (any jam) | Fruit | **Canned goods** |
| Canned corn | Vegetables | **Canned goods** |
| Peanut butter | Dairy & eggs | **Canned goods** |
| 1 lime, juiced | Other | **Fruit** |
| 1 pound potatoes, unpeeled… | Other | **Vegetables** |
| Applesauce | Other | **Canned goods** |
| Cold foam | Other | **Dairy** |
| Flowers | Other | **Flowers — first aisle, before Fruit** |
| Hand soap | Other | **Home goods — after Bakery, before Canned goods** |
| Lox pastrami kind | Other | **Meat & fish** |
| Mexican crema | Other | **Dairy** |
| Pesto | Other | **Refrigerated** |

## Walk order changes

Current order starts with Fruit. Proposed additions/reorder:

```
1. Flowers          ← new, first
2. Fruit
3. Vegetables
4. Refrigerated (cheese/tofu, pesto, …)
5. Canned drinks    ← apple cider here
6. Dairy & eggs     ← crema, cold foam
7. Meat & fish      ← lox
8. Bakery
9. Home goods       ← new: hand soap, etc.
10. Dry goods / cans / cereal / rice  ← canned peaches, jam, corn, peanut butter, applesauce
… (existing aisles follow)
```

Exact labels/order open to tweak, but **flowers before fruit** and **home goods after bakery, before canned** are requirements.

## Root causes

### 1. Missing keywords
`store_aisles.txt` lacks entries for: `jam`, `applesauce`, `peanut butter`, `apple cider`, `crema`, `lox`, `smoked salmon`, `pesto`, `flowers`, `hand soap`, `soap`, `canned peaches`, `canned corn`, `cold foam`, etc.

### 2. Normalization leaves prep text → keyword miss
Examples today:
- `1 lime, juiced` → `lime, juiced` → **Other** (keyword `lime` doesn't match)
- `1 pound potatoes, unpeeled but scrubbed clean` → `potatoes, unpeeled but scrubbed clean` → **Other** (keyword `potato` doesn't match)

Fix: strip trailing prep phrases (`juiced`, `unpeeled but…`, `diced`, `grated`, etc.) **before** aisle classification, or classify on `ingredient_name()` after stronger normalization.

### 3. `"canned"` keyword too broad / wrong priority
`canned corn` matches `corn` (vegetables) before `canned` (dry goods). Canned goods should win when line starts with or contains `canned` as a product descriptor.

### 4. `"raspberry"` in fruit beats `"jam"`
`raspberry jam` matches fruit keyword `raspberry` instead of canned/jam.

**Suggestion:** prefer longer/more-specific keywords, or add explicit compound keywords (`raspberry jam`, `canned peaches`, `canned corn`, `peanut butter`) under the correct aisle.

## Proposed work

1. **Add new aisle sections** to `store_aisles.txt`: `flowers`, `home_goods` (or similar)
2. **Reorder aisles** per walk order above
3. **Add keywords** for all misclassified items + compound phrases
4. **Improve classification priority** — canned/jam/drink compounds beat partial fruit/veg matches
5. **Strip prep suffixes** before `classify_aisle()` so `lime`, `potatoes`, etc. match
6. **Apply #33 strip helper** before classification so checklist prefixes don't break keyword match
7. **Tests** in `tests/src/grocery_wizard/shopping/test_store_aisles.py` for every row in the misclassification table

## Relevant files

- `src/grocery_wizard/config/store_aisles.txt` — aisle order + keywords
- `src/grocery_wizard/shopping/store_aisles.py` — `classify_aisle()`, `sort_grocery_items()`
- `src/grocery_wizard/ingredients/normalize.py` — prep text stripping
- `src/grocery_wizard/shopping/grocery_list.py` — `format_meals_and_grocery_list()`

## Related

- **#33 — prerequisite** (checklist stripping; shared normalizer)
- **#35** — sort order + dedup after strip
- **#37** — unexplained items (`peas`, `semi-soft cheese`) on list not visible in user's recipe

## Acceptance criteria

- [ ] Every item in the misclassification table lands in the correct aisle
- [ ] Flowers appears first; home goods after bakery, before canned
- [ ] `raspberry jam`, `canned corn`, `canned peaches` → canned goods (not fruit/veg)
- [ ] `apple cider` → drinks (not fruit)
- [ ] Normalized prep-heavy lines (`lime, juiced`, `potatoes, unpeeled…`) classify correctly
- [ ] Tests cover all cases + no regressions on existing aisle tests
