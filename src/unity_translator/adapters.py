from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AdapterSpec:
    id: str
    version: int
    supported_formats: tuple[str, ...]
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...]

    def descriptor(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "supported_formats": list(self.supported_formats),
            "capabilities": list(self.capabilities),
            "limitations": list(self.limitations),
        }

    def validate_profile(self, profile: dict) -> None:
        if self.id == "unity-addressables-textasset":
            raise ValueError("Addressables adapter is diagnostic-only; full extraction is not available yet")
        if self.id == "streamingassets-csv":
            if not isinstance(profile.get("files"), list) or not profile["files"]:
                raise ValueError("Profile must declare at least one file rule")
        elif self.id == "unity-textasset-json":
            required = ("asset_file", "list_key", "id_field", "text_field", "textasset")
            missing = [field for field in required if field not in profile]
            if missing:
                raise ValueError(f"Unity JSON profile missing fields: {', '.join(missing)}")
        elif self.id == "holyknight-encrypted-tsv":
            if not isinstance(profile.get("source_root"), str) or not profile["source_root"]:
                raise ValueError("Holy Knight profile must declare source_root")
        elif self.id == "naninovel-addressables":
            # No profile fields beyond "extractor" exist yet: detection and extraction
            # are fully automatic. Explicit no-op so the absence of rules here is a
            # decision, not an oversight.
            pass

    def extract(self, project, manifest):
        from . import pipeline
        handlers = {
            "streamingassets-csv": pipeline._extract_streaming_csv,
            "unity-textasset-json": pipeline._extract_unity_json,
            "holyknight-encrypted-tsv": pipeline.extract_holyknight,
            "naninovel-addressables": pipeline._extract_naninovel,
        }
        return handlers[self.id](project, manifest)

    def inject(self, path, entries, profile):
        from . import pipeline
        asset_type = entries[0]["asset_type"]
        if asset_type == "StreamingAssetsCSV":
            return pipeline._inject_csv_file(path, entries)
        if asset_type == "TextAssetJSON":
            return pipeline._inject_unity_json_file(path, entries, profile)
        if asset_type == "HolyKnightEncryptedTSV":
            return pipeline.inject_holyknight_file(path, entries)
        if asset_type == "NaninovelScript":
            return pipeline._inject_naninovel_file(path, entries)
        raise ValueError(f"Unsupported asset type: {asset_type}")


_COMMON_CAPABILITIES = ("detect", "analyze", "extract", "export", "import", "validate", "inject", "verify")
_ADAPTERS = {
    "streamingassets-csv": AdapterSpec(
        "streamingassets-csv", 1, ("csv",), _COMMON_CAPABILITIES,
        ("columns require a profile",),
    ),
    "unity-textasset-json": AdapterSpec(
        "unity-textasset-json", 1, ("unity-serialized", "json"), _COMMON_CAPABILITIES,
        ("requires an explicit asset and TextAsset locator",),
    ),
    "holyknight-encrypted-tsv": AdapterSpec(
        "holyknight-encrypted-tsv", 1, ("encrypted-tsv",), _COMMON_CAPABILITIES,
        ("supports the known encrypted TSV layout",),
    ),
    "unity-addressables-textasset": AdapterSpec(
        "unity-addressables-textasset", 1, ("assetbundle", "addressables"), ("detect", "analyze"),
        ("Catalog Addressables not verified", "Full AssetBundle extraction/injection is not available yet"),
    ),
    "naninovel-addressables": AdapterSpec(
        "naninovel-addressables", 1, ("addressables", "assetbundle", "naninovel"),
        ("detect", "analyze", "extract", "export", "import", "validate", "inject", "verify"),
        ("Unsupported Naninovel records remain unchanged",),
    ),
}


def get_adapter(adapter_id: str) -> AdapterSpec:
    try:
        return _ADAPTERS[adapter_id]
    except KeyError as error:
        raise ValueError(f"Unknown adapter: {adapter_id}") from error


def list_adapters() -> list[str]:
    return sorted(_ADAPTERS)
