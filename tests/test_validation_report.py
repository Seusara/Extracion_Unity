import csv
import json
from pathlib import Path

from unity_translator.pipeline import auto_fix_validation, create_project, extract, validate


def _project(tmp_path: Path) -> Path:
    game = tmp_path / "Game"
    data = game / "Game_Data" / "StreamingAssets"
    data.mkdir(parents=True)
    (game / "Game.exe").write_bytes(b"fixture")
    (data / "dialogue.csv").write_text("id,text\nhello,Hello\n", encoding="utf-8")
    project = tmp_path / "project"
    create_project(
        game,
        project,
        {"extractor": "streamingassets-csv", "files": [{"glob": "dialogue.csv", "columns": [1], "header": True}]},
    )
    extract(project)
    return project


def test_validation_writes_detailed_json_and_csv_reports(tmp_path: Path) -> None:
    project = _project(tmp_path)
    report = validate(project)
    json_path = Path(report["report_json"])
    csv_path = Path(report["report_csv"])
    assert json_path.is_file()
    assert csv_path.is_file()
    document = json.loads(json_path.read_text(encoding="utf-8"))
    assert document["issues"] == []
    assert csv_path.read_text(encoding="utf-8-sig").startswith("severity,code,entry_id")


def test_auto_fix_resets_only_unchanged_translations(tmp_path: Path) -> None:
    project = _project(tmp_path)
    ir_path = project / "translation.json"
    document = json.loads(ir_path.read_text(encoding="utf-8"))
    document["entries"][0]["translated_text"] = "Hello"
    document["entries"][0]["status"] = "translated"
    ir_path.write_text(json.dumps(document), encoding="utf-8")
    report = auto_fix_validation(project)
    assert report["auto_fixed"] == 1
    updated = json.loads(ir_path.read_text(encoding="utf-8"))
    assert updated["entries"][0]["status"] == "untranslated"
    assert updated["entries"][0]["translated_text"] == ""
