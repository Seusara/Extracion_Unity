from types import SimpleNamespace

import pytest

from unity_translator import naninovel_audit


def _fake_environment() -> SimpleNamespace:
    return SimpleNamespace(
        objects=[SimpleNamespace(type=SimpleNamespace(name="MonoBehaviour"), path_id=1)],
        files={},
    )


def test_audit_reports_uncovered_text_like_fields(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "Game_Data"
    bundle_dir = data_dir / "StreamingAssets" / "aa" / "StandaloneWindows64"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "scene.bundle").write_bytes(b"fixture")

    class FakeParser:
        def __init__(self, _root) -> None:
            self.data_dir = data_dir

        def _parse_script(self, _obj):
            return "scene", [
                ("Naninovel.Commands.PrintText", {"Text": {"value": "Covered dialogue line"}}),
                ("Naninovel.Commands.SetCharacterExpression", {
                    "Expression": "happy",
                    "Summary": {"value": "An uncovered summary line"},
                }),
            ]

    monkeypatch.setattr(naninovel_audit, "NaninovelParser", FakeParser)
    monkeypatch.setattr(naninovel_audit.UnityPy, "load", lambda _path: _fake_environment())

    report = naninovel_audit.audit_command_coverage(tmp_path)

    assert report == {"Naninovel.Commands.SetCharacterExpression.Summary": 1}


def test_audit_reports_nothing_when_everything_is_covered_or_noise(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "Game_Data"
    bundle_dir = data_dir / "StreamingAssets" / "aa" / "StandaloneWindows64"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "scene.bundle").write_bytes(b"fixture")

    class FakeParser:
        def __init__(self, _root) -> None:
            self.data_dir = data_dir

        def _parse_script(self, _obj):
            return "scene", [
                ("Naninovel.Commands.PrintText", {"Text": {"value": "Covered dialogue line"}}),
                ("Naninovel.Commands.SetCharacterExpression", {"Expression": "happy"}),
            ]

    monkeypatch.setattr(naninovel_audit, "NaninovelParser", FakeParser)
    monkeypatch.setattr(naninovel_audit.UnityPy, "load", lambda _path: _fake_environment())

    report = naninovel_audit.audit_command_coverage(tmp_path)

    assert report == {}


def test_audit_counts_repeated_occurrences_across_bundles(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "Game_Data"
    bundle_dir = data_dir / "StreamingAssets" / "aa" / "StandaloneWindows64"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "scene1.bundle").write_bytes(b"fixture1")
    (bundle_dir / "scene2.bundle").write_bytes(b"fixture2")

    class FakeParser:
        def __init__(self, _root) -> None:
            self.data_dir = data_dir

        def _parse_script(self, _obj):
            return "scene", [
                ("Naninovel.Commands.SetCharacterExpression", {"Summary": {"value": "An uncovered summary line"}}),
            ]

    monkeypatch.setattr(naninovel_audit, "NaninovelParser", FakeParser)
    monkeypatch.setattr(naninovel_audit.UnityPy, "load", lambda _path: _fake_environment())

    report = naninovel_audit.audit_command_coverage(tmp_path)

    assert report == {"Naninovel.Commands.SetCharacterExpression.Summary": 2}
