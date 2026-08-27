from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import UnityPy
from UnityPy.helpers.TypeTreeHelper import EndianBinaryWriter, read_typetree, write_typetree
from UnityPy.streams import EndianBinaryReader

from .naninovel import NaninovelParser
from .storage import sha256_file


def _close_environment(environment: Any) -> None:
    for asset_file in getattr(environment, "files", {}).values():
        stream = getattr(getattr(asset_file, "reader", None), "stream", None)
        if stream is not None and hasattr(stream, "close"):
            stream.close()


def _write_string(writer: EndianBinaryWriter, value: str) -> None:
    writer.write_aligned_string(value)


def _serialized_text(value: Any) -> str | None:
    if isinstance(value, dict) and isinstance(value.get("value"), str):
        return value["value"]
    return value if isinstance(value, str) else None


def _verification_result(entry: dict, expected_text: str, **values: Any) -> dict[str, Any]:
    result = {
        "entry_id": entry.get("id"),
        "expected_text": expected_text,
        "status": "fail",
        "ok": False,
    }
    result.update(values)
    return result


def verify_naninovel_entry(
    bundle_path: str | Path,
    entry: dict,
    expected_text: str,
) -> dict[str, Any]:
    """Reopen a rebuilt bundle and compare one serialized value to the IR."""
    if expected_text != entry.get("translated_text"):
        return _verification_result(
            entry,
            expected_text,
            error_code="expected_text_mismatch",
            message="Expected verification text differs from the Translation IR",
        )
    metadata = entry.get("metadata", {})
    environment = None
    try:
        environment = UnityPy.load(str(bundle_path))
        path_id = int(metadata["path_id"])
        obj = next((item for item in environment.objects
                    if item.type.name == "MonoBehaviour" and item.path_id == path_id), None)
        if obj is None:
            return _verification_result(
                entry,
                expected_text,
                error_code="object_not_found",
                message=f"Naninovel object path_id not found: {path_id}",
            )

        expected_asset = metadata.get("asset")
        if expected_asset:
            bundle_objects = [item for item in environment.objects if item.type.name == "AssetBundle"]
            if bundle_objects:
                bundle_data = bundle_objects[0].read()
                containers = getattr(bundle_data, "m_Container", [])
                asset_match = next((item for item in containers
                                    if item[1].asset.path_id == path_id), None)
                if asset_match is None or asset_match[0] != expected_asset:
                    return _verification_result(
                        entry,
                        expected_text,
                        error_code="asset_not_found",
                        message=f"Naninovel asset locator did not match: {expected_asset}",
                    )

        data_dir = next((parent for parent in Path(bundle_path).parents
                         if parent.name.endswith("_Data")), None)
        game_root = data_dir.parent if data_dir is not None else Path(bundle_path).parent
        parser = NaninovelParser(game_root)
        _prefix, records = _read_records(parser, obj)
        entry_index = int(metadata["entry_index"])
        record = next((item for item in records if item.index == entry_index), None)
        if record is None or record.parsed is None:
            return _verification_result(
                entry,
                expected_text,
                error_code="entry_not_found",
                message=f"Naninovel entry index not found or unsupported: {entry_index}",
            )
        field = metadata["field"]
        if field not in record.parsed:
            return _verification_result(
                entry,
                expected_text,
                error_code="field_not_found",
                message=f"Naninovel field not found: {field}",
            )
        actual_text = _serialized_text(record.parsed[field])
        if actual_text != expected_text:
            return _verification_result(
                entry,
                expected_text,
                error_code="text_mismatch",
                actual_text=actual_text,
                message="Serialized Naninovel text differs from the expected Translation IR value",
            )
        return {
            "entry_id": entry.get("id"),
            "status": "pass",
            "ok": True,
            "expected_text": expected_text,
            "actual_text": actual_text,
            "path_id": path_id,
            "entry_index": entry_index,
            "field": field,
        }
    except (KeyError, TypeError, ValueError, OSError, RuntimeError) as error:
        return _verification_result(
            entry,
            expected_text,
            error_code="verification_error",
            message=str(error),
        )
    finally:
        if environment is not None:
            _close_environment(environment)


@dataclass
class _Record:
    index: int
    raw: bytes
    class_name: str
    namespace: str
    assembly: str
    parsed: dict[str, Any] | None
    tree: Any = None


def _read_records(parser: NaninovelParser, obj: Any) -> tuple[bytes, list[_Record]]:
    raw = obj.get_raw_data()
    reader = EndianBinaryReader(raw, "<")
    reader.read_int(); reader.read_long(); reader.read_byte(); reader.align_stream(4)
    reader.read_int(); reader.read_long(); reader.read_aligned_string()
    line_count = reader.read_int()
    for _ in range(line_count):
        reader.read_int()
    if reader.read_int() != 1:
        raise ValueError("Unsupported Naninovel script registry version")
    prefix = raw[:reader.Position]
    records: list[_Record] = []
    while reader.Position < len(raw):
        record_start = reader.Position
        class_name = reader.read_aligned_string()
        namespace = reader.read_aligned_string()
        assembly = reader.read_aligned_string()
        if not class_name and not namespace and not assembly:
            records.append(_Record(len(records), raw[record_start:reader.Position], "", "", "", None))
            continue
        payload_start = reader.Position
        fullname = f"{namespace}.{class_name}" if namespace else class_name
        parsed = None
        tree = None
        try:
            tree = parser._type_tree(assembly.removesuffix(".dll"), fullname)
            parsed = read_typetree(tree, reader, as_dict=True, check_read=False)
            if (reader.Position != len(raw)
                    and not parser._header_at(raw, reader.Position)
                    and raw[reader.Position:reader.Position + 12] != b"\0" * 12):
                raise ValueError("serialized record boundary is not valid")
        except Exception:
            reader.Position = parser._next_header(raw, payload_start)
            tree = None
        records.append(_Record(
            len(records), raw[record_start:reader.Position], class_name, namespace, assembly, parsed, tree,
        ))
    return prefix, records


def _rewrite_object(parser: NaninovelParser, obj: Any, replacements: dict[tuple[int, str], str]) -> int:
    prefix, records = _read_records(parser, obj)
    output = bytearray(prefix)
    changed = 0
    for record in records:
        replacement_fields = {field: text for (index, field), text in replacements.items() if index == record.index}
        if not replacement_fields or record.parsed is None or record.tree is None:
            output.extend(record.raw)
            continue
        for field, text in replacement_fields.items():
            if field not in record.parsed or not isinstance(record.parsed[field], (str, dict)):
                raise ValueError(f"Naninovel field is not writable: {record.class_name}.{field}")
            if isinstance(record.parsed[field], dict):
                record.parsed[field]["value"] = text
            else:
                record.parsed[field] = text
            changed += 1
        writer = EndianBinaryWriter(endian="<")
        _write_string(writer, record.class_name)
        _write_string(writer, record.namespace)
        _write_string(writer, record.assembly)
        write_typetree(record.parsed, record.tree, writer, obj.assets_file)
        output.extend(writer.bytes)
    if changed != len(replacements):
        raise ValueError(f"Only {changed} of {len(replacements)} Naninovel entries were rewritten")
    obj.set_raw_data(bytes(output))
    return changed


def inject_bundle(path: str | Path, entries: list[dict]) -> int:
    bundle_path = Path(path)
    if not entries:
        return 0
    expected = {entry["metadata"].get("bundle_hash") for entry in entries}
    if len(expected) != 1 or None in expected or sha256_file(bundle_path) != next(iter(expected)):
        raise ValueError(f"Bundle hash mismatch before injection: {bundle_path}")
    data_dir = next((parent for parent in bundle_path.parents if parent.name.endswith("_Data")), None)
    if data_dir is None:
        raise ValueError(f"Bundle is not below a Unity data directory: {bundle_path}")
    parser = NaninovelParser(data_dir.parent)
    environment = UnityPy.load(str(bundle_path))
    try:
        grouped: dict[int, dict[tuple[int, str], str]] = {}
        for entry in entries:
            metadata = entry["metadata"]
            grouped.setdefault(int(metadata["path_id"]), {})[(int(metadata["entry_index"]), metadata["field"])] = entry["translated_text"]
        changed = 0
        for path_id, replacements in grouped.items():
            obj = next((item for item in environment.objects
                        if item.type.name == "MonoBehaviour" and item.path_id == path_id), None)
            if obj is None:
                raise ValueError(f"Naninovel object path_id not found: {path_id}")
            changed += _rewrite_object(parser, obj, replacements)
        if changed != len(entries):
            raise ValueError(f"Expected {len(entries)} changes, applied {changed}")
        obj.assets_file.mark_changed()
        with tempfile.TemporaryDirectory() as output_dir:
            environment.save(pack="lz4", out_path=output_dir)
            generated = Path(output_dir) / bundle_path.name
            if not generated.is_file():
                raise RuntimeError("UnityPy did not produce the rebuilt bundle")
            _close_environment(environment)
            shutil.copy2(generated, bundle_path)
    finally:
        _close_environment(environment)
    if sha256_file(bundle_path) == next(iter(expected)):
        raise RuntimeError("Bundle hash did not change after injection")
    for entry in entries:
        verification = verify_naninovel_entry(bundle_path, entry, entry["translated_text"])
        if not verification["ok"]:
            raise RuntimeError(
                f"Post-injection Naninovel verification failed for {entry['id']}: "
                f"{verification.get('error_code')}: {verification.get('message', '')}"
            )
    return changed