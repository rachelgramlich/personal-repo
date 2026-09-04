"""Grocery Wizard CLI — production workflow and dev maintenance commands."""

from __future__ import annotations

import argparse
import sys

from src.grocery_wizard.config import load_config
from src.grocery_wizard.integrations.notion import NotionRecipesDB
from src.grocery_wizard.lib.feedback import PROD_COMMANDS, prompt_for_feedback

_DEPRECATED_COMMANDS: dict[str, str] = {
    "add": "Use `add-recipe` instead.",
    "plan": "Use `plan-recipes` instead.",
    "grocery": "Use `create-grocery-list` instead.",
    "pantry": "Use `edit-pantry` instead.",
    "sync": "Use `dev backfill-ingredients` or `dev reconcile-ingredients`.",
    "refresh-ingredients": "Use `dev refresh-all-ingredients` instead.",
    "audit": "Use `dev audit-recipes` instead.",
    "schema": "Use `dev show-schema` instead.",
}

_DEPRECATED_DEV_COMMANDS: dict[str, str] = {
    "backfill": "Use `dev backfill-ingredients` instead.",
    "reconcile": "Use `dev reconcile-ingredients` instead.",
    "refresh-all": "Use `dev refresh-all-ingredients` instead.",
    "audit": "Use `dev audit-recipes` instead.",
    "schema": "Use `dev show-schema` instead.",
}


def _print_deprecated(name: str, message: str) -> None:
    print(f"Command '{name}' was removed.", file=sys.stderr)
    print(message, file=sys.stderr)
    print(
        "Run: uv run python -m src.grocery_wizard.cli --help",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] in _DEPRECATED_COMMANDS:
        _print_deprecated(argv[0], _DEPRECATED_COMMANDS[argv[0]])
        return 1

    if len(argv) >= 2 and argv[0] == "dev" and argv[1] in _DEPRECATED_DEV_COMMANDS:
        _print_deprecated(f"dev {argv[1]}", _DEPRECATED_DEV_COMMANDS[argv[1]])
        return 1

    parser = argparse.ArgumentParser(
        prog="grocery-wizard",
        description="Plan meals from Notion recipes and build grocery lists.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser(
        "add-recipe",
        help="Save a new recipe from a URL into Notion",
    )
    add_parser.add_argument(
        "urls",
        nargs="*",
        help="Recipe page URLs to save (or paste URLs when prompted)",
    )
    add_parser.set_defaults(func=cmd_add)

    plan_parser = subparsers.add_parser(
        "plan-recipes",
        help="Pick dinners for the week (saves week_plan.json)",
    )
    plan_parser.add_argument(
        "--meals",
        type=int,
        default=None,
        help="How many dinners to plan (default: from your config, usually 7)",
    )
    plan_parser.set_defaults(func=cmd_plan)

    grocery_parser = subparsers.add_parser(
        "create-grocery-list",
        help="Build your shopping list from this week's plan",
    )
    grocery_parser.add_argument(
        "--recipes",
        help="Use these recipe names instead of the saved week plan",
    )
    grocery_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output: hide excluded staples and skip the re-add prompt",
    )
    grocery_parser.add_argument(
        "--backfill-missing",
        action="store_true",
        help=("Scrape Notion recipes that have a link but no ingredients, then build the list"),
    )
    grocery_parser.add_argument(
        "--include-staples",
        action="store_true",
        help="Don't exclude pantry staples (salt, oil, etc.) from the list",
    )
    grocery_parser.add_argument(
        "--no-recurring-weekly-items",
        action="store_true",
        help="Omit recurring weekly items (berries, milk, etc.) from the list",
    )
    grocery_parser.set_defaults(func=cmd_grocery)

    pantry_parser = subparsers.add_parser(
        "edit-pantry",
        help="Edit what's always in your kitchen (won't appear on shopping list)",
    )
    pantry_parser.set_defaults(func=cmd_pantry)

    dev_parser = subparsers.add_parser(
        "dev",
        help="Database maintenance and debugging commands",
    )
    dev_subparsers = dev_parser.add_subparsers(dest="dev_command", required=True)

    backfill_parser = dev_subparsers.add_parser(
        "backfill-ingredients",
        help="Fill in missing ingredient lists from recipe links",
    )
    backfill_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which recipes would be updated without writing to Notion",
    )
    backfill_parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape recipes with empty ingredients (does not overwrite filled rows)",
    )
    backfill_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show each scraped ingredient line as it is saved",
    )
    backfill_parser.set_defaults(func=cmd_dev_backfill)

    reconcile_parser = dev_subparsers.add_parser(
        "reconcile-ingredients",
        help="Update ingredients where you already have some (keeps your edits)",
    )
    reconcile_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which recipes would be merged without writing to Notion",
    )
    reconcile_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show each scraped ingredient line during merge",
    )
    reconcile_parser.set_defaults(func=cmd_dev_reconcile)

    refresh_parser = dev_subparsers.add_parser(
        "refresh-all-ingredients",
        help="Re-download ingredients for every recipe",
    )
    refresh_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to Notion",
    )
    refresh_parser.add_argument(
        "--split-only",
        action="store_true",
        help="Re-split existing ingredient text without re-scraping links",
    )
    refresh_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show ingredient lines for each recipe",
    )
    refresh_parser.set_defaults(func=cmd_dev_refresh_all)

    reformat_parser = dev_subparsers.add_parser(
        "reformat-ingredients",
        help="Clean up stored ingredient text (split compounds, drop junk)",
    )
    reformat_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to Notion",
    )
    reformat_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show ingredient lines for each recipe",
    )
    reformat_parser.set_defaults(func=cmd_dev_reformat)

    audit_parser = dev_subparsers.add_parser(
        "audit-recipes",
        help="Show which recipes need attention",
    )
    audit_parser.set_defaults(func=cmd_dev_audit)

    schema_parser = dev_subparsers.add_parser(
        "show-schema",
        help="Show how Notion columns are detected",
    )
    schema_parser.set_defaults(func=cmd_dev_schema)

    list_feedback_parser = dev_subparsers.add_parser(
        "list-feedback",
        help="Show feedback collected from production commands",
    )
    list_feedback_parser.set_defaults(func=cmd_dev_list_feedback)

    validate_pipeline_parser = dev_subparsers.add_parser(
        "validate-pipeline",
        help="Run Notion → meal plan → grocery list validation report",
    )
    validate_pipeline_parser.add_argument(
        "--seeds",
        default="1,2,3",
        help="Comma-separated random seeds for suggest_meals (default: 1,2,3)",
    )
    validate_pipeline_parser.add_argument(
        "--meals",
        type=int,
        default=None,
        help="Meal count when no saved week plan exists (default: from config)",
    )
    validate_pipeline_parser.add_argument(
        "--output",
        default="tests/fixtures/pipeline_validation_report.txt",
        help="Where to write the report (default: tests/fixtures/pipeline_validation_report.txt)",
    )
    validate_pipeline_parser.add_argument(
        "--suggest-meals",
        action="store_true",
        help="Ignore saved week plan and use suggest_meals with --seeds",
    )
    validate_pipeline_parser.set_defaults(func=cmd_dev_validate_pipeline)

    nyt_parser = subparsers.add_parser(
        "nyt",
        help="NYT Cooking integration (saved recipes, sync to Notion)",
    )
    nyt_subparsers = nyt_parser.add_subparsers(dest="nyt_command", required=True)

    nyt_auth_status_parser = nyt_subparsers.add_parser(
        "auth-status",
        help="Check whether NYT Cooking credentials are configured (env vars)",
    )
    nyt_auth_status_parser.set_defaults(func=cmd_nyt_auth_status)

    nyt_saved_parser = nyt_subparsers.add_parser(
        "saved",
        help="List saved recipe box recipes",
    )
    nyt_saved_parser.add_argument(
        "--collection",
        help="Filter to a specific NYT recipe-box folder by name",
    )
    nyt_saved_parser.set_defaults(func=cmd_nyt_saved)

    nyt_sync_parser = nyt_subparsers.add_parser(
        "sync",
        help="Sync NYT saved recipes to Notion (skips duplicates)",
    )
    nyt_sync_parser.add_argument(
        "--collection",
        help="Sync only recipes from a specific NYT folder (skips interactive picker)",
    )
    nyt_sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview recipes that would be added without writing to Notion",
    )
    nyt_sync_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Review and confirm each recipe before creating (default: batch import)",
    )
    nyt_sync_parser.set_defaults(func=cmd_nyt_sync)

    nyt_review_parser = nyt_subparsers.add_parser(
        "review-metadata",
        help="Show metadata assigned during the last NYT sync",
    )
    nyt_review_parser.set_defaults(func=cmd_nyt_review_metadata)

    nyt_apply_parser = nyt_subparsers.add_parser(
        "apply-metadata",
        help="Apply metadata corrections from a JSON file",
    )
    nyt_apply_parser.add_argument(
        "corrections_file",
        help='JSON file: [{"page_id": "...", "fields": {"Meal": "Dessert"}}]',
    )
    nyt_apply_parser.set_defaults(func=cmd_nyt_apply_metadata)

    nyt_reclassify_parser = nyt_subparsers.add_parser(
        "reclassify",
        help="Re-run Meal and Weeknight Friendly for NYT-synced recipes",
    )
    nyt_reclassify_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to Notion",
    )
    nyt_reclassify_parser.set_defaults(func=cmd_nyt_reclassify)

    args = parser.parse_args(argv)
    exit_code = args.func(args)
    if exit_code == 0 and args.command in PROD_COMMANDS:
        prompt_for_feedback(args.command)
    return exit_code


def cmd_add(args: argparse.Namespace) -> int:
    from src.grocery_wizard.recipes.add_recipe import add_recipes_from_urls, read_urls_from_stdin

    config = load_config()
    db = NotionRecipesDB(config)

    urls = list(args.urls)
    if not urls:
        urls = read_urls_from_stdin()
    if not urls:
        print("No URLs provided.", file=sys.stderr)
        return 1

    created = add_recipes_from_urls(db, urls)
    print(f"\nCreated {len(created)} recipe(s).")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    from src.grocery_wizard.planning.meal_planner import run_meal_planner

    config = load_config()
    db = NotionRecipesDB(config)
    meals = args.meals or config.default_meals
    plan = run_meal_planner(db, meals=meals)
    return 0 if plan else 1


def cmd_grocery(args: argparse.Namespace) -> int:
    from src.grocery_wizard.shopping.grocery_list import run_grocery_list

    config = load_config()
    db = NotionRecipesDB(config)

    recipe_names: list[str] | None = None
    if args.recipes:
        recipe_names = [name.strip() for name in args.recipes.split(",") if name.strip()]

    return run_grocery_list(
        db,
        recipe_names=recipe_names,
        quiet=args.quiet,
        backfill_missing=args.backfill_missing,
        exclude_pantry=not args.include_staples,
        include_recurring_weekly_items=not args.no_recurring_weekly_items,
    )


def cmd_pantry(_args: argparse.Namespace) -> int:
    from src.grocery_wizard.shopping.pantry import run_pantry_interactive

    return run_pantry_interactive()


def cmd_dev_schema(_args: argparse.Namespace) -> int:
    config = load_config()
    db = NotionRecipesDB(config)
    schema = db.schema

    print(f"Database ID: {config.notion_database_id}")
    print(f"Name column: {schema.name_column}")
    print(f"Link column: {schema.link_column}")
    print(f"Ingredients column: {schema.ingredients_column or '(not detected)'}")
    print()

    print("All columns:")
    for name, col in sorted(schema.all_columns.items()):
        line = f"  {name} ({col.type})"
        if col.options:
            line += f" — options: {', '.join(col.options)}"
        print(line)

    print()
    print(f"Filter columns ({len(schema.filter_columns)}):")
    for col in schema.filter_columns:
        print(f"  {col.name} ({col.type})")
        if col.options:
            print(f"    options: {', '.join(col.options)}")

    recipes = db.query_recipes()
    print()
    print(f"Recipes in database: {len(recipes)}")
    return 0


def cmd_dev_backfill(args: argparse.Namespace) -> int:
    from src.grocery_wizard.ingredients.sync import (
        categorize_recipes,
        format_recipe_progress,
        format_sync_summary,
        run_sync,
    )

    config = load_config()
    db = NotionRecipesDB(config)

    categories = categorize_recipes(db.query_recipes())
    count = len(categories.empty)
    if args.dry_run:
        print(f"Would backfill {count} recipe(s) with empty Ingredients...")
    else:
        print(f"Backfilling {count} recipe(s) with empty Ingredients...")
        if count:
            print()

    def on_recipe_done(index: int, total: int, result) -> None:
        print(format_recipe_progress(index, total, result))
        if args.verbose and result.ingredient_lines:
            for line in result.ingredient_lines:
                print(f"    {line}")

    summary = run_sync(
        db,
        dry_run=args.dry_run,
        force=args.force,
        on_recipe_done=None if args.dry_run else on_recipe_done,
    )

    print()
    print(format_sync_summary(summary, dry_run=args.dry_run, merge=False, verbose=args.verbose))
    return 0


def cmd_dev_reconcile(args: argparse.Namespace) -> int:
    from src.grocery_wizard.ingredients.sync import (
        categorize_recipes,
        format_sync_summary,
        run_merge_sync,
    )

    config = load_config()
    db = NotionRecipesDB(config)

    if args.dry_run:
        categories = categorize_recipes(db.query_recipes())
        count = len(categories.populated)
        print(f"Would reconcile {count} populated recipe(s)...")
    else:
        print("Reconciling populated recipes one at a time...")

    summary = run_merge_sync(db, dry_run=args.dry_run)

    print()
    print(format_sync_summary(summary, dry_run=args.dry_run, merge=True, verbose=args.verbose))
    return 0


def cmd_dev_refresh_all(args: argparse.Namespace) -> int:
    from src.grocery_wizard.ingredients.sync import (
        format_refresh_progress,
        format_refresh_summary,
        run_refresh_ingredients,
    )

    config = load_config()
    db = NotionRecipesDB(config)
    recipes = db.query_recipes()
    total = len(recipes)

    if args.split_only:
        mode = "split-only"
    else:
        mode = "scrape + split"

    if args.dry_run:
        print(f"Dry run: refreshing {total} recipe(s) ({mode})...")
    else:
        print(f"Refreshing {total} recipe(s) ({mode})...")
        if total:
            print()

    def on_recipe_done(index: int, count: int, result) -> None:
        print(format_refresh_progress(index, count, result))
        if args.verbose and result.ingredient_lines:
            for line in result.ingredient_lines:
                print(f"    {line}")

    summary = run_refresh_ingredients(
        db,
        dry_run=args.dry_run,
        split_only=args.split_only,
        on_recipe_done=None if args.dry_run else on_recipe_done,
    )

    if args.dry_run:
        print()
        for index, result in enumerate(summary.results, start=1):
            if result.status in ("dry_run", "unchanged", "skipped", "failed"):
                print(format_refresh_progress(index, total, result))

    print()
    print(
        format_refresh_summary(
            summary,
            dry_run=args.dry_run,
            split_only=args.split_only,
        )
    )
    return 0


def cmd_dev_reformat(args: argparse.Namespace) -> int:
    """Re-run ingest cleanup on stored Notion ingredients without re-scraping."""
    args.split_only = True
    return cmd_dev_refresh_all(args)


def cmd_dev_audit(_args: argparse.Namespace) -> int:
    from src.grocery_wizard.dev.audit import audit_recipes, format_audit_report

    config = load_config()
    db = NotionRecipesDB(config)
    report = audit_recipes(db.query_recipes())
    print(format_audit_report(report))
    return 0


def cmd_dev_list_feedback(_args: argparse.Namespace) -> int:
    from src.grocery_wizard.lib.feedback import list_feedback

    print(list_feedback())
    return 0


def cmd_dev_validate_pipeline(args: argparse.Namespace) -> int:
    from pathlib import Path

    from src.grocery_wizard.dev.validate_pipeline import (
        format_pipeline_report,
        run_pipeline_validation,
    )

    config = load_config()
    db = NotionRecipesDB(config)

    seed_values: list[int | None]
    if args.seeds.strip().lower() in ("none", "saved"):
        seed_values = [None]
    else:
        seed_values = [int(part.strip()) for part in args.seeds.split(",") if part.strip()]

    output_path = Path(args.output)
    report = run_pipeline_validation(
        db,
        meals=args.meals,
        seeds=seed_values,
        use_saved_week_plan=not args.suggest_meals,
    )
    text = format_pipeline_report(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nReport saved to {output_path}")
    return 0


def cmd_nyt_auth_status(_args: argparse.Namespace) -> int:
    from src.grocery_wizard.integrations.nyt_cooking import (
        NytAuthError,
        NYTCookingClient,
        credentials_status,
    )

    status = credentials_status()
    if not status["configured"]:
        print("NYT Cooking credentials: not configured")
        print("Set NYT_S_COOKIE and NYT_REGI_ID (or NYT_USER_ID) in your environment.")
        print("See README for how to copy values from browser DevTools.")
        return 1

    print("NYT Cooking credentials: configured (environment)")
    print(f"regi_id: {status['regi_id']}")

    client = NYTCookingClient()
    try:
        client.verify_auth()
    except NytAuthError as exc:
        print(f"Verification failed: {exc}", file=sys.stderr)
        return 1

    print("Verification: OK")
    return 0


def cmd_nyt_saved(args: argparse.Namespace) -> int:
    from src.grocery_wizard.integrations.nyt_cooking import NytAuthError, NYTCookingClient

    client = NYTCookingClient()
    collection_id: str | None = None

    if args.collection:
        collection = client.find_collection_by_name(args.collection)
        if collection is None:
            print(
                f"Collection '{args.collection}' not found; listing full recipe box.",
                file=sys.stderr,
            )
        else:
            collection_id = collection.id
            print(f"Folder: {collection.name} ({collection.recipe_count} recipes)")

    try:
        recipes = list(client.iter_all_saved_recipes(collection_id=collection_id))
    except NytAuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not recipes:
        print("No saved recipes found.")
        return 0

    for index, recipe in enumerate(recipes, start=1):
        author = f" — {recipe.author}" if recipe.author else ""
        print(f"{index:4d}. {recipe.name}{author}")
        print(f"      {recipe.url}")
    print(f"\nTotal: {len(recipes)} recipe(s)")
    return 0


def cmd_nyt_sync(args: argparse.Namespace) -> int:
    from src.grocery_wizard.integrations.nyt_cooking import (
        NytAuthError,
        NYTCookingClient,
        NytSyncCancelledError,
        format_metadata_review,
        prompt_collection_choice,
        save_sync_report,
        sync_saved_recipes_to_notion,
    )

    config = load_config()
    db = NotionRecipesDB(config)
    client = NYTCookingClient()

    if args.dry_run:
        print("Dry run — no recipes will be written to Notion.\n")

    collection_id: str | None = None
    collection_label: str | None = None

    try:
        if args.collection:
            pass
        else:
            collection_id, collection_label = prompt_collection_choice(client, on_info=print)
            print()
    except NytAuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except NytSyncCancelledError as exc:
        print(str(exc))
        return 0

    try:
        summary = sync_saved_recipes_to_notion(
            db,
            client,
            collection_name=args.collection,
            collection_id=collection_id,
            collection_label=collection_label,
            dry_run=args.dry_run,
            no_confirm=not args.confirm,
            on_progress=print,
        )
    except NytAuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not args.dry_run and summary.created_recipes:
        save_sync_report(summary)

    print()
    print(
        f"Sync complete: {summary.total} in NYT, "
        f"{summary.skipped_existing} already in Notion, "
        f"{summary.created} created, "
        f"{summary.dry_run} would add, "
        f"{summary.failed} failed."
    )

    if summary.created_recipes:
        print()
        report = {
            "synced_at": "",
            "collection": summary.collection_label,
            "created": [
                {
                    "page_id": r.page_id,
                    "name": r.name,
                    "url": r.url,
                    "metadata": r.metadata,
                    "flags": r.flags,
                }
                for r in summary.created_recipes
            ],
        }
        print(format_metadata_review(report))
        if not args.dry_run and summary.created:
            print("Ask your agent to review flagged recipes, or run: nyt review-metadata")
    return 0


def cmd_nyt_review_metadata(_args: argparse.Namespace) -> int:
    from src.grocery_wizard.integrations.nyt_cooking import (
        format_metadata_review,
        load_sync_report,
    )

    report = load_sync_report()
    if report is None:
        print("No NYT sync report found. Run `nyt sync` first.")
        return 1
    print(format_metadata_review(report))
    return 0


def cmd_nyt_apply_metadata(args: argparse.Namespace) -> int:
    import json
    from pathlib import Path

    from src.grocery_wizard.integrations.nyt_cooking import apply_metadata_corrections

    path = Path(args.corrections_file)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    corrections = json.loads(path.read_text())
    if not isinstance(corrections, list):
        print("Corrections file must be a JSON array.", file=sys.stderr)
        return 1

    config = load_config()
    db = NotionRecipesDB(config)
    updated = apply_metadata_corrections(db, corrections)
    print(f"Updated {updated} recipe(s).")
    return 0


def cmd_nyt_reclassify(args: argparse.Namespace) -> int:
    from src.grocery_wizard.integrations.nyt_cooking import (
        NYTCookingClient,
        format_reclassify_summary,
        reclassify_nyt_synced_recipes,
    )

    config = load_config()
    db = NotionRecipesDB(config)
    client = NYTCookingClient()

    if args.dry_run:
        print("Dry run — no recipes will be written to Notion.\n")

    summary = reclassify_nyt_synced_recipes(
        db,
        client,
        dry_run=args.dry_run,
        on_progress=print,
    )
    print()
    print(format_reclassify_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
