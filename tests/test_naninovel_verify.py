from types import SimpleNamespace

import pytest

from unity_translator import pipeline
import unity_translator.naninovel_inject as naninovel_inject


ENTRY = {
    "id": "scene.bundle:7:24:Text",
    "translated_text": "PRUEBA_UNITYTRANSLATOR_12345",
    "metadata": {
        "path_id": 7,
        "asset": "TEST_DIALOGUE",
        "entry_index": 24,
        "field": "Text",
    },
}


class FakeEnvironment:
    def __init__(self, value: str = ENTRY["translated_text"], path_id: int = 7) -> None:
        self.objects = [SimpleNamespace(type=SimpleNamespace(name="MonoBehaviour"), path_id=path_id)]
        self.files = {}
        self.value = value


@pytest.fixture
def fake_verifier(monkeypatch: pytest.MonkeyPatch):
    environment = FakeEnvironment()
    monkeypatch.setattr(naninovel_inject.UnityPy, "load", lambda _path: environment)
    monkeypatch.setattr(naninovel_inject, "NaninovelParser", lambda _root: object())
    monkeypatch.setattr(
        naninovel_inject,
        "_read_records",
        lambda _parser, _obj: (b"", [SimpleNamespace(
            index=24,
            class_name="PrintText",
            namespace="Naninovel.Commands",
            assembly="Elringus.Naninovel.Runtime",
            parsed={"Text": {"value": environment.value}},
            tree=object(),
            raw=b"",
        )]),
    )
    return environment


def test_verify_naninovel_entry_accepts_longer_translation(fake_verifier, tmp_path):
    result = naninovel_inject.verify_naninovel_entry(tmp_path / "scene.bundle", ENTRY, ENTRY["translated_text"])

    assert result["ok"] is True
    assert result["status"] == "pass"
    assert result["actual_text"] == ENTRY["translated_text"]
    assert result["expected_text"] == ENTRY["translated_text"]


def test_verify_naninovel_entry_accepts_shorter_translation(fake_verifier, tmp_path):
    fake_verifier.value = "Corto"
    entry = {**ENTRY, "translated_text": "Corto"}

    result = naninovel_inject.verify_naninovel_entry(tmp_path / "scene.bundle", entry, "Corto")

    assert result["ok"] is True
    assert result["actual_text"] == "Corto"


def test_verify_naninovel_entry_accepts_unchanged_text(fake_verifier, tmp_path):
    fake_verifier.value = "Original"
    entry = {**ENTRY, "translated_text": "Original"}

    result = naninovel_inject.verify_naninovel_entry(tmp_path / "scene.bundle", entry, "Original")

    assert result["ok"] is True


def test_verify_naninovel_entry_returns_controlled_failure_for_wrong_locator(fake_verifier, tmp_path):
    entry = {**ENTRY, "metadata": {**ENTRY["metadata"], "path_id": 999}}

    result = naninovel_inject.verify_naninovel_entry(tmp_path / "scene.bundle", entry, ENTRY["translated_text"])

    assert result["ok"] is False
    assert result["status"] == "fail"
    assert result["error_code"] == "object_not_found"


def test_verify_naninovel_entry_returns_controlled_failure_for_wrong_expected_text(fake_verifier, tmp_path):
    fake_verifier.value = "Different actual text"
    result = naninovel_inject.verify_naninovel_entry(
        tmp_path / "scene.bundle", ENTRY, ENTRY["translated_text"]
    )

    assert result["ok"] is False
    assert result["status"] == "fail"
    assert result["error_code"] == "text_mismatch"
    assert result["actual_text"] == "Different actual text"


def test_verify_naninovel_entry_returns_controlled_failure_when_expected_text_differs_from_ir(fake_verifier, tmp_path):
    result = naninovel_inject.verify_naninovel_entry(
        tmp_path / "scene.bundle", ENTRY, "Something the IR never recorded"
    )

    assert result["ok"] is False
    assert result["status"] == "fail"
    assert result["error_code"] == "expected_text_mismatch"


def test_verify_naninovel_entry_returns_controlled_failure_for_missing_entry_index(fake_verifier, tmp_path):
    entry = {**ENTRY, "metadata": {**ENTRY["metadata"], "entry_index": 999}}

    result = naninovel_inject.verify_naninovel_entry(tmp_path / "scene.bundle", entry, ENTRY["translated_text"])

    assert result["ok"] is False
    assert result["status"] == "fail"
    assert result["error_code"] == "entry_not_found"


def test_verify_naninovel_entry_returns_controlled_failure_for_missing_field(fake_verifier, tmp_path):
    entry = {**ENTRY, "metadata": {**ENTRY["metadata"], "field": "MissingField"}}

    result = naninovel_inject.verify_naninovel_entry(tmp_path / "scene.bundle", entry, ENTRY["translated_text"])

    assert result["ok"] is False
    assert result["status"] == "fail"
    assert result["error_code"] == "field_not_found"


def test_verify_naninovel_entry_returns_controlled_failure_for_wrong_asset_locator(fake_verifier, tmp_path):
    bundle_data = SimpleNamespace(m_Container=[("OTHER_ASSET", SimpleNamespace(asset=SimpleNamespace(path_id=7)))])
    fake_verifier.objects.append(
        SimpleNamespace(type=SimpleNamespace(name="AssetBundle"), read=lambda: bundle_data)
    )

    result = naninovel_inject.verify_naninovel_entry(tmp_path / "scene.bundle", ENTRY, ENTRY["translated_text"])

    assert result["ok"] is False
    assert result["status"] == "fail"
    assert result["error_code"] == "asset_not_found"


def test_verify_naninovel_entry_returns_controlled_failure_for_unexpected_error(fake_verifier, tmp_path):
    entry = {**ENTRY, "metadata": {key: value for key, value in ENTRY["metadata"].items() if key != "path_id"}}

    result = naninovel_inject.verify_naninovel_entry(tmp_path / "scene.bundle", entry, ENTRY["translated_text"])

    assert result["ok"] is False
    assert result["status"] == "fail"
    assert result["error_code"] == "verification_error"


def test_verify_naninovel_entry_does_not_change_unrelated_records(monkeypatch, tmp_path):
    environment = FakeEnvironment()
    environment.objects = [
        SimpleNamespace(type=SimpleNamespace(name="MonoBehaviour"), path_id=7),
        SimpleNamespace(type=SimpleNamespace(name="MonoBehaviour"), path_id=8),
    ]
    records = {
        7: [SimpleNamespace(index=24, parsed={"Text": {"value": "Changed"}}, raw=b"target")],
        8: [SimpleNamespace(index=25, parsed={"Text": {"value": "Untouched"}}, raw=b"unrelated")],
    }
    monkeypatch.setattr(naninovel_inject.UnityPy, "load", lambda _path: environment)
    monkeypatch.setattr(naninovel_inject, "NaninovelParser", lambda _root: object())
    monkeypatch.setattr(naninovel_inject, "_read_records", lambda _parser, obj: (b"", records[obj.path_id]))

    entry = {**ENTRY, "translated_text": "Changed"}
    result = naninovel_inject.verify_naninovel_entry(tmp_path / "scene.bundle", entry, "Changed")

    assert result["ok"] is True
    assert records[8][0].parsed["Text"]["value"] == "Untouched"


def test_pipeline_passes_translation_ir_to_naninovel_injector(monkeypatch, tmp_path):
    captured = {}

    def fake_inject(bundle_path, entries):
        captured["bundle_path"] = bundle_path
        captured["entries"] = entries

    monkeypatch.setattr(pipeline, "inject_naninovel_bundle", fake_inject)
    pipeline._inject_naninovel_file(tmp_path / "scene.bundle", [ENTRY])

    assert captured["entries"][0]["translated_text"] == ENTRY["translated_text"]
    assert captured["entries"][0]["metadata"]["entry_index"] == 24


def test_pipeline_does_not_hide_naninovel_verification_failure(monkeypatch, tmp_path):
    def failing_inject(_bundle_path, _entries):
        raise RuntimeError("Post-injection Naninovel verification failed")

    monkeypatch.setattr(pipeline, "inject_naninovel_bundle", failing_inject)

    with pytest.raises(RuntimeError, match="Post-injection Naninovel verification failed"):
        pipeline._inject_naninovel_file(tmp_path / "scene.bundle", [ENTRY])
