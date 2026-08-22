from pathlib import Path

import pytest

from unity_translator.pipeline import _resolve_asset_file


def test_resolves_asset_file_inside_il2cpp_data_when_profile_uses_basename(tmp_path: Path) -> None:
    data_dir = tmp_path / "HolyKnightRicca_Data"
    expected = data_dir / "il2cpp_data" / "sharedassets0.assets"
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b"asset")

    assert _resolve_asset_file(data_dir, "sharedassets0.assets") == expected


def test_asset_resolution_reports_ambiguous_basename(tmp_path: Path) -> None:
    data_dir = tmp_path / "Game_Data"
    for folder in ("il2cpp_data", "nested"):
        asset = data_dir / folder / "sharedassets0.assets"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"asset")

    with pytest.raises(FileNotFoundError, match="multiple Unity asset files"):
        _resolve_asset_file(data_dir, "sharedassets0.assets")
