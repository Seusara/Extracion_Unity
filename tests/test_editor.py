import json
from pathlib import Path

from unity_translator.pipeline import create_project, extract, list_entries, update_translation


PROFILE = {
    "extractor": "streamingassets-csv",
    "files": [
        {
            "glob": "dialogue.csv",
            "columns": [1],
            "header": True,
            "encoding": "utf-8-sig",
            "delimiter": ",",
        }
    ],
}


def test_update_translation_persists_editor_change(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "SampleGame"
    project = tmp_path / "project"
    create_project(fixture, project, PROFILE)
    entry_id = extract(project)[0]["id"]

    updated = update_translation(project, entry_id, "Iniciar juego")

    saved = json.loads((project / "translation.json").read_text(encoding="utf-8"))
    assert updated["translated_text"] == "Iniciar juego"
    assert updated["status"] == "translated"
    assert saved["entries"][0]["translated_text"] == "Iniciar juego"


def test_update_translation_supports_intentionally_empty_text(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "SampleGame"
    project = tmp_path / "project"
    create_project(fixture, project, PROFILE)
    entry_id = extract(project)[0]["id"]

    updated = update_translation(project, entry_id, "", intentionally_empty=True)

    assert updated["status"] == "intentionally_empty"


def test_list_entries_returns_saved_ir_entries(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "SampleGame"
    project = tmp_path / "project"
    create_project(fixture, project, PROFILE)
    extracted = extract(project)

    assert list_entries(project) == extracted
