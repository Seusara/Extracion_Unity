import json
import zipfile
from pathlib import Path

from unity_translator.cli import main
from unity_translator.diagnostic_package import generate_diagnostic_package


def make_game(root: Path) -> Path:
    game = root / "Personal" / "Games" / "Unknown"
    data = game / "Unknown_Data"
    (data / "Managed").mkdir(parents=True)
    (data / "StreamingAssets" / "aa").mkdir(parents=True)
    (data / "StreamingAssets" / "aa" / "catalog.json").write_text("{}", encoding="utf-8")
    (data / "StreamingAssets" / "aa" / "group.bundle").write_bytes(b"bundle")
    (data / "resources.assets").write_bytes(b"serialized")
    (data / "Managed" / "Assembly-CSharp.dll").write_bytes(b"dll")
    (data / "Managed" / "Unity.TextMeshPro.dll").write_bytes(b"dll")
    (game / "Unknown.exe").write_bytes(b"MZ")
    (game / ".env").write_text("TOKEN=secret", encoding="utf-8")
    (game / "save" / "slot1.json").parent.mkdir()
    (game / "save" / "slot1.json").write_text("private save", encoding="utf-8")
    (game / "screen.png").write_bytes(b"image")
    return game


def test_generation_contains_sanitized_complete_context_and_no_originals(tmp_path: Path) -> None:
    game = make_game(tmp_path)
    package = generate_diagnostic_package(game, tmp_path / "out")

    assert package.zip_path.is_file()
    assert (package.directory / "README.md").is_file()
    assert json.loads((package.directory / "game_profile.json").read_text())["compatibility_level"] == "assisted"
    assert "<GameRoot>" in (package.directory / "problem.md").read_text()
    assert "Personal" not in (package.directory / "diagnostics.json").read_text()
    assert "Assembly-CSharp.dll" in (package.directory / "assemblies.json").read_text()
    assert "addressables" in (package.directory / "candidates.json").read_text().lower()
    assert "TOKEN" not in package.zip_path.read_bytes().decode("latin1", errors="ignore")
    assert "secret" not in package.zip_path.read_bytes().decode("latin1", errors="ignore")
    assert "Personal" not in (package.directory / "logs" / "analysis.log").read_text()


def test_zip_contains_only_generated_allowed_files(tmp_path: Path) -> None:
    package = generate_diagnostic_package(make_game(tmp_path), tmp_path / "out")
    with zipfile.ZipFile(package.zip_path) as archive:
        names = archive.namelist()
        assert names
        assert all(name.startswith("AI_CONTEXT/") for name in names)
        assert not any(name.endswith((".exe", ".dll", ".assets", ".bundle", ".env", ".png")) for name in names)
        assert "AI_CONTEXT/README.md" in names
        assert "AI_CONTEXT/logs/analysis.log" in names
        assert sorted(names) == names


def test_deep_and_large_tree_are_truncated(tmp_path: Path) -> None:
    game = make_game(tmp_path)
    data = game / "Unknown_Data"
    deep = data
    for index in range(12):
        deep /= f"deep{index}"
        deep.mkdir()
    for index in range(120):
        (data / f"file-{index}.txt").write_text("x", encoding="utf-8")
    package = generate_diagnostic_package(game, tmp_path / "out", max_depth=3, max_files=20)
    structure = (package.directory / "directory_structure.txt").read_text()
    assert "TRUNCATED" in structure
    diagnostics = json.loads((package.directory / "diagnostics.json").read_text())
    assert diagnostics["directory_structure"]["truncated"] is True


def test_manual_assisted_diagnosis_cli_creates_package(tmp_path: Path, capsys) -> None:
    game = make_game(tmp_path)
    output = tmp_path / "manual-package"
    assert main(["diagnose", str(game), "--output", str(output)]) == 0
    stdout = capsys.readouterr().out
    assert "Diagnostic package:" in stdout
    assert (output / "AI_CONTEXT.zip").is_file()


def test_unknown_game_gets_investigation_package(tmp_path: Path) -> None:
    game = tmp_path / "Unknown"
    (game / "Unknown_Data").mkdir(parents=True)
    package = generate_diagnostic_package(game, tmp_path / "out")
    profile = json.loads((package.directory / "game_profile.json").read_text())
    assert profile["compatibility_level"] == "investigation"
    assert json.loads((package.directory / "candidates.json").read_text()) == []
    assert "No registered adapter" in (package.directory / "problem.md").read_text()


def test_logical_package_content_is_reproducible(tmp_path: Path) -> None:
    game = make_game(tmp_path)
    first = generate_diagnostic_package(game, tmp_path / "first")
    second = generate_diagnostic_package(game, tmp_path / "second")
    with zipfile.ZipFile(first.zip_path) as left, zipfile.ZipFile(second.zip_path) as right:
        assert {name: left.read(name) for name in left.namelist()} == {name: right.read(name) for name in right.namelist()}
