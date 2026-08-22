from __future__ import annotations

import re
from pathlib import Path


def find_data_dir(game_path: Path) -> Path | None:
    candidates = sorted(path for path in game_path.glob("*_Data") if path.is_dir())
    return candidates[0] if len(candidates) == 1 else None


def analyze_game(game_path: Path) -> dict:
    game_path = game_path.resolve()
    data_dir = find_data_dir(game_path)
    if data_dir is None:
        return {
            "game_path": str(game_path),
            "is_unity": False,
            "runtime": "unknown",
            "unity_version": "unknown",
            "compatibility": "unknown",
            "reason": "Expected exactly one *_Data directory",
        }

    managed = data_dir / "Managed"
    il2cpp = data_dir / "il2cpp_data"
    game_assembly = game_path / "GameAssembly.dll"
    if il2cpp.is_dir() or game_assembly.is_file():
        runtime = "il2cpp"
    elif managed.is_dir():
        runtime = "mono"
    else:
        runtime = "unknown"

    files = [path for path in data_dir.rglob("*") if path.is_file()]
    names = [path.name.lower() for path in files]
    streaming = data_dir / "StreamingAssets"
    addressables = streaming / "aa"
    assets = sorted(
        str(path.relative_to(data_dir))
        for path in files
        if path.suffix.lower() in {".assets", ".bundle"}
        or path.name.lower().startswith("sharedassets")
        or path.name.lower() in {"resources.assets", "globalgamemanagers"}
    )
    searchable = "\n".join(names)
    return {
        "game_path": str(game_path),
        "data_dir": str(data_dir),
        "data_dir_name": data_dir.name,
        "is_unity": True,
        "runtime": runtime,
        "unity_version": "unknown",
        "managed": managed.is_dir(),
        "streaming_assets": streaming.is_dir(),
        "resources": (data_dir / "Resources").is_dir(),
        "addressables": addressables.is_dir(),
        "asset_files": assets,
        "localization_references": bool(re.search(r"localization|stringtable", searchable)),
        "textmeshpro_references": bool(re.search(r"textmesh|tmp_", searchable)),
        "compatibility": "experimental" if streaming.is_dir() else "detected_unsupported",
    }
