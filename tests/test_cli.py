import json
from pathlib import Path

from unity_translator.cli import main


def test_cli_analyze_prints_machine_readable_report(tmp_path: Path, capsys) -> None:
    game = tmp_path / "Game"
    (game / "Game_Data" / "StreamingAssets").mkdir(parents=True)

    exit_code = main(["analyze", str(game), "--json"])

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["is_unity"] is True
    assert report["streaming_assets"] is True


def test_cli_init_auto_detects_naninovel_profile_without_a_profile_file(tmp_path: Path, capsys) -> None:
    game = tmp_path / "Game"
    managed = game / "Game_Data" / "Managed"
    managed.mkdir(parents=True)
    (managed / "Elringus.Naninovel.Runtime.dll").write_bytes(b"")
    (managed / "Naninovel.Common.dll").write_bytes(b"")
    project = tmp_path / "project"

    exit_code = main(["init", str(game), str(project), "--auto"])

    assert exit_code == 0
    manifest = json.loads((project / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["profile"] == {"extractor": "naninovel-addressables"}


def test_cli_init_auto_reports_clear_error_when_nothing_detected(tmp_path: Path, capsys) -> None:
    game = tmp_path / "Game"
    (game / "Game_Data" / "StreamingAssets").mkdir(parents=True)
    project = tmp_path / "project"

    exit_code = main(["init", str(game), str(project), "--auto"])

    assert exit_code == 2
    assert "profile" in capsys.readouterr().err.lower()
