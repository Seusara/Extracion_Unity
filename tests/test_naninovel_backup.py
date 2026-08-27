import json
from pathlib import Path

import pytest

from unity_translator import pipeline
from unity_translator.pipeline import inject
from unity_translator.storage import sha256_file, sha256_text, write_json_atomic


def _naninovel_manifest(game: Path) -> dict:
    data = game / "Game_Data"
    return {
        "game_path": str(game),
        "analysis": {"data_dir": str(data), "data_dir_name": data.name},
        "extractor": {"name": "naninovel-addressables", "version": 1},
        "profile": {"extractor": "naninovel-addressables"},
        "source_files": {},
    }


def _entry(source_file: str, bundle_hash: str) -> dict:
    return {
        "id": f"{source_file}:7:24:Text",
        "source_file": source_file,
        "asset_type": "NaninovelScript",
        "object_identifier": "TEST_DIALOGUE",
        "field": "Text",
        "original_text": "Original",
        "translated_text": "Translated",
        "original_hash": sha256_text("Original"),
        "status": "translated",
        "metadata": {
            "bundle": source_file,
            "asset": "TEST_DIALOGUE",
            "path_id": 7,
            "type": "Naninovel.Commands.PrintText",
            "field": "Text",
            "bundle_hash": bundle_hash,
            "entry_index": 24,
        },
    }


def test_naninovel_extract_snapshots_each_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    game = tmp_path / "Game"
    data = game / "Game_Data"
    bundle = data / "StreamingAssets" / "aa" / "StandaloneWindows64" / "naninovel" / "scripts" / "scene.bundle"
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"bundle bytes")
    project = tmp_path / "project"
    project.mkdir()
    relative = "Game_Data/StreamingAssets/aa/StandaloneWindows64/naninovel/scripts/scene.bundle"
    entry = _entry(relative, sha256_file(bundle))

    class FakeParser:
        def __init__(self, _game: Path) -> None:
            pass

        def extract(self) -> list[dict]:
            return [entry]

    monkeypatch.setattr(pipeline, "NaninovelParser", FakeParser)
    entries, source_files = pipeline._extract_naninovel(project, _naninovel_manifest(game))

    snapshot = project / "originals" / Path(relative)
    assert entries == [entry]
    assert source_files == {relative: sha256_file(bundle)}
    assert snapshot.is_file()
    assert snapshot.read_bytes() == bundle.read_bytes()
    assert sha256_file(snapshot) == sha256_file(bundle)


def test_naninovel_inject_backup_contains_original_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    game = tmp_path / "Game"
    data = game / "Game_Data"
    bundle = data / "StreamingAssets" / "aa" / "StandaloneWindows64" / "naninovel" / "scripts" / "scene.bundle"
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"bundle bytes")
    relative = "Game_Data/StreamingAssets/aa/StandaloneWindows64/naninovel/scripts/scene.bundle"
    project = tmp_path / "project"
    (project / "originals" / Path(relative).parent).mkdir(parents=True)
    snapshot = project / "originals" / Path(relative)
    snapshot.write_bytes(bundle.read_bytes())
    entry = _entry(relative, sha256_file(bundle))
    manifest = _naninovel_manifest(game)
    manifest["source_files"] = {relative: sha256_file(bundle)}
    write_json_atomic(project / "manifest.json", manifest)
    write_json_atomic(project / "translation.json", {"entries": [entry]})
    for directory in ("builds", "backups", "logs"):
        (project / directory).mkdir()

    class FakeAdapter:
        def inject(self, _path: Path, _entries: list[dict], _profile: dict) -> None:
            pass

    monkeypatch.setattr(pipeline, "get_adapter", lambda _adapter_id: FakeAdapter())
    monkeypatch.setattr(pipeline, "validate", lambda _project: {"errors": 0, "issues": [], "report_csv": ""})

    build = inject(project)
    backups = list((project / "backups").iterdir())
    assert len(backups) == 1
    backup_bundle = backups[0] / "originals" / Path(relative)
    assert build.is_dir()
    assert backup_bundle.is_file()
    assert sha256_file(backup_bundle) == sha256_file(bundle)
    assert bundle.read_bytes() == b"bundle bytes"
