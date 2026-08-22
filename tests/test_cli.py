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
