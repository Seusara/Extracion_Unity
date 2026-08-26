from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AddressableEntry:
    key: str
    internal_id: str
    provider: str | None
    resource_type: str | None
    bundle: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "internal_id": self.internal_id,
            "provider": self.provider,
            "resource_type": self.resource_type,
            "bundle": self.bundle,
        }


@dataclass(frozen=True)
class CatalogInspection:
    path: str
    locator_id: str | None
    entries: tuple[AddressableEntry, ...]
    bundles: tuple[str, ...]
    resource_types: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "locator_id": self.locator_id,
            "entry_count": len(self.entries),
            "entries": [entry.as_dict() for entry in self.entries],
            "bundles": list(self.bundles),
            "resource_types": list(self.resource_types),
            "warnings": list(self.warnings),
        }


def _bundle_from_internal_id(internal_id: str) -> str | None:
    normalized = internal_id.replace("\\", "/")
    if not normalized.lower().endswith(".bundle"):
        return None
    return normalized


def _fixture_entries(document: dict[str, Any]) -> list[AddressableEntry] | None:
    raw_entries = document.get("entries")
    if not isinstance(raw_entries, list):
        return None
    entries: list[AddressableEntry] = []
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, dict) or not isinstance(raw.get("key"), str):
            raise ValueError(f"Invalid Addressables fixture entry at index {index}")
        internal_id = raw.get("internal_id", "")
        if not isinstance(internal_id, str):
            raise ValueError(f"Invalid internal_id at fixture entry {index}")
        entries.append(AddressableEntry(
            key=raw["key"],
            internal_id=internal_id,
            provider=raw.get("provider"),
            resource_type=raw.get("resource_type"),
            bundle=raw.get("bundle") or _bundle_from_internal_id(internal_id),
        ))
    return entries


def inspect_catalog(path: str | Path) -> CatalogInspection:
    catalog_path = Path(path)
    try:
        document = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid Addressables catalog: {catalog_path}: {error}") from error
    if not isinstance(document, dict):
        raise ValueError(f"Addressables catalog must be a JSON object: {catalog_path}")

    fixture_entries = _fixture_entries(document)
    warnings: list[str] = []
    if fixture_entries is not None:
        entries = fixture_entries
    else:
        internal_ids = document.get("m_InternalIds")
        if not isinstance(internal_ids, list):
            raise ValueError("Addressables catalog has no supported entry or m_InternalIds data")
        entries = [
            AddressableEntry(
                key=f"internal-id:{index}",
                internal_id=value,
                provider=None,
                resource_type=None,
                bundle=_bundle_from_internal_id(value) if isinstance(value, str) else None,
            )
            for index, value in enumerate(internal_ids)
            if isinstance(value, str)
        ]
        warnings.append("Compact catalog entries were not fully decoded; keys/providers are inferred")

    bundles = tuple(sorted({entry.bundle for entry in entries if entry.bundle}))
    resource_types: list[str] = []
    for item in document.get("m_resourceTypes", []):
        if isinstance(item, dict) and isinstance(item.get("m_ClassName"), str):
            resource_types.append(item["m_ClassName"])
    return CatalogInspection(
        path=str(catalog_path),
        locator_id=document.get("m_LocatorId") if isinstance(document.get("m_LocatorId"), str) else None,
        entries=tuple(entries),
        bundles=bundles,
        resource_types=tuple(dict.fromkeys(resource_types)),
        warnings=tuple(warnings),
    )
