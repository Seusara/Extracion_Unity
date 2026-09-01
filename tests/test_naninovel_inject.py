import base64
import json
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from unity_translator import addressables_catalog, naninovel_inject
from unity_translator.storage import sha256_file


def _bundle(tmp_path: Path, content: bytes) -> Path:
    data_dir = tmp_path / "Game_Data"
    data_dir.mkdir(parents=True, exist_ok=True)
    bundle = data_dir / "scene.bundle"
    bundle.write_bytes(content)
    return bundle


def _bundle_under_addressables(tmp_path: Path, content: bytes) -> tuple[Path, Path]:
    data_dir = tmp_path / "Game_Data"
    bundle = data_dir / "StreamingAssets" / "aa" / "StandaloneWindows64" / "naninovel" / "scripts" / "scene.bundle"
    bundle.parent.mkdir(parents=True, exist_ok=True)
    bundle.write_bytes(content)
    return data_dir, bundle


def _encode_json_object(class_name: str, json_obj: dict) -> bytes:
    assembly_bytes = b"Unity.ResourceManager"
    class_bytes = class_name.encode("ascii")
    json_bytes = json.dumps(json_obj, separators=(",", ":")).encode("utf-16-le")
    return (
        bytes([7])
        + bytes([len(assembly_bytes)]) + assembly_bytes
        + bytes([len(class_bytes)]) + class_bytes
        + struct.pack("<i", len(json_bytes))
        + json_bytes
    )


def _write_single_bundle_catalog(catalog_path: Path, bundle_name: str, crc: int) -> None:
    extra = _encode_json_object(
        "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions",
        {"m_Hash": "abcdef0123456789", "m_Crc": crc, "m_BundleName": bundle_name, "m_BundleSize": 1024},
    )
    entry_data = struct.pack("<i", 1) + struct.pack("<7i", 0, 0, -1, 0, 0, 0, 0)
    catalog = {
        "m_InternalIds": [f"{{RuntimePath}}/StandaloneWindows64/{bundle_name}"],
        "m_ProviderIds": ["UnityEngine.ResourceManagement.ResourceProviders.AssetBundleProvider"],
        "m_EntryDataString": base64.b64encode(entry_data).decode("ascii"),
        "m_ExtraDataString": base64.b64encode(extra).decode("ascii"),
        "m_KeyDataString": base64.b64encode(struct.pack("<i", 0)).decode("ascii"),
        "m_BucketDataString": base64.b64encode(struct.pack("<i", 0)).decode("ascii"),
    }
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")


def _entry(path_id: int, translated: str, bundle_hash: str) -> dict:
    return {
        "id": f"scene.bundle:{path_id}:0:Text",
        "translated_text": translated,
        "metadata": {
            "path_id": path_id,
            "asset": f"ASSET_{path_id}",
            "entry_index": 0,
            "field": "Text",
            "bundle_hash": bundle_hash,
        },
    }


class FakeAssetsFile:
    def __init__(self, path_id: int, calls: list[int]) -> None:
        self._path_id = path_id
        self._calls = calls

    def mark_changed(self) -> None:
        self._calls.append(self._path_id)


class FakeObject:
    def __init__(self, path_id: int, parsed: dict, mark_changed_calls: list[int]) -> None:
        self.type = SimpleNamespace(name="MonoBehaviour")
        self.path_id = path_id
        self.assets_file = FakeAssetsFile(path_id, mark_changed_calls)
        self.data = None

    def set_raw_data(self, data: bytes) -> None:
        self.data = data
        self.assets_file.mark_changed()


class FakeEnvironment:
    def __init__(self, objects: list[FakeObject], rebuilt_content: bytes) -> None:
        self.objects = objects
        self.files: dict = {}
        self._rebuilt_content = rebuilt_content

    def save(self, pack: str, out_path: str) -> None:
        (Path(out_path) / "scene.bundle").write_bytes(self._rebuilt_content)


@pytest.fixture
def two_object_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    original = b"original bundle bytes"
    bundle_path = _bundle(tmp_path, original)
    bundle_hash = sha256_file(bundle_path)

    records = {
        7: (b"prefix7", [SimpleNamespace(
            index=0, raw=b"", class_name="PrintText", namespace="Naninovel.Commands",
            assembly="Elringus.Naninovel.Runtime", parsed={"Text": {"value": "Original A"}}, tree=object(),
        )]),
        8: (b"prefix8", [SimpleNamespace(
            index=0, raw=b"", class_name="PrintText", namespace="Naninovel.Commands",
            assembly="Elringus.Naninovel.Runtime", parsed={"Text": {"value": "Original B"}}, tree=object(),
        )]),
    }
    mark_changed_calls: list[int] = []
    objects = [
        FakeObject(7, records[7][1][0].parsed, mark_changed_calls),
        FakeObject(8, records[8][1][0].parsed, mark_changed_calls),
    ]
    environment = FakeEnvironment(objects, rebuilt_content=b"rebuilt bundle bytes")

    monkeypatch.setattr(naninovel_inject.UnityPy, "load", lambda _path: environment)
    monkeypatch.setattr(naninovel_inject, "NaninovelParser", lambda _root: object())
    monkeypatch.setattr(naninovel_inject, "_read_records", lambda _parser, obj: records[obj.path_id])
    monkeypatch.setattr(naninovel_inject, "write_typetree", lambda _parsed, _tree, writer, _assets_file: writer.write_aligned_string("record"))

    entries = [
        _entry(7, "Translated A", bundle_hash),
        _entry(8, "Translated B", bundle_hash),
    ]
    return bundle_path, entries, records, mark_changed_calls


def test_inject_bundle_persists_changes_to_every_touched_object(two_object_bundle):
    bundle_path, entries, records, mark_changed_calls = two_object_bundle

    changed = naninovel_inject.inject_bundle(bundle_path, entries)

    assert changed == 2
    assert records[7][1][0].parsed["Text"]["value"] == "Translated A"
    assert records[8][1][0].parsed["Text"]["value"] == "Translated B"


def test_inject_bundle_marks_every_touched_object_changed_not_just_the_last(two_object_bundle):
    bundle_path, entries, _records, mark_changed_calls = two_object_bundle

    naninovel_inject.inject_bundle(bundle_path, entries)

    assert set(mark_changed_calls) == {7, 8}


@pytest.fixture
def single_object_addressables_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    original = b"original bundle bytes"
    data_dir, bundle_path = _bundle_under_addressables(tmp_path, original)
    bundle_hash = sha256_file(bundle_path)

    record = SimpleNamespace(
        index=0, raw=b"", class_name="PrintText", namespace="Naninovel.Commands",
        assembly="Elringus.Naninovel.Runtime", parsed={"Text": {"value": "Original"}}, tree=object(),
    )
    mark_changed_calls: list[int] = []
    obj = FakeObject(7, record.parsed, mark_changed_calls)
    environment = FakeEnvironment([obj], rebuilt_content=b"rebuilt bundle bytes")

    monkeypatch.setattr(naninovel_inject.UnityPy, "load", lambda _path: environment)
    monkeypatch.setattr(naninovel_inject, "NaninovelParser", lambda _root: object())
    monkeypatch.setattr(naninovel_inject, "_read_records", lambda _parser, _obj: (b"prefix", [record]))
    monkeypatch.setattr(naninovel_inject, "write_typetree", lambda _parsed, _tree, writer, _assets_file: writer.write_aligned_string("record"))

    entry = _entry(7, "Translated", bundle_hash)
    return data_dir, bundle_path, entry


def test_inject_bundle_neutralizes_the_addressables_catalog_crc(single_object_addressables_bundle):
    data_dir, bundle_path, entry = single_object_addressables_bundle
    catalog_path = data_dir / "StreamingAssets" / "aa" / "catalog.json"
    _write_single_bundle_catalog(catalog_path, "scene.bundle", crc=999888777)

    naninovel_inject.inject_bundle(bundle_path, [entry])

    updated = json.loads(catalog_path.read_text(encoding="utf-8"))
    extra = base64.b64decode(updated["m_ExtraDataString"])
    _class_name, json_text, _start, _length = addressables_catalog._read_json_object(extra, 0)
    assert addressables_catalog._read_crc_value(json_text) == 0


def test_inject_bundle_raises_when_only_a_binary_catalog_is_present(single_object_addressables_bundle):
    data_dir, bundle_path, entry = single_object_addressables_bundle
    (data_dir / "StreamingAssets" / "aa" / "catalog.bin").write_bytes(b"")

    with pytest.raises(RuntimeError, match="[Bb]inary"):
        naninovel_inject.inject_bundle(bundle_path, [entry])


def test_inject_bundle_succeeds_without_any_addressables_catalog(single_object_addressables_bundle):
    _data_dir, bundle_path, entry = single_object_addressables_bundle

    changed = naninovel_inject.inject_bundle(bundle_path, [entry])

    assert changed == 1
