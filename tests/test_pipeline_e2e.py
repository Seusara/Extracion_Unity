import csv
import json
from pathlib import Path

from unity_translator.pipeline import (
    analyze,
    create_project,
    export_csv,
    extract,
    import_csv,
    inject,
    validate,
)


def test_streamingassets_csv_translation_end_to_end(tmp_path: Path) -> None:
    game = tmp_path / "SampleGame"
    data = game / "SampleGame_Data"
    streaming = data / "StreamingAssets"
    streaming.mkdir(parents=True)
    (data / "Managed").mkdir()
    source = streaming / "dialogue.csv"
    source.write_text("key,text,command\nstart,Start Game,show\nquit,Quit,close\n", encoding="utf-8-sig")

    analysis = analyze(game)
    assert analysis["is_unity"] is True
    assert analysis["runtime"] == "mono"
    assert analysis["streaming_assets"] is True

    project = tmp_path / "translation-project"
    profile = {
        "extractor": "streamingassets-csv",
        "files": [{"glob": "dialogue.csv", "columns": [1], "header": True}],
    }
    create_project(game, project, profile)
    entries = extract(project)
    assert [entry["original_text"] for entry in entries] == ["Start Game", "Quit"]

    translator_csv = tmp_path / "es-MX.csv"
    export_csv(project, translator_csv)
    with translator_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["translation"] = "Iniciar juego"
    with translator_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    result = import_csv(project, translator_csv)
    assert result == {"imported": 1, "pending": 1, "intentionally_empty": 0}
    report = validate(project)
    assert report["errors"] == 0

    build = inject(project)
    patched = build / "SampleGame_Data" / "StreamingAssets" / "dialogue.csv"
    with patched.open("r", encoding="utf-8-sig", newline="") as handle:
        patched_rows = list(csv.reader(handle))
    assert patched_rows == [
        ["key", "text", "command"],
        ["start", "Iniciar juego", "show"],
        ["quit", "Quit", "close"],
    ]
    assert source.read_text(encoding="utf-8-sig") == "key,text,command\nstart,Start Game,show\nquit,Quit,close\n"

    ir = json.loads((project / "translation.json").read_text(encoding="utf-8"))
    assert ir["entries"][0]["status"] == "translated"
    assert (project / "backups").is_dir()
