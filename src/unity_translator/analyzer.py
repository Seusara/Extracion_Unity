from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import UnityPy

from .adapters import get_adapter, list_adapters
from .holyknight import PROFILE as HOLYKNIGHT_PROFILE
from .holyknight import detect as detect_holyknight
from .naninovel import detect_naninovel

_MAX_DISCOVERY_DEPTH = 2
_FORMATS = {".json", ".csv", ".tsv", ".xml", ".txt", ".dat"}


@dataclass(frozen=True)
class CandidateResult:
    adapter_id: str
    adapter_version: int
    confidence: float
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]
    capabilities: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {
            "evidence": list(self.evidence),
            "limitations": list(self.limitations),
            "capabilities": list(self.capabilities),
        }


def _candidate(adapter_id: str, confidence: float, evidence: list[str], limitations: list[str] | None = None) -> dict:
    adapter = get_adapter(adapter_id)
    return CandidateResult(
        adapter_id=adapter.id,
        adapter_version=adapter.version,
        confidence=round(max(0.0, min(1.0, confidence)), 2),
        evidence=tuple(dict.fromkeys(evidence)),
        limitations=tuple(dict.fromkeys(limitations or adapter.limitations)),
        capabilities=adapter.capabilities,
    ).to_dict()


def _discovered_data_dirs(selected: Path) -> list[Path]:
    selected = selected.resolve()
    candidates: list[Path] = []
    search_roots = [selected]
    if selected.is_dir():
        search_roots.extend(child for child in selected.iterdir() if child.is_dir())
    for path in search_roots:
        candidates.extend(item for item in path.glob("*_Data") if item.is_dir())
    unique = sorted(set(candidates))
    return [path for path in unique if not any(parent != path and parent in path.parents for parent in unique)]


def find_data_dir(game_path: Path) -> Path | None:
    candidates = _discovered_data_dirs(game_path)
    return candidates[0] if len(candidates) == 1 else None


def _display_path(path: Path, root: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        relative = path.name
    return f"<GameRoot>/{relative}" if relative else "<GameRoot>"


def _detect_unity_version(data_dir: Path) -> str:
    managers = data_dir / "globalgamemanagers"
    if not managers.is_file():
        return "unknown"
    try:
        env = UnityPy.load(str(managers))
        versions = [getattr(asset, "unity_version", None) for asset in env.assets]
        for asset_file in env.files.values():
            stream = getattr(getattr(asset_file, "reader", None), "stream", None)
            if stream is not None and hasattr(stream, "close"):
                stream.close()
        return next((version for version in versions if version), "unknown")
    except Exception:
        return "unknown"


def _runtime(data_dir: Path, game_root: Path) -> str:
    managed = data_dir / "Managed"
    il2cpp = data_dir / "il2cpp_data"
    game_assembly = game_root / "GameAssembly.dll"
    if il2cpp.is_dir() or game_assembly.is_file():
        return "il2cpp"
    if managed.is_dir():
        return "mono"
    return "unknown"


def _compatibility(candidates: list[dict]) -> str:
    plausible = [item for item in candidates if item["confidence"] >= 0.5]
    if not plausible:
        return "investigation"
    fully_capable = [
        item for item in plausible
        if {"extract", "inject"}.issubset(item["capabilities"])
    ]
    if len(plausible) == 1 and fully_capable and plausible[0]["confidence"] >= 0.9:
        return "automatic"
    return "assisted"


def _frameworks(files: list[Path], root: Path) -> tuple[list[str], list[str]]:
    known = {
        "naninovel": "Naninovel",
        "pixelcrushers": "Pixel Crushers",
        "localization": "Unity Localization",
        "stringtable": "Unity Localization/String Tables",
        "2dtoolkit": "2D Toolkit",
        "textmeshpro": "TextMeshPro",
    }
    labels: set[str] = set()
    evidence: list[str] = []
    for path in files:
        haystack = str(path).casefold()
        for marker, label in known.items():
            if marker in haystack:
                labels.add(label)
                evidence.append(f"{label}: {_display_path(path, root)}")
    return sorted(labels), evidence


def _inspect(data_dir: Path, root: Path) -> tuple[dict, list[Path]]:
    files = [path for path in data_dir.rglob("*") if path.is_file()]
    relative = lambda path: _display_path(path, root)
    asset_files = sorted(path for path in files if path.suffix.casefold() == ".assets" or path.name.casefold().startswith("sharedassets"))
    resource_files = sorted(path for path in files if path.suffix.casefold() == ".resource")
    bundle_files = sorted(path for path in files if path.suffix.casefold() == ".bundle")
    external_files = sorted(path for path in files if path.suffix.casefold() in _FORMATS)
    dlls = sorted(path for path in files if path.suffix.casefold() == ".dll")
    textasset_candidates = sorted(path for path in external_files if path.suffix.casefold() in {".json", ".csv", ".tsv", ".xml", ".txt"})
    streaming = data_dir / "StreamingAssets"
    addressables = streaming / "aa"
    frameworks, framework_evidence = _frameworks(files, root)
    return {
        "inspected_files": [relative(path) for path in sorted(files)],
        "asset_files": [relative(path) for path in asset_files],
        "resource_files": [relative(path) for path in resource_files],
        "bundle_files": [relative(path) for path in bundle_files],
        "external_text_files": [relative(path) for path in external_files],
        "textasset_candidates": [relative(path) for path in textasset_candidates],
        "dlls": [relative(path) for path in dlls],
        "frameworks": frameworks,
        "framework_evidence": framework_evidence,
        "serialized_assets": bool(asset_files),
        "resource_blobs": bool(resource_files),
        "bundles": bool(bundle_files),
        "data_dir_files": files,
    }, files


def _detect_candidates(data_dir: Path, root: Path, inventory: dict) -> list[dict]:
    candidates: list[dict] = []
    streaming = data_dir / "StreamingAssets"
    csv_files = sorted(path for path in streaming.rglob("*.csv") if path.is_file()) if streaming.is_dir() else []
    if csv_files:
        confidence = 0.95 if any(path.name.casefold() == "dialogue.csv" for path in csv_files) else 0.7
        evidence = [f"StreamingAssets/{path.relative_to(streaming).as_posix()}" for path in csv_files[:10]]
        evidence.append(f"{len(csv_files)} CSV file(s) available for profile-based extraction")
        candidates.append(_candidate("streamingassets-csv", confidence, evidence, ["Columns require a profile"] if confidence < 0.9 else []))

    if detect_holyknight(data_dir):
        dat_files = [path for path in (data_dir / "StreamingAssets" / "Lang" / "en").glob("*.dat") if path.is_file()]
        candidates.append(_candidate(
            "holyknight-encrypted-tsv", 0.99,
            ["StreamingAssets/Lang/en/*.dat", f"{len(dat_files)} encrypted TSV candidate file(s)", "Known encrypted-table signature detected"],
            ["Supports the known encrypted TSV layout"],
        ))

    if inventory["serialized_assets"]:
        evidence = ["Serialized Unity asset files detected"]
        evidence.extend(inventory["asset_files"][:5])
        limitations = ["TextAsset content was not fully decoded during discovery", "Requires an explicit asset and TextAsset locator"]
        candidates.append(_candidate("unity-textasset-json", 0.55, evidence, limitations))

    if inventory["bundles"] and (data_dir / "StreamingAssets" / "aa").is_dir():
        candidates.append(_candidate(
            "unity-addressables-textasset", 0.72,
            ["StreamingAssets/aa detected", f"{len(inventory['bundle_files'])} AssetBundle file(s) found"],
            ["Catalog Addressables not verified", "Full AssetBundle extraction/injection is not available yet"],
        ))
    naninovel = detect_naninovel(root)
    if naninovel["family"]:
        candidates.append(_candidate(
            "naninovel-addressables",
            naninovel["confidence"],
            naninovel["evidence"] + [f"{naninovel['script_bundles']} Addressables bundle(s) in the build"],
            ["Serialized Naninovel script writer and bundle injection are not verified"],
        ))
    return sorted(candidates, key=lambda item: (-item["confidence"], item["adapter_id"]))


def analyze_game(game_path: Path, sanitize_paths: bool = True) -> dict:
    selected = game_path.resolve()
    data_dirs = _discovered_data_dirs(selected)
    if len(data_dirs) != 1:
        result = {
            "game_path": str(selected),
            "is_unity": False,
            "runtime": "unknown",
            "unity_version": "unknown",
            "compatibility": "investigation",
            "compatibility_level": "investigation",
            "candidates": [],
            "game_candidates": [str(path) for path in data_dirs],
            "reason": "No se encontró exactamente una carpeta *_Data en la profundidad segura de búsqueda",
        }
        if sanitize_paths:
            result["game_path"] = "<GameRoot>"
            result["game_candidates"] = [f"<GameRoot>/{path.name}" for path in data_dirs]
        return result

    data_dir = data_dirs[0]
    root = data_dir.parent
    inventory, files = _inspect(data_dir, root)
    candidates = _detect_candidates(data_dir, root, inventory)
    version = _detect_unity_version(data_dir)
    result = {
        "game_path": str(root),
        "data_dir": str(data_dir),
        "data_dir_name": data_dir.name,
        "is_unity": True,
        "unity_version": version,
        "runtime": _runtime(data_dir, root),
        "managed": (data_dir / "Managed").is_dir(),
        "streaming_assets": (data_dir / "StreamingAssets").is_dir(),
        "resources": (data_dir / "Resources").is_dir(),
        "addressables": (data_dir / "StreamingAssets" / "aa").is_dir(),
        "globalgamemanagers": (data_dir / "globalgamemanagers").is_file(),
        "resources_assets": (data_dir / "resources.assets").is_file(),
        "asset_files": inventory["asset_files"],
        "resource_files": inventory["resource_files"],
        "bundle_files": inventory["bundle_files"],
        "external_text_files": inventory["external_text_files"],
        "textasset_candidates": inventory["textasset_candidates"],
        "dlls": inventory["dlls"],
        "frameworks": inventory["frameworks"],
        "framework_evidence": inventory["framework_evidence"],
        "inspected_files": inventory["inspected_files"],
        "serialized_assets": inventory["serialized_assets"],
        "resource_blobs": inventory["resource_blobs"],
        "bundles": inventory["bundles"],
        "candidates": candidates,
        "compatibility_level": _compatibility(candidates),
        "compatibility": _compatibility(candidates),
    }
    if sanitize_paths:
        result["game_path"] = "<GameRoot>"
        result["data_dir"] = _display_path(data_dir, root)
    return result


def detect_profile(game_path: Path) -> dict | None:
    """Suggest a supported profile from the game's on-disk structure."""
    analysis = analyze_game(game_path, sanitize_paths=False)
    if not analysis.get("is_unity"):
        return None
    data_dir = Path(analysis["data_dir"])
    if detect_holyknight(data_dir):
        return dict(HOLYKNIGHT_PROFILE)
    dialogue = data_dir / "StreamingAssets" / "dialogue.csv"
    if dialogue.is_file():
        return {
            "extractor": "streamingassets-csv",
            "files": [{"glob": "dialogue.csv", "columns": [1], "header": True}],
        }
    if detect_naninovel(game_path)["family"]:
        return {"extractor": "naninovel-addressables"}
    return None
