import csv
from pathlib import Path

import pytest

from unity_translator.pipeline import create_project, export_csv, extract, import_csv


def _csv_project(tmp_path: Path) -> tuple[Path, Path, list[dict]]:
    game = tmp_path / "Game"
    streaming = game / "Game_Data" / "StreamingAssets"
    streaming.mkdir(parents=True)
    (streaming / "text.csv").write_text("key,text\na,Alpha\nb,Beta\n", encoding="utf-8-sig")
    project = tmp_path / "project"
    create_project(game, project, {
        "extractor": "streamingassets-csv",
        "files": [{"glob": "text.csv", "columns": [1], "header": True}],
    })
    extract(project)
    target = tmp_path / "translation.csv"
    export_csv(project, target)
    with target.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return project, target, rows


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "original", "translation", "intentionally_empty"])
        writer.writeheader()
        writer.writerows(rows)


def test_import_rejects_duplicate_ids(tmp_path: Path) -> None:
    project, target, rows = _csv_project(tmp_path)
    _write(target, [rows[0], rows[0], rows[1]])
    with pytest.raises(ValueError, match="Duplicate CSV ID"):
        import_csv(project, target)


def test_import_rejects_missing_ids(tmp_path: Path) -> None:
    project, target, rows = _csv_project(tmp_path)
    _write(target, rows[:1])
    with pytest.raises(ValueError, match="Missing CSV IDs"):
        import_csv(project, target)


def test_import_rejects_unknown_ids(tmp_path: Path) -> None:
    project, target, rows = _csv_project(tmp_path)
    rows[0]["id"] = "unknown"
    _write(target, rows)
    with pytest.raises(ValueError, match="Unknown CSV ID"):
        import_csv(project, target)


def test_import_rejects_modified_original(tmp_path: Path) -> None:
    project, target, rows = _csv_project(tmp_path)
    rows[0]["original"] = "Changed"
    _write(target, rows)
    with pytest.raises(ValueError, match="Original text changed"):
        import_csv(project, target)


def test_import_rejects_invalid_utf8(tmp_path: Path) -> None:
    project, target, _ = _csv_project(tmp_path)
    target.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(UnicodeDecodeError):
        import_csv(project, target)
