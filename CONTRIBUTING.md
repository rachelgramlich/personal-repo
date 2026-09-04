# Contributing & Code Review Guide

This document codifies the coding standards enforced in this repository. All changes should pass the automated checks described here before review.

---

## Automated Checks

Run everything locally before pushing:

```bash
just check        # lint + tests
just format       # auto-format with ruff
just lint         # ruff check --fix
just test         # pytest
just pre-commit   # all pre-commit hooks
```

The CI equivalent is the pre-commit hook suite (ruff + ruff-format + trailing-whitespace + end-of-file-fixer + yaml/merge-conflict checks).

---

## Ruff Lint Rules

Ruff is the single linting tool. The enabled rule categories are documented in `pyproject.toml`. A summary of what each category enforces:

| Category | What it catches |
|---|---|
| `E` / `F` | pycodestyle errors, unused imports, undefined names |
| `I` | import ordering (isort-style) |
| `UP` | deprecated Python patterns — use modern syntax |
| `B` | bugbear — common footguns (mutable defaults, loop variable rebind) |
| `N` | PEP 8 naming: `ClassName`, `function_name`, `CONSTANT`, `_private` |
| `SIM` | simplifiable conditions — merge nested `if`, use `any()`/`all()` |
| `RUF` | ruff-specific: mutable class defaults, unsorted `__all__`, ambiguous Unicode |
| `C4` | use comprehensions/generators instead of `list(map(...))` |
| `PIE` | miscellaneous improvements — no unnecessary `pass`, prefer `isinstance(..., (...))` |
| `RET` | return statement hygiene — no `else` after `return`, no dead assignments |
| `ISC` | no implicit string concatenation on the same line |
| `PGH` | no bare `# type: ignore`, no unqualified `# noqa` |
| `DTZ` | timezone-aware datetimes — always pass `tz=UTC` or use `datetime.now(UTC)` |
| `PERF` | performance — `list.extend` over loops, list comprehensions, dict comprehensions |
| `FLY` | f-strings over `str.join` and `%`-formatting |
| `PT` | pytest style — use `pytest.raises`, tuple args for `parametrize`, no manual `assert raised` |
| `PLR` / `PLE` / `PLW` | pylint equivalents — merge comparisons, no loop-variable shadowing, use `elif` |
| `TRY` | tryceratops — move success path to `else`, not `try` body |
| `EM` | no f-strings or literals as the first arg to `raise Exception(...)` |
| `FURB` | modernise patterns — `path.read_text()`, `x or y` over `x if x else y` |

### Ignored rules (with rationale)

| Rule | Rationale |
|---|---|
| `EM101` / `EM102` / `TRY003` | Inline exception messages are fine for simple errors; the full EM/TRY separation is invasive |
| `PLR2004` | Magic value comparisons are permitted in test files (`tests/**` override) |
| `PLR0912/13/15/11` | Complexity thresholds — large orchestration functions are acceptable; prefer refactoring when adding code rather than suppressing |
| `SIM108` | Ternary expressions — prefer explicit `if/else` when it reads more clearly |

### Adding `# noqa` comments

Only suppress a rule when the code is intentionally violating it and the violation cannot be fixed:

```python
_UNICODE_DASHES = ("–", "—", "−")  # noqa: RUF001  # intentional Unicode chars
```

Always include a comment explaining why the suppression is justified.

---

## Code Structure Standards

### Type annotations

- Every public function must have a return type annotation.
- Use `from __future__ import annotations` at the top of every module (PEP 563 — deferred evaluation).
- Prefer concrete types over `Any`. Use `TypedDict` or dataclasses when a `dict[str, Any]` has a fixed shape.

```python
# Bad
def load_feedback(path: Path) -> list[dict[str, Any]]: ...


# Good
class FeedbackEntry(TypedDict):
    timestamp: str
    command: str
    feedback: str


def load_feedback(path: Path) -> list[FeedbackEntry]: ...
```

### Type aliases

Use the `type` keyword (Python 3.12+) for named type aliases:

```python
type FilterValue = str | list[str] | bool | None
```

### Structured data — prefer dataclasses or TypedDict over dicts

- Use `@dataclass` (or `@dataclass(frozen=True, slots=True)` for value objects) instead of raw dicts where the shape is known.
- Use `TypedDict` for dict shapes that cross API boundaries or are stored as JSON.
- Add `slots=True` to frozen dataclasses to reduce memory overhead and prevent accidental attribute assignment:

```python
@dataclass(frozen=True, slots=True)
class ScrapedRecipe:
    title: str
    ingredients: list[str]
    link: str | None = None
```

### `__all__`

Every public module must define `__all__` listing its public API. This makes re-export intent explicit and helps linters flag accidental name leakage.

```python
__all__ = ["MyClass", "public_function"]
```

---

## Exception Naming

Exception classes must end with `Error` (PEP 8 / ruff `N818`):

```python
# Bad
class NytSyncCancelled(Exception): ...


# Good
class NytSyncCancelledError(Exception): ...
```

---

## Function Signature Conventions

### Keyword-only arguments

When a function takes more than 5 positional arguments, or when argument order is not obvious from names alone, make the extra arguments keyword-only with `*`:

```python
def _resolve_slot_interactive(
    pool: list[Recipe],
    plan_recipes: list[Recipe],
    *,
    accepted_names: set[str],
    rejected_names: set[str],
    schema,
    prompt_fn: Callable[[str], str],
) -> Recipe | None: ...
```

### Boolean arguments

Prefer keyword-only boolean flags to avoid call-site ambiguity:

```python
# Bad
run_grocery_list(db, True, False)

# Good
run_grocery_list(db, quiet=True, exclude_pantry=False)
```

---

## Import Conventions

### Ordering

Ruff (`I`) enforces isort-style ordering automatically: stdlib → third-party → local, alphabetically within each group.

### No lazy imports inside function bodies

Imports inside function bodies are only acceptable to break true circular imports. The import must be accompanied by a comment explaining the circular dependency. All other imports belong at the top of the module.

```python
# Bad — use at top-level instead
def format_sync_message(summary: SyncSummary) -> str:
    from src.grocery_wizard.ingredients.sync import format_sync_summary

    return format_sync_summary(summary)


# Good
from src.grocery_wizard.ingredients.sync import format_sync_summary


def format_sync_message(summary: SyncSummary) -> str:
    return format_sync_summary(summary)
```

### No importing private symbols from other modules

Leading-underscore names are private to their module. If another module needs them, either:
1. Promote the symbol to public (remove the underscore, add to `__all__`), or
2. Move the shared logic to a new module that both can import.

```python
# Bad
from src.grocery_wizard.recipes.scraper import _looks_fragmented

# Good — after promoting to public in scraper.py
from src.grocery_wizard.recipes.scraper import looks_fragmented
```

---

## Control Flow

### Return conditions directly

```python
# Bad
if condition:
    return True
return False

# Good
return condition
```

### Use `else` on `try` for the success path

```python
# Bad (TRY300)
try:
    result = risky_call()
    return result.value
except SomeError:
    handle()

# Good
try:
    result = risky_call()
except SomeError:
    handle()
else:
    return result.value
```

### Use `any()` / `all()` over loops

```python
# Bad
for item in items:
    if predicate(item):
        return True
return False

# Good
return any(predicate(item) for item in items)
```

### Use `list.extend` over repeated `append`

```python
# Bad
for item in items:
    result.append(transform(item))

# Good
result.extend(transform(item) for item in items)
```

---

## Datetime

Always use timezone-aware datetimes. Import and pass `UTC` explicitly:

```python
from datetime import UTC, datetime

timestamp = datetime.now(UTC).isoformat()
```

---

## Testing

### pytest style

- Use `pytest.raises` for asserting exceptions — not a `try/except` with a `raised` flag.
- Use `tuple` for multi-argument `@pytest.mark.parametrize` first args: `("arg1", "arg2")` not `"arg1, arg2"`.
- Remove duplicate test cases in `@pytest.mark.parametrize`.
- Prefix unused unpack targets with `_`: `_items, _excluded, summary = call(...)`.

```python
# Bad
try:
    risky()
    raised = False
except MyError as exc:
    raised = True
    assert "message" in str(exc)
assert raised

# Good
with pytest.raises(MyError, match="message"):
    risky()
```

### String literals in tests

Use f-strings or plain literals instead of `"\n".join([...])` for short multi-line strings:

```python
# Bad
text = "\n".join(["line one", "line two", "line three"])

# Good
text = "line one\nline two\nline three"
```

---

## File Organization

```
src/grocery_wizard/
├── cli/          # argparse entry points only — no business logic
├── config/       # Config dataclass + data files (pantry, aisles, recurring)
├── dev/          # Developer/maintenance commands (audit, validate)
├── ingredients/  # Ingredient parsing, normalization, Notion sync
├── integrations/ # External API clients (Notion, NYT Cooking)
├── lib/          # Shared utilities (prompts, feedback)
├── planning/     # Meal planning flows
├── recipes/      # Scraping, classification, add-recipe flow
├── shopping/     # Grocery list, pantry, aisle sorting
└── ui/           # Streamlit app
```

- Keep modules focused: a file that grows beyond ~400 lines of business logic is a signal to split.
- Separate data models (`@dataclass` / `TypedDict`) from logic functions.
- `__init__.py` re-exports the package's public surface via `__all__`.

---

## Pre-commit and CI

Pre-commit hooks run automatically on every commit:
- `ruff` with `--fix` (lint + auto-fix)
- `ruff-format` (formatting)
- `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`, `check-merge-conflict`

To run all hooks manually:

```bash
just pre-commit
```

The pre-commit hook version in `.pre-commit-config.yaml` must match the `ruff>=` version floor in `pyproject.toml`.
