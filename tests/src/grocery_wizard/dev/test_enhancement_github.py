from src.grocery_wizard.dev.enhancement_github import format_issue_body, parse_issue_body


def test_format_and_parse_issue_body_roundtrip() -> None:
    body = format_issue_body(
        enh_id="enh_003",
        area="shopping",
        description="First paragraph.\n\nSecond paragraph.",
        pr_url="https://github.com/o/r/pull/9",
        completed_at="2026-01-01T00:00:00+00:00",
    )
    parsed = parse_issue_body(body)
    assert parsed["id"] == "enh_003"
    assert parsed["area_from_body"] == "shopping"
    assert parsed["pr_url"] == "https://github.com/o/r/pull/9"
    assert "First paragraph." in parsed["description"]
    assert "Second paragraph." in parsed["description"]
