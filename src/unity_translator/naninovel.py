from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.helpers.TypeTreeHelper import read_typetree
from UnityPy.helpers.TypeTreeNode import TypeTreeNode
from UnityPy.streams import EndianBinaryReader

from .storage import sha256_file, sha256_text

try:
    import dnfile
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    dnfile = None


TEXT_FIELDS: dict[str, tuple[tuple[str, ...], str]] = {
    "Naninovel.Commands.PrintText": (("Text",), "dialogue"),
    "Naninovel.Commands.AddChoice": (("ChoiceSummary",), "choice"),
    "Naninovel.Commands.ShowToastUI": (("Text", "Message"), "ui_command"),
}
COMMON_UNITY_FIELDS = {"m_GameObject", "m_Enabled", "m_Script", "m_Name"}


def _close_environment(environment: Any) -> None:
    for asset_file in getattr(environment, "files", {}).values():
        stream = getattr(getattr(asset_file, "reader", None), "stream", None)
        if stream is not None and hasattr(stream, "close"):
            stream.close()


def _parameter_value(value: Any) -> str:
    if isinstance(value, dict) and "value" in value:
        value = value["value"]
    return value if isinstance(value, str) else ""


def _read_aligned_string(reader: EndianBinaryReader) -> str:
    value = reader.read_aligned_string()
    return value if isinstance(value, str) else ""


class NaninovelParser:
    """Read serialized Naninovel Script objects without game-name rules."""

    def __init__(self, game_root: str | Path):
        self.game_root = Path(game_root).resolve()
        data_dirs = sorted(self.game_root.glob("*_Data"))
        if len(data_dirs) != 1:
            raise ValueError(f"Expected exactly one *_Data directory, found {len(data_dirs)}")
        self.data_dir = data_dirs[0]
        manager = self.data_dir / "globalgamemanagers"
        environment = UnityPy.load(str(manager))
        versions = [file.unity_version for file in environment.files.values() if getattr(file, "unity_version", None)]
        _close_environment(environment)
        if not versions:
            raise ValueError("Unity version could not be read from globalgamemanagers")
        self.generator = TypeTreeGenerator(versions[0])
        self.generator.load_local_game(str(self.game_root))
        self.assemblies = {name.removesuffix(".dll") for name in self.generator.get_loaded_dll_names()}
        self.known_types = self._known_types()
        self.known_types.add(("Assembly-CSharp", "Command_SpriteController"))
        self.node_cache: dict[tuple[str, str], TypeTreeNode] = {}
        self.unparsed_types: Counter[str] = Counter()

    def _known_types(self) -> set[tuple[str, str]]:
        self.failed_assemblies: list[str] = []
        if dnfile is None:
            return set()
        known: set[tuple[str, str]] = set()
        for dll in (self.data_dir / "Managed").glob("*.dll"):
            pe = None
            try:
                pe = dnfile.dnPE(str(dll))
                if not pe.net or not pe.net.mdtables.TypeDef:
                    continue
                for typedef in pe.net.mdtables.TypeDef:
                    cls = str(typedef.TypeName)
                    namespace = str(typedef.TypeNamespace)
                    known.add((dll.stem, f"{namespace}.{cls}" if namespace else cls))
            except Exception:
                self.failed_assemblies.append(dll.stem)
                continue
            finally:
                if pe is not None:
                    pe.close()
        return known

    def _type_tree(self, assembly: str, fullname: str) -> TypeTreeNode:
        key = (assembly, fullname)
        if key not in self.node_cache:
            nodes = self.generator.get_nodes(assembly, fullname)
            values = [{
                "m_Level": node.m_Level,
                "m_Type": node.m_Type,
                "m_Name": node.m_Name,
                "m_MetaFlag": node.m_MetaFlag,
            } for node in nodes]
            start = next((i for i, node in enumerate(values[1:], 1)
                          if node["m_Level"] == 1 and node["m_Name"] not in COMMON_UNITY_FIELDS), None)
            custom = [{"m_Level": 0, "m_Type": fullname.rsplit(".", 1)[-1],
                       "m_Name": "Base", "m_MetaFlag": 0}]
            if start is not None:
                custom.extend(values[start:])
            self.node_cache[key] = TypeTreeNode.from_list(custom)
        return self.node_cache[key]

    @staticmethod
    def _read_string(data: bytes, position: int) -> tuple[str | None, int]:
        if position + 4 > len(data):
            return None, position
        size = int.from_bytes(data[position:position + 4], "little", signed=True)
        position += 4
        if size < 0 or size > 1024 or position + size > len(data):
            return None, position
        try:
            value = data[position:position + size].decode("utf-8")
        except UnicodeDecodeError:
            return None, position
        return value, (position + size + 3) & ~3

    def _header_at(self, data: bytes, position: int) -> bool:
        cls, position = self._read_string(data, position)
        namespace, position = self._read_string(data, position)
        assembly, _ = self._read_string(data, position)
        if not cls or namespace is None or not assembly:
            return False
        return (assembly.removesuffix(".dll"), f"{namespace}.{cls}" if namespace else cls) in self.known_types

    def _next_header(self, data: bytes, position: int) -> int:
        for candidate in range((position + 3) & ~3, len(data) - 12, 4):
            if self._header_at(data, candidate):
                return candidate
        return len(data)

    def _parse_script(self, obj: Any) -> tuple[str, list[tuple[str, dict[str, Any] | None]]]:
        raw = obj.get_raw_data()
        reader = EndianBinaryReader(raw, "<")
        reader.read_int(); reader.read_long(); reader.read_byte(); reader.align_stream(4)
        reader.read_int(); reader.read_long()
        script_name = _read_aligned_string(reader)
        line_count = reader.read_int()
        for _ in range(line_count):
            reader.read_int()
        if reader.read_int() != 1:
            raise ValueError("Unsupported Naninovel script registry version")
        entries: list[tuple[str, dict[str, Any] | None]] = []
        while reader.Position < len(obj.get_raw_data()):
            class_name = _read_aligned_string(reader)
            namespace = _read_aligned_string(reader)
            assembly = _read_aligned_string(reader)
            if not class_name and not namespace and not assembly:
                entries.append(("", None)); continue
            fullname = f"{namespace}.{class_name}" if namespace else class_name
            start = reader.Position
            try:
                tree = self._type_tree(assembly.removesuffix(".dll"), fullname)
                parsed = read_typetree(tree, reader, as_dict=True, check_read=False)
            except Exception:
                self.unparsed_types[fullname] += 1
                entries.append((fullname, None))
                reader.Position = self._next_header(raw, start)
                continue
            if reader.Position <= start:
                raise ValueError("Naninovel parser did not advance")
            entries.append((fullname, parsed))
        return script_name, entries

    def extract(self) -> list[dict[str, Any]]:
        script_root = self.data_dir / "StreamingAssets" / "aa"
        bundles = sorted(script_root.glob("StandaloneWindows64/**/*.bundle"))
        rows: list[dict[str, Any]] = []
        for bundle_path in bundles:
            environment = None
            try:
                environment = UnityPy.load(str(bundle_path))
                for obj in environment.objects:
                    if obj.type.name != "MonoBehaviour":
                        continue
                    bundle = next((item for item in environment.objects if item.type.name == "AssetBundle"), None)
                    if bundle is None:
                        continue
                    bundle_data = bundle.read()
                    containers = getattr(bundle_data, "m_Container", [])
                    container = next((item for item in containers if item[1].asset.path_id == obj.path_id), None)
                    if container is None or not container[0].lower().endswith(".nani"):
                        continue
                    script_name, entries = self._parse_script(obj)
                    relative = bundle_path.relative_to(self.game_root).as_posix()
                    occurrences: Counter[tuple[str, str]] = Counter()
                    for entry_index, (fullname, parsed) in enumerate(entries):
                        rule = TEXT_FIELDS.get(fullname)
                        if not rule or not parsed:
                            continue
                        for field in rule[0]:
                            text = _parameter_value(parsed.get(field))
                            if not text.strip():
                                continue
                            occurrence = occurrences[(field, text)]
                            occurrences[(field, text)] += 1
                            rows.append({
                                "id": f"{relative}:{obj.path_id}:{entry_index}:{field}",
                                "source_file": relative,
                                "asset_type": "NaninovelScript",
                                "object_identifier": container[0],
                                "field": field,
                                "original_text": text,
                                "translated_text": "",
                                "original_hash": sha256_text(text),
                                "status": "untranslated",
                                "metadata": {
                                    "bundle": relative,
                                    "asset": container[0],
                                    "path_id": obj.path_id,
                                    "type": fullname,
                                    "field": field,
                                    "bundle_hash": sha256_file(bundle_path),
                                    "category": rule[1],
                                    "raw_occurrence": occurrence,
                                    "entry_index": entry_index,
                                },
                            })
            except Exception:
                # One unreadable/custom bundle must not hide other candidates.
                continue
            finally:
                if environment is not None:
                    _close_environment(environment)
        return rows


def detect_naninovel(game_root: str | Path) -> dict[str, Any]:
    root = Path(game_root).resolve()
    data_dirs = sorted(root.glob("*_Data"))
    managed = data_dirs[0] / "Managed" if len(data_dirs) == 1 else Path()
    assemblies = {path.name for path in managed.glob("*.dll")} if managed.is_dir() else set()
    script_bundles = list((data_dirs[0] / "StreamingAssets" / "aa").glob("StandaloneWindows64/**/*.bundle")) if len(data_dirs) == 1 else []
    has_runtime = {"Elringus.Naninovel.Runtime.dll", "Naninovel.Common.dll"} <= assemblies
    has_naninovel_paths = any(
        "naninovel" in path.relative_to(data_dirs[0]).as_posix().casefold()
        for path in script_bundles
    )
    evidence = []
    if has_runtime: evidence.append("Naninovel runtime assemblies detected")
    if has_naninovel_paths: evidence.append("Naninovel-named Addressables bundles detected")
    return {
        "family": "Naninovel" if evidence else None,
        "confidence": min(0.95, 0.55 + 0.2 * len(evidence)) if evidence else 0.0,
        "evidence": evidence,
        "script_bundles": len(script_bundles),
    }