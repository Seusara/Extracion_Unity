import json
from pathlib import Path

from unity_translator.analyzer import analyze_game, find_data_dir
from unity_translator.cli import main


def test_strong_csv_candidate_is_automatic_with_evidence(tmp_path: Path) -> None:
    game = tmp_path / "Game"
    streaming = game / "Game_Data" / "StreamingAssets"
    streaming.mkdir(parents=True)
    (streaming / "dialogue.csv").write_text("id,text\n1,Hello\n", encoding="utf-8")

    result = analyze_game(game)

    assert result["compatibility_level"] == "automatic"
    candidate = result["candidates"][0]
    assert candidate["adapter_id"] == "streamingassets-csv"
    assert candidate["confidence"] >= 0.9
    assert any("StreamingAssets/dialogue.csv" in item for item in candidate["evidence"])
    assert "extract" in candidate["capabilities"]


def test_multiple_candidates_are_reported_without_collapsing(tmp_path: Path) -> None:
    game = tmp_path / "Game"
    streaming = game / "Game_Data" / "StreamingAssets"
    streaming.mkdir(parents=True)
    (streaming / "dialogue.csv").write_text("id,text\n1,Hello\n", encoding="utf-8")
    (streaming / "other.json").write_text(json.dumps({"text": "Hello"}), encoding="utf-8")
    (streaming / "aa").mkdir()
    (streaming / "aa" / "catalog.json").write_text("{}", encoding="utf-8")
    (streaming / "aa" / "group.bundle").write_bytes(b"bundle")

    result = analyze_game(game)
    adapters = {candidate["adapter_id"] for candidate in result["candidates"]}

    assert "streamingassets-csv" in adapters
    assert "unity-addressables-textasset" in adapters
    assert result["compatibility_level"] == "assisted"


def test_unknown_game_is_investigation(tmp_path: Path) -> None:
    game = tmp_path / "Game"
    (game / "Game_Data").mkdir(parents=True)

    result = analyze_game(game)

    assert result["compatibility_level"] == "investigation"
    assert result["candidates"] == []


def test_csv_outside_streamingassets_is_not_a_streaming_candidate(tmp_path: Path) -> None:
    game = tmp_path / "Game"
    (game / "Game_Data" / "Resources").mkdir(parents=True)
    (game / "Game_Data" / "Resources" / "dialogue.csv").write_text("Hello", encoding="utf-8")

    result = analyze_game(game)

    assert "streamingassets-csv" not in {candidate["adapter_id"] for candidate in result["candidates"]}


def test_registered_adapter_with_insufficient_evidence_is_not_suggested(tmp_path: Path) -> None:
    game = tmp_path / "Game"
    (game / "Game_Data" / "StreamingAssets").mkdir(parents=True)

    result = analyze_game(game)

    assert all(candidate["confidence"] >= 0.5 for candidate in result["candidates"])
    assert result["compatibility_level"] == "investigation"


def test_nested_reasonable_game_root_is_discovered(tmp_path: Path) -> None:
    selected = tmp_path / "SelectedFolder"
    game = selected / "Subfolder"
    (game / "Game_Data" / "StreamingAssets").mkdir(parents=True)
    (game / "Game.exe").write_bytes(b"MZ")

    result = analyze_game(selected, sanitize_paths=False)

    assert result["is_unity"] is True
    assert Path(result["data_dir"]) == game / "Game_Data"
    assert find_data_dir(selected) == game / "Game_Data"


def test_multiple_data_directories_require_selection(tmp_path: Path) -> None:
    selected = tmp_path / "SelectedFolder"
    for name in ("One_Data", "Two_Data"):
        (selected / name).mkdir(parents=True)

    result = analyze_game(selected)

    assert result["is_unity"] is False
    assert result["compatibility_level"] == "investigation"
    assert len(result["game_candidates"]) == 2


def test_candidate_evidence_uses_relative_sanitized_paths(tmp_path: Path) -> None:
    game = tmp_path / "Private" / "Game"
    streaming = game / "Game_Data" / "StreamingAssets"
    streaming.mkdir(parents=True)
    (streaming / "dialogue.csv").write_text("id,text\n1,Hello\n", encoding="utf-8")

    result = analyze_game(game)
    serialized = json.dumps(result, ensure_ascii=False)

    assert "Private" not in serialized
    assert "<GameRoot>/Game_Data/StreamingAssets/dialogue.csv" in serialized


def test_cli_analyze_prints_candidate_evidence(tmp_path: Path, capsys) -> None:
    game = tmp_path / "Game"
    streaming = game / "Game_Data" / "StreamingAssets"
    streaming.mkdir(parents=True)
    (streaming / "dialogue.csv").write_text("id,text\n1,Hello\n", encoding="utf-8")

    assert main(["analyze", str(game)]) == 0
    output = capsys.readouterr().out

    assert "Compatibility: AUTOMATIC" in output
    assert "streamingassets-csv" in output
    assert "Evidence:" in output
