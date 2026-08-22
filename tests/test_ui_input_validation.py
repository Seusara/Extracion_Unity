from pathlib import Path

import pytest

from unity_translator.ui import _required_path


def test_required_path_rejects_empty_or_current_directory() -> None:
    with pytest.raises(ValueError, match="Juego"):
        _required_path("", "Juego")
    with pytest.raises(ValueError, match="Proyecto"):
        _required_path(".", "Proyecto")


def test_required_path_returns_explicit_path(tmp_path: Path) -> None:
    selected = tmp_path / "game"
    assert _required_path(str(selected), "Juego") == str(selected)
