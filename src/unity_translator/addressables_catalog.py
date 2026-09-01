"""Locate and neutralize the Addressables CRC recorded for a local AssetBundle.

Unity Addressables loads local bundles with
``AssetBundle.LoadFromFileAsync(path, crc)``, where ``crc`` comes from the
``AssetBundleRequestOptions`` stored in the content catalog. A CRC of ``0``
tells Unity to skip verification; any other value must match the bundle's
real CRC or the engine refuses to load it. Editing a bundle's bytes (to
translate its contents) changes its real CRC, so the catalog's recorded
value must be zeroed for that bundle before the edited build can run.

The JSON catalog format (``catalog*.json``) packs entries and their "extra
data" (which holds ``AssetBundleRequestOptions``) as base64-encoded binary
blobs inside otherwise-plain JSON. The byte layout implemented here follows
``UnityEngine.AddressableAssets.Utility.SerializationUtilities`` and
``JsonContentCatalogData`` from the ``com.unity.addressables`` package
source (``ReadObjectFromByteArray`` / ``WriteObjectToByteList`` for the
extra-data objects; the 7-int32-per-entry layout for ``m_EntryDataString``).
It has not been validated against a real Unity-built catalog — treat it as
unverified until confirmed against one.

Binary catalogs (``catalog*.bin``) use a completely different, more complex
format (``BinaryStorageBuffer``) and are intentionally not supported here;
see ``has_binary_catalog``.
"""

from __future__ import annotations

import base64
import json
import struct
from pathlib import Path
from typing import Any

_JSON_OBJECT_TYPE = 7  # ObjectType.JsonObject ordinal in SerializationUtilities.cs
_ENTRY_FIELDS_PER_RECORD = 7  # internalId, provider, depKey, depHash, dataIndex, primaryKey, resourceType


class CatalogFormatError(ValueError):
    """The catalog does not match the documented Addressables JSON binary layout."""


class BundleNotInCatalogError(LookupError):
    """This catalog's m_InternalIds does not reference the given bundle at all."""


def locate_catalogs(data_dir: Path) -> list[Path]:
    aa = data_dir / "StreamingAssets" / "aa"
    if not aa.is_dir():
        return []
    return sorted(aa.rglob("catalog*.json"))


def has_binary_catalog(data_dir: Path) -> bool:
    aa = data_dir / "StreamingAssets" / "aa"
    if not aa.is_dir():
        return False
    return any(aa.rglob("catalog*.bin"))


def _decode_entry_data(entry_bytes: bytes) -> list[dict[str, int]]:
    if len(entry_bytes) < 4:
        raise CatalogFormatError("m_EntryDataString is too short to contain an entry count")
    count = struct.unpack_from("<i", entry_bytes, 0)[0]
    record_size = 4 * _ENTRY_FIELDS_PER_RECORD
    if count < 0 or len(entry_bytes) < 4 + count * record_size:
        raise CatalogFormatError("m_EntryDataString length does not match its declared entry count")
    entries = []
    offset = 4
    for _ in range(count):
        fields = struct.unpack_from("<7i", entry_bytes, offset)
        entries.append({
            "internal_id_index": fields[0],
            "provider_index": fields[1],
            "dependency_key_index": fields[2],
            "dependency_hash": fields[3],
            "data_index": fields[4],
            "primary_key_index": fields[5],
            "resource_type_index": fields[6],
        })
        offset += record_size
    return entries


def _read_json_object(buffer: bytes, offset: int) -> tuple[str, str, int, int] | None:
    """Return (class_name, json_text, json_byte_start, json_byte_length) at offset, or None."""
    if offset < 0 or offset >= len(buffer):
        raise CatalogFormatError(f"extra-data offset out of range: {offset}")
    if buffer[offset] != _JSON_OBJECT_TYPE:
        return None
    pos = offset + 1
    if pos >= len(buffer):
        raise CatalogFormatError("extra-data JsonObject header runs past the buffer")
    assembly_len = buffer[pos]
    pos += 1 + assembly_len
    if pos >= len(buffer):
        raise CatalogFormatError("extra-data JsonObject header runs past the buffer")
    class_len = buffer[pos]
    pos += 1
    class_name = buffer[pos:pos + class_len].decode("ascii")
    pos += class_len
    if pos + 4 > len(buffer):
        raise CatalogFormatError("extra-data JsonObject header runs past the buffer")
    json_len = struct.unpack_from("<i", buffer, pos)[0]
    pos += 4
    if json_len < 0 or pos + json_len > len(buffer):
        raise CatalogFormatError("extra-data JsonObject json length runs past the buffer")
    json_text = buffer[pos:pos + json_len].decode("utf-16-le")
    return class_name, json_text, pos, json_len


def _crc_span(json_text: str) -> tuple[int, int]:
    marker = '"m_Crc":'
    key_index = json_text.index(marker)
    value_start = key_index + len(marker)
    while value_start < len(json_text) and json_text[value_start] in " \t":
        value_start += 1
    value_end = value_start
    while value_end < len(json_text) and json_text[value_end].isdigit():
        value_end += 1
    if value_end == value_start:
        raise CatalogFormatError("m_Crc value is not a plain integer literal")
    return value_start, value_end


def _read_crc_value(json_text: str) -> int:
    start, end = _crc_span(json_text)
    return int(json_text[start:end])


def _zero_crc_in_json_text(json_text: str) -> str:
    """Replace the m_Crc numeric literal with 0, preserving the exact character count.

    JSON permits whitespace between ``:`` and a value, so left-padding the
    single digit "0" keeps the surrounding byte offsets — and therefore
    every other entry's data_index — untouched.
    """
    start, end = _crc_span(json_text)
    padding = " " * (end - start - 1)
    return json_text[:start] + padding + "0" + json_text[end:]


def _matching_internal_id_indexes(internal_ids: list[str], bundle_filename: str) -> set[int]:
    return {
        index for index, internal_id in enumerate(internal_ids)
        if internal_id.replace("\\", "/").rsplit("/", 1)[-1] == bundle_filename
    }


def _find_bundle_data_offsets(matching_indexes: set[int], entries: list[dict[str, int]]) -> list[int]:
    return [
        entry["data_index"] for entry in entries
        if entry["internal_id_index"] in matching_indexes and entry["data_index"] >= 0
    ]


def neutralize_bundle_crc(catalog_path: Path, bundle_filename: str) -> dict[str, Any]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    try:
        entry_bytes = base64.b64decode(catalog["m_EntryDataString"])
        extra_data = bytearray(base64.b64decode(catalog["m_ExtraDataString"]))
    except KeyError as error:
        raise CatalogFormatError(f"Catalog is missing an expected field: {error}") from error

    entries = _decode_entry_data(entry_bytes)
    matching_indexes = _matching_internal_id_indexes(catalog.get("m_InternalIds") or [], bundle_filename)
    if not matching_indexes:
        raise BundleNotInCatalogError(f"{bundle_filename} is not referenced by {catalog_path}")
    data_offsets = _find_bundle_data_offsets(matching_indexes, entries)
    if not data_offsets:
        raise CatalogFormatError(
            f"Bundle {bundle_filename} is referenced in {catalog_path} but its catalog entry has no extra data"
        )

    crc_offsets: list[int] = []
    for offset in data_offsets:
        parsed = _read_json_object(bytes(extra_data), offset)
        if parsed is None:
            continue
        class_name, json_text, _start, _length = parsed
        if "AssetBundleRequestOptions" in class_name and '"m_Crc":' in json_text:
            crc_offsets.append(offset)
    if not crc_offsets:
        raise CatalogFormatError(
            f"Bundle {bundle_filename} is referenced in {catalog_path} but has no "
            "AssetBundleRequestOptions.m_Crc entry"
        )

    before: dict[int, int] = {}
    changed = False
    for offset in crc_offsets:
        _class_name, json_text, json_start, json_length = _read_json_object(bytes(extra_data), offset)
        before[offset] = _read_crc_value(json_text)
        if before[offset] == 0:
            continue
        patched_text = _zero_crc_in_json_text(json_text)
        patched_bytes = patched_text.encode("utf-16-le")
        if len(patched_bytes) != json_length:
            raise CatalogFormatError("CRC patch changed the serialized byte length; refusing to write")
        extra_data[json_start:json_start + json_length] = patched_bytes
        changed = True

    if not changed:
        return {"catalog": str(catalog_path), "bundle": bundle_filename, "crc_before": before, "crc_after": dict(before), "changed": False}

    catalog["m_ExtraDataString"] = base64.b64encode(bytes(extra_data)).decode("ascii")
    temporary = catalog_path.with_suffix(catalog_path.suffix + ".tmp")
    temporary.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    temporary.replace(catalog_path)

    reread = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    reread_extra = base64.b64decode(reread["m_ExtraDataString"])
    after: dict[int, int] = {}
    for offset in crc_offsets:
        parsed = _read_json_object(reread_extra, offset)
        if parsed is None:
            raise RuntimeError(f"Post-write catalog verification failed: entry vanished at offset {offset}")
        after[offset] = _read_crc_value(parsed[1])
        if after[offset] != 0:
            raise RuntimeError(f"Post-write catalog verification failed: CRC still {after[offset]} at offset {offset}")

    return {"catalog": str(catalog_path), "bundle": bundle_filename, "crc_before": before, "crc_after": after, "changed": True}
