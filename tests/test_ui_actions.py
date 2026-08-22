from pathlib import Path

from unity_translator.ui import open_folder, start_executable


def test_open_folder_uses_the_system_launcher(tmp_path: Path) -> None:
    calls: list[str] = []

    result = open_folder(tmp_path, launcher=calls.append)

    assert result == tmp_path.resolve()
    assert calls == [str(tmp_path.resolve())]


def test_start_executable_uses_its_parent_as_working_directory(tmp_path: Path) -> None:
    executable = tmp_path / "Sample Game.exe"
    executable.write_bytes(b"fixture")
    calls: list[tuple[list[str], str]] = []

    def launcher(command: list[str], cwd: str) -> object:
        calls.append((command, cwd))
        return object()

    result = start_executable(executable, launcher=launcher)

    assert result == executable.resolve()
    assert calls == [([str(executable.resolve())], str(tmp_path.resolve()))]
