from pathlib import Path
from types import SimpleNamespace

import pytest

import unity_translator.naninovel as naninovel


def test_known_types_closes_dnfile_handle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = tmp_path / "Game_Data"
    managed = data / "Managed"
    managed.mkdir(parents=True)
    dll = managed / "Example.dll"
    dll.write_bytes(b"fixture")
    closed = []

    class FakePE:
        net = SimpleNamespace(mdtables=SimpleNamespace(TypeDef=[]))

        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(naninovel.dnfile, "dnPE", lambda _path: FakePE())
    parser = naninovel.NaninovelParser.__new__(naninovel.NaninovelParser)
    parser.data_dir = data

    parser._known_types()

    assert closed == [True]


def test_known_types_reports_assemblies_that_fail_to_parse(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = tmp_path / "Game_Data"
    managed = data / "Managed"
    managed.mkdir(parents=True)
    (managed / "Broken.dll").write_bytes(b"fixture")

    def raise_dnpe(_path: str):
        raise OSError("corrupt PE header")

    monkeypatch.setattr(naninovel.dnfile, "dnPE", raise_dnpe)
    parser = naninovel.NaninovelParser.__new__(naninovel.NaninovelParser)
    parser.data_dir = data

    parser._known_types()

    assert parser.failed_assemblies == ["Broken"]
