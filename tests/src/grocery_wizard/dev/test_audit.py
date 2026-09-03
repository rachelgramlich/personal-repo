from src.grocery_wizard.dev.audit import (
    audit_recipes,
    looks_suspicious_ingredients,
    split_ingredient_lines,
)
from src.grocery_wizard.integrations.notion import Recipe


def test_split_ingredient_lines_handles_br_tags() -> None:
    lines = split_ingredient_lines("2<br>tablespoons<br>cocoa powder")
    assert lines == ["2", "tablespoons", "cocoa powder"]


def test_looks_suspicious_detects_fragmented_lines() -> None:
    text = "\n".join(["2", "tablespoons", "cocoa powder", "1", "cup", "sugar"])
    assert looks_suspicious_ingredients(text)


def test_looks_suspicious_accepts_normal_lines() -> None:
    text = "2 tablespoons cocoa powder\n1 cup sugar"
    assert not looks_suspicious_ingredients(text)


def test_audit_recipes_categorizes() -> None:
    recipes = [
        Recipe("1", "Empty linked", "https://example.com", None, {}),
        Recipe("2", "No link", None, "1 cup flour", {}),
        Recipe(
            "3", "Broken", "https://example.com", "2\ntablespoons\ncocoa\npowder\n1\ncup\nsugar", {}
        ),
        Recipe("4", "OK", "https://example.com", "2 tablespoons cocoa powder", {}),
    ]
    report = audit_recipes(recipes)

    assert report.empty == ["Empty linked"]
    assert report.no_link == ["No link"]
    assert report.suspicious == ["Broken"]
    assert report.ok == ["OK"]
