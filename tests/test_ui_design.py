from unity_translator.ui import DESIGN_COLORS


def test_design_palette_is_dark_accessible_and_has_semantic_states() -> None:
    assert DESIGN_COLORS["background"] == "#0F1115"
    assert DESIGN_COLORS["panel"] == "#171A21"
    assert DESIGN_COLORS["accent"] == "#38BDF8"
    assert DESIGN_COLORS["success"] == "#22C55E"
    assert DESIGN_COLORS["warning"] == "#F59E0B"
    assert DESIGN_COLORS["error"] == "#EF4444"
