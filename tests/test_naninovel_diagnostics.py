from collections import Counter
from pathlib import Path

import pytest

from unity_translator import pipeline
from unity_translator.storage import read_json


def _manifest(game: Path) -> dict:
    return {"game_path": str(game)}


def test_naninovel_extract_reports_unparsed_types(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    game = tmp_path / "Game"
    game.mkdir()
    project = tmp_path / "project"
    project.mkdir()

    class FakeParser:
        def __init__(self, _game: Path) -> None:
            self.unparsed_types = Counter({"Naninovel.Commands.UnknownCommand": 2})
            self.failed_assemblies = ["Broken"]

        def extract(self) -> list[dict]:
            return []

    monkeypatch.setattr(pipeline, "NaninovelParser", FakeParser)

    pipeline._extract_naninovel(project, _manifest(game))

    report = read_json(project / "logs" / "naninovel-unparsed-types.json")
    assert report == {
        "unparsed_types": {"Naninovel.Commands.UnknownCommand": 2},
        "failed_assemblies": ["Broken"],
    }


def test_naninovel_extract_does_not_write_report_when_everything_parsed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = tmp_path / "Game"
    game.mkdir()
    project = tmp_path / "project"
    project.mkdir()

    class FakeParser:
        def __init__(self, _game: Path) -> None:
            self.unparsed_types = Counter()
            self.failed_assemblies: list[str] = []

        def extract(self) -> list[dict]:
            return []

    monkeypatch.setattr(pipeline, "NaninovelParser", FakeParser)

    pipeline._extract_naninovel(project, _manifest(game))

    assert not (project / "logs" / "naninovel-unparsed-types.json").exists()


def test_naninovel_extract_reports_failed_assemblies_even_without_unparsed_types(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = tmp_path / "Game"
    game.mkdir()
    project = tmp_path / "project"
    project.mkdir()

    class FakeParser:
        def __init__(self, _game: Path) -> None:
            self.unparsed_types = Counter()
            self.failed_assemblies = ["Broken"]

        def extract(self) -> list[dict]:
            return []

    monkeypatch.setattr(pipeline, "NaninovelParser", FakeParser)

    pipeline._extract_naninovel(project, _manifest(game))

    report = read_json(project / "logs" / "naninovel-unparsed-types.json")
    assert report == {"unparsed_types": {}, "failed_assemblies": ["Broken"]}


def test_naninovel_extract_report_survives_undecodable_type_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A misaligned recovery scan can read raw garbage as a "class name": UnityPy
    decodes it with errors="surrogateescape", producing an unpaired surrogate
    that plain json.dump cannot write as UTF-8. The report must not crash."""
    game = tmp_path / "Game"
    game.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    garbage_name = "Naninovel.Commands.Bad\udce0Name"

    class FakeParser:
        def __init__(self, _game: Path) -> None:
            self.unparsed_types = Counter({garbage_name: 1})
            self.failed_assemblies: list[str] = []

        def extract(self) -> list[dict]:
            return []

    monkeypatch.setattr(pipeline, "NaninovelParser", FakeParser)

    pipeline._extract_naninovel(project, _manifest(game))

    report = read_json(project / "logs" / "naninovel-unparsed-types.json")
    assert list(report["unparsed_types"].values()) == [1]
    assert garbage_name not in report["unparsed_types"]
