import pytest

from unity_translator.adapters import get_adapter, list_adapters


def test_registry_exposes_all_current_adapters() -> None:
    assert list_adapters() == [
        "holyknight-encrypted-tsv",
        "streamingassets-csv",
        "unity-textasset-json",
    ]


def test_registry_descriptor_has_capabilities_and_limits() -> None:
    descriptor = get_adapter("streamingassets-csv").descriptor()
    assert descriptor["id"] == "streamingassets-csv"
    assert "extract" in descriptor["capabilities"]
    assert "columns require a profile" in descriptor["limitations"]


def test_unknown_adapter_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown adapter"):
        get_adapter("unknown-format")
