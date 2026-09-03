"""Flow 0: Add recipe URLs to Notion."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from src.grocery_wizard.integrations.notion import NotionRecipesDB
from src.grocery_wizard.lib.prompts import confirm_no_default
from src.grocery_wizard.recipes.classify import classify_recipe
from src.grocery_wizard.recipes.scraper import ScrapeError, ingredients_to_text, scrape_recipe


def add_recipes_from_urls(
    db: NotionRecipesDB,
    urls: list[str],
    *,
    prompt: Callable[[str], str] | None = None,
    confirm: Callable[[str], bool] | None = None,
    select_option: Callable[[str, list[str], str | None], str | None] | None = None,
) -> list[str]:
    """Add recipes for each URL. Returns list of created page IDs."""
    prompt_fn = prompt or _default_prompt
    confirm_fn = confirm or confirm_no_default
    select_fn = select_option or _default_select_option

    created_ids: list[str] = []
    schema = db.schema

    for url in urls:
        url = url.strip()
        if not url:
            continue

        existing = db.find_by_link(url)
        if existing:
            print(f"Skipping duplicate URL (already in Notion as '{existing.name}'): {url}")
            continue

        print(f"\nScraping: {url}")
        try:
            scraped = scrape_recipe(url)
        except ScrapeError as exc:
            print(f"Could not scrape recipe: {exc}")
            continue

        filter_columns = [(col.name, col.type, col.options) for col in schema.filter_columns]
        inferred = classify_recipe(scraped.title, scraped.ingredients, filter_columns)

        field_values: dict[str, Any] = {
            schema.name_column: scraped.title,
            schema.link_column: url,
        }
        if schema.ingredients_column:
            field_values[schema.ingredients_column] = ingredients_to_text(scraped.ingredients)

        for column_name, value in inferred.items():
            field_values[column_name] = value

        reviewed = _review_fields(
            db=db,
            field_values=field_values,
            prompt_fn=prompt_fn,
            select_fn=select_fn,
        )
        if reviewed is None:
            print("Skipped.")
            continue

        if not confirm_fn("Create this recipe in Notion?"):
            print("Skipped.")
            continue

        recipe = db.create_recipe(reviewed)
        created_ids.append(recipe.page_id)
        print(f"Created: {recipe.name}")

    return created_ids


def _review_fields(
    db: NotionRecipesDB,
    field_values: dict[str, Any],
    prompt_fn: Callable[[str], str],
    select_fn: Callable[[str, list[str], str | None], str | None],
) -> dict[str, Any] | None:
    schema = db.schema
    reviewed: dict[str, Any] = {}

    ordered_fields = [schema.name_column, schema.link_column]
    if schema.ingredients_column:
        ordered_fields.append(schema.ingredients_column)
    ordered_fields.extend(col.name for col in schema.review_columns)

    for field_name in ordered_fields:
        if field_name not in field_values and field_name not in schema.all_columns:
            continue

        column = schema.all_columns.get(field_name)
        current = field_values.get(field_name)

        if column and column.type in ("select", "status"):
            options = [""] + column.options
            current_str = current if isinstance(current, str) else None
            picked = select_fn(field_name, options, current_str)
            if picked is None:
                return None
            reviewed[field_name] = picked if picked else None

        elif column and column.type == "multi_select":
            current_list = current if isinstance(current, list) else []
            picked = _prompt_multi_select(field_name, column.options, current_list, prompt_fn)
            if picked is None:
                return None
            reviewed[field_name] = picked

        elif column and column.type == "checkbox":
            picked = _prompt_checkbox(field_name, current, prompt_fn)
            if picked is None:
                return None
            reviewed[field_name] = picked

        elif field_name == schema.ingredients_column:
            picked = _prompt_ingredients(field_name, current, prompt_fn)
            if picked is None:
                return None
            reviewed[field_name] = picked

        else:
            display = _format_value(current)
            print(f"\n{field_name}:\n{display or '(empty)'}")
            new_value = prompt_fn(f"  Enter value for {field_name} (Enter to keep): ")
            reviewed[field_name] = new_value if new_value else current

    return reviewed


def _prompt_ingredients(
    field_name: str,
    current: Any,
    prompt_fn: Callable[[str], str],
) -> str | None:
    lines = _ingredients_to_lines(current)
    print(f"\n{field_name}:")
    if lines:
        for index, line in enumerate(lines, start=1):
            print(f"  {index}. {line}")
    else:
        print("  (empty)")

    print("  Enter = keep, e = replace list, a = append lines, 0 = skip recipe")
    choice = prompt_fn("  Choice: ").strip().lower()

    if choice in ("", "k", "keep"):
        return ingredients_to_text(lines)
    if choice == "0":
        return None
    if choice == "e":
        return _read_multiline_ingredients(prompt_fn, "replace")
    if choice == "a":
        appended = _read_multiline_ingredients(prompt_fn, "append")
        combined = lines + _ingredients_to_lines(appended)
        return ingredients_to_text(combined)

    print("  Invalid choice, keeping current ingredients.")
    return ingredients_to_text(lines)


def _read_multiline_ingredients(prompt_fn: Callable[[str], str], mode: str) -> str:
    print(f"  Paste ingredients to {mode} (one per line, empty line to finish):")
    lines: list[str] = []
    while True:
        line = prompt_fn("")
        if not line.strip():
            break
        lines.append(line.strip())
    return ingredients_to_text(lines)


def _ingredients_to_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def _prompt_multi_select(
    field_name: str,
    options: list[str],
    current: list[str],
    prompt_fn: Callable[[str], str],
) -> list[str] | None:
    print(f"\n{field_name}: {', '.join(current) or '(empty)'}")
    if options:
        print("  Options:")
        for i, option in enumerate(options, start=1):
            marker = " *" if option in current else ""
            print(f"    {i}. {option}{marker}")
    print("  Enter comma-separated numbers or names (Enter to keep, 0 to clear):")

    while True:
        choice = prompt_fn("  Choice: ").strip()
        if not choice:
            return current
        if choice == "0":
            return []
        if choice.isdigit() and int(choice) == 0:
            return []

        picked: list[str] = []
        for part in choice.split(","):
            part = part.strip()
            if not part:
                continue
            if part.isdigit():
                index = int(part)
                if 1 <= index <= len(options):
                    picked.append(options[index - 1])
                    continue
            if part in options:
                picked.append(part)
                continue
            print("  Invalid choice, try again.")
            picked = []
            break

        if picked:
            return list(dict.fromkeys(picked))


def _prompt_checkbox(
    field_name: str,
    current: Any,
    prompt_fn: Callable[[str], str],
) -> bool | None:
    current_label = "yes" if current else "no" if current is False else "(unset)"
    print(f"\n{field_name}: {current_label}")

    while True:
        choice = prompt_fn("  Set to yes/no? (y/n, Enter to keep): ").strip().lower()
        if not choice:
            return bool(current) if current is not None else False
        if choice in ("y", "yes"):
            return True
        if choice in ("n", "no"):
            return False
        print("  Enter y, n, or Enter to keep.")


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _default_prompt(message: str) -> str:
    return input(message)


def _default_select_option(field_name: str, options: list[str], current: str | None) -> str | None:
    print(f"\n{field_name}: {_format_value(current) or '(empty)'}")
    print("  Options:")
    for i, option in enumerate(options, start=1):
        label = option if option else "(blank)"
        marker = " *" if option and option == current else ""
        if not option and not current:
            marker = " *"
        print(f"    {i}. {label}{marker}")
    print("  0. Skip this recipe")

    while True:
        choice = input("  Choice: ").strip()
        if choice == "0":
            return None
        if not choice and current is not None:
            return current
        if not choice:
            return ""
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(options):
                return options[index - 1]
        if choice in options:
            return choice
        print("  Invalid choice, try again.")


def read_urls_from_stdin() -> list[str]:
    print("Paste recipe URL(s), one per line. Empty line to finish:")
    urls: list[str] = []
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            break
        urls.append(line)
    return urls
