import json
from pathlib import Path

import pytest

from unity_translator.addressables import inspect_catalog
from unity_translator.assetbundles import inspect_bundle


def test_addressables_fixture_relates_entries_to_bundles(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({
        "m_LocatorId": "test",
        "entries": [
            {"key": "dialogue", "internal_id": "aa/dialogue.bundle", "resource_type": "TextAsset"},
            {"key": "image", "internal_id": "aa/image.bundle", "resource_type": "Texture2D"},
        ],
    }), encoding="utf-8")
    result = inspect_catalog(catalog)
    assert result.locator_id == "test"
    assert result.bundles == ("aa/dialogue.bundle", "aa/image.bundle")
    assert result.entries[0].resource_type == "TextAsset"


def test_real_shape_compact_catalog_keeps_bundle_evidence(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({
        "m_LocatorId": "AddressablesMainContentCatalog",
        "m_InternalIds": ["_START", "StandaloneWindows64/scripts.bundle"],
        "m_resourceTypes": [{"m_ClassName": "UnityEngine.TextAsset"}],
    }), encoding="utf-8")
    result = inspect_catalog(catalog)
    assert result.bundles == ("StandaloneWindows64/scripts.bundle",)
    assert result.warnings
    assert "UnityEngine.TextAsset" in result.resource_types


def test_invalid_catalog_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid Addressables catalog"):
        inspect_catalog(path)


def test_corrupt_bundle_is_reported_without_raising(tmp_path: Path) -> None:
    path = tmp_path / "broken.bundle"
    path.write_bytes(b"not a Unity bundle")
    result = inspect_bundle(path)
    assert result.readable is False
    assert result.error
    assert result.sha256.startswith("sha256:")
