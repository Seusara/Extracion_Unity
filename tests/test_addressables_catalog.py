import base64
import json
import struct
from pathlib import Path

import pytest

from unity_translator import addressables_catalog as catalog_module

_REQUEST_OPTIONS_TYPE = "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions"


def _encode_json_object(class_name: str, json_obj: dict, assembly_name: str = "Unity.ResourceManager") -> bytes:
    assembly_bytes = assembly_name.encode("ascii")
    class_bytes = class_name.encode("ascii")
    json_bytes = json.dumps(json_obj, separators=(",", ":")).encode("utf-16-le")
    return (
        bytes([7])  # ObjectType.JsonObject, per SerializationUtilities.cs
        + bytes([len(assembly_bytes)]) + assembly_bytes
        + bytes([len(class_bytes)]) + class_bytes
        + struct.pack("<i", len(json_bytes))
        + json_bytes
    )


def _encode_entry_data(entries: list[tuple[int, int, int, int, int, int, int]]) -> bytes:
    body = b"".join(struct.pack("<7i", *entry) for entry in entries)
    return struct.pack("<i", len(entries)) + body


def _build_catalog(bundles: dict[str, int | None]) -> dict:
    """``bundles`` maps a bundle filename to its recorded CRC, or None for no extra data."""
    names = list(bundles)
    internal_ids = [f"{{UnityEngine.AddressableAssets.Addressables.RuntimePath}}/StandaloneWindows64/{name}" for name in names]
    extra = bytearray()
    entries = []
    for index, name in enumerate(names):
        crc = bundles[name]
        if crc is None:
            data_index = -1
        else:
            data_index = len(extra)
            extra.extend(_encode_json_object(
                _REQUEST_OPTIONS_TYPE,
                {"m_Hash": "abcdef0123456789", "m_Crc": crc, "m_BundleName": name, "m_BundleSize": 1024},
            ))
        entries.append((index, 0, -1, 0, data_index, 0, 0))
    return {
        "m_LocatorId": "AddressablesMainContentCatalog",
        "m_InternalIds": internal_ids,
        "m_ProviderIds": ["UnityEngine.ResourceManagement.ResourceProviders.AssetBundleProvider"],
        "m_EntryDataString": base64.b64encode(_encode_entry_data(entries)).decode("ascii"),
        "m_ExtraDataString": base64.b64encode(bytes(extra)).decode("ascii"),
        "m_KeyDataString": base64.b64encode(struct.pack("<i", 0)).decode("ascii"),
        "m_BucketDataString": base64.b64encode(struct.pack("<i", 0)).decode("ascii"),
    }


def _write_catalog(path: Path, bundles: dict[str, int | None]) -> dict:
    catalog = _build_catalog(bundles)
    path.write_text(json.dumps(catalog), encoding="utf-8")
    return catalog


def test_neutralize_bundle_crc_zeroes_nonzero_crc_without_disturbing_other_entries(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    _write_catalog(catalog_path, {"scene.bundle": 123456789, "other.bundle": 999})

    report = catalog_module.neutralize_bundle_crc(catalog_path, "scene.bundle")

    assert report["changed"] is True
    assert list(report["crc_before"].values()) == [123456789]
    assert list(report["crc_after"].values()) == [0]

    reread = json.loads(catalog_path.read_text(encoding="utf-8"))
    extra = base64.b64decode(reread["m_ExtraDataString"])
    scene_json = catalog_module._read_json_object(extra, 0)[1]
    assert '"m_Crc":0' in scene_json.replace(" ", "")
    other_offset = json.loads(catalog_path.read_text(encoding="utf-8"))
    entries = catalog_module._decode_entry_data(base64.b64decode(other_offset["m_EntryDataString"]))
    other_json = catalog_module._read_json_object(extra, entries[1]["data_index"])[1]
    assert catalog_module._read_crc_value(other_json) == 999


def test_neutralize_bundle_crc_is_a_no_op_when_already_zero(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    _write_catalog(catalog_path, {"scene.bundle": 0})
    before_bytes = catalog_path.read_bytes()

    report = catalog_module.neutralize_bundle_crc(catalog_path, "scene.bundle")

    assert report["changed"] is False
    assert report["crc_before"] == report["crc_after"]
    assert catalog_path.read_bytes() == before_bytes


def test_neutralize_bundle_crc_raises_bundle_not_in_catalog_when_unreferenced(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    _write_catalog(catalog_path, {"other.bundle": 42})

    with pytest.raises(catalog_module.BundleNotInCatalogError):
        catalog_module.neutralize_bundle_crc(catalog_path, "scene.bundle")


def test_neutralize_bundle_crc_raises_format_error_when_entry_has_no_request_options(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    _write_catalog(catalog_path, {"scene.bundle": None})

    with pytest.raises(catalog_module.CatalogFormatError):
        catalog_module.neutralize_bundle_crc(catalog_path, "scene.bundle")


def test_locate_catalogs_finds_json_catalogs_under_streaming_assets(tmp_path: Path) -> None:
    data_dir = tmp_path / "Game_Data"
    aa = data_dir / "StreamingAssets" / "aa" / "StandaloneWindows64"
    aa.mkdir(parents=True)
    (aa / "catalog_2024.01.01.json").write_text("{}", encoding="utf-8")

    result = catalog_module.locate_catalogs(data_dir)

    assert result == [aa / "catalog_2024.01.01.json"]


def test_locate_catalogs_returns_empty_when_no_addressables_folder(tmp_path: Path) -> None:
    data_dir = tmp_path / "Game_Data"
    data_dir.mkdir()

    assert catalog_module.locate_catalogs(data_dir) == []


def test_has_binary_catalog_detects_bin_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "Game_Data"
    aa = data_dir / "StreamingAssets" / "aa" / "StandaloneWindows64"
    aa.mkdir(parents=True)
    (aa / "catalog.bin").write_bytes(b"")

    assert catalog_module.has_binary_catalog(data_dir) is True


def test_has_binary_catalog_is_false_without_bin_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "Game_Data"
    aa = data_dir / "StreamingAssets" / "aa" / "StandaloneWindows64"
    aa.mkdir(parents=True)
    (aa / "catalog.json").write_text("{}", encoding="utf-8")

    assert catalog_module.has_binary_catalog(data_dir) is False
