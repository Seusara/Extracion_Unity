import csv
import io
from pathlib import Path

from unity_translator.analyzer import detect_profile
from unity_translator.holyknight import _decrypt, _encrypt
from unity_translator.pipeline import create_project, extract, inject


def test_detect_profile_for_encrypted_holy_knight_layout(tmp_path: Path) -> None:
    game = tmp_path / "Game"
    data = game / "Game_Data"
    source = data / "StreamingAssets" / "Lang" / "en" / "system.dat"
    source.parent.mkdir(parents=True)
    source.write_bytes(_encrypt("title\tStart\n"))
    (data / "il2cpp_data").mkdir()
    profile = detect_profile(game)
    assert profile == {"extractor": "holyknight-encrypted-tsv", "source_root": "StreamingAssets/Lang/en"}


def test_holyknight_extract_and_inject_round_trip(tmp_path: Path) -> None:
    game = tmp_path / "Game"
    data = game / "Game_Data"
    source = data / "StreamingAssets" / "Lang" / "en" / "system.dat"
    source.parent.mkdir(parents=True)
    source.write_bytes(_encrypt("title\tStart\nmenu\tOptions\n"))
    (data / "il2cpp_data").mkdir()
    (game / "Game.exe").write_bytes(b"fixture")
    project = tmp_path / "project"
    profile = {"extractor": "holyknight-encrypted-tsv", "source_root": "StreamingAssets/Lang/en"}

    create_project(game, project, profile)
    entries = extract(project)
    assert [entry["original_text"] for entry in entries] == ["Start", "Options"]
    ir = (project / "translation.json").read_text(encoding="utf-8")
    assert "HolyKnightEncryptedTSV" in ir
    rows = list(csv.reader(io.StringIO(_decrypt(source), newline=""), delimiter="\t"))
    assert rows[0][1] == "Start"

    from unity_translator.storage import read_json, write_json_atomic
    document = read_json(project / "translation.json")
    document["entries"][0]["translated_text"] = "Comenzar"
    document["entries"][0]["status"] = "translated"
    write_json_atomic(project / "translation.json", document)
    build = inject(project)
    patched = build / "Game_Data" / "StreamingAssets" / "Lang" / "en" / "system.dat"
    assert list(csv.reader(io.StringIO(_decrypt(patched), newline=""), delimiter="\t"))[0][1] == "Comenzar"
    assert _decrypt(source).splitlines()[0] == "title\tStart"
