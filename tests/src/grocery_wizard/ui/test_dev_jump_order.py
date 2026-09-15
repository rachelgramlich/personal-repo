"""Dev jump wizard flow order."""

from src.grocery_wizard.ui.dev_jumps import (
    DEV_JUMP_FLOW_ORDER,
    DevJumpTarget,
    dev_jump_display_title,
)


def test_dev_jump_flow_matches_wizard_order() -> None:
    assert DEV_JUMP_FLOW_ORDER == (
        DevJumpTarget.MEALS_FILLED,
        DevJumpTarget.PRE_BUILD_GROCERY,
        DevJumpTarget.PER_RECIPE_REVIEW,
        DevJumpTarget.GROCERY_RESULT,
    )


def test_dev_jump_display_titles() -> None:
    assert dev_jump_display_title(DevJumpTarget.MEALS_FILLED) == "Meals filled"
    assert dev_jump_display_title(DevJumpTarget.PRE_BUILD_GROCERY) == "Pre-build grocery"
    assert dev_jump_display_title(DevJumpTarget.PER_RECIPE_REVIEW) == "Per-recipe review"
    assert dev_jump_display_title(DevJumpTarget.GROCERY_RESULT) == "Final list"
