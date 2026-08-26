from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .analyzer import analyze_game
from .storage import write_json_atomic

_PACKAGE_NAME = "AI_CONTEXT"
_SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    "credentials.json",
    "secrets.json",
    "token.json",
    "auth.json",
}
_SENSITIVE_SUFFIXES = {".sav", ".save", ".key", ".pem", ".p12", ".logins"}


@dataclass(frozen=True)
class DiagnosticPackage:
    directory: Path
    zip_path: Path


def _is_sensitive(path: Path) -> bool:
    name = path.name.casefold()
    return name in _SENSITIVE_NAMES or path.suffix.casefold() in _SENSITIVE_SUFFIXES or name.startswith("screenshot")


def _tree(root: Path, max_depth: int, max_files: int) -> tuple[str, dict[str, Any]]:
    lines = ["<GameRoot>/"]
    included_files = 0
    truncated = False

    def visit(directory: Path, prefix: str, depth: int) -> None:
        nonlocal included_files, truncated
        try:
            children = sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold()))
        except OSError:
            lines.append(f"{prefix}└── [unreadable]")
            return
        safe_children = [child for child in children if not _is_sensitive(child)]
        for index, child in enumerate(safe_children):
            is_last = index == len(safe_children) - 1
            branch = "└── " if is_last else "├── "
            if child.is_dir():
                lines.append(f"{prefix}{branch}{child.name}/")
                if depth >= max_depth:
                    truncated = True
                    lines.append(f"{prefix}{'    ' if is_last else '│   '}└── [TRUNCATED: depth limit]")
                else:
                    visit(child, prefix + ("    " if is_last else "│   "), depth + 1)
                continue
            if included_files >= max_files:
                truncated = True
                lines.append(f"{prefix}{branch}[TRUNCATED: file limit]")
                break
            lines.append(f"{prefix}{branch}{child.name}")
            included_files += 1

    visit(root, "", 0)
    metadata = {
        "max_depth": max_depth,
        "max_files": max_files,
        "included_files": included_files,
        "truncated": truncated,
    }
    return "\n".join(lines) + "\n", metadata


def _json(path: Path, value: Any) -> None:
    write_json_atomic(path, value)


def _problem(analysis: dict) -> str:
    level = analysis.get("compatibility_level", "investigation").upper()
    candidates = analysis.get("candidates", [])
    lines = [
        "# Unity Translation Tool — Investigation Problem",
        "",
        f"Compatibility: {level}",
        f"Data root: {analysis.get('data_dir', '<GameRoot>')}",
        "",
    ]
    if candidates:
        lines.extend([
            "The analyzer found one or more adapter candidates, but the current result requires human confirmation or further investigation.",
            "",
            "Candidates and confidence:",
        ])
        for candidate in candidates:
            lines.append(f"- {candidate['adapter_id']}: {candidate['confidence']:.2f}")
    else:
        lines.extend([
            "No registered adapter can safely complete extraction and reinjection for the detected structure.",
            "",
            "The objective is to determine where translatable text lives and whether the solution can become a reusable adapter.",
        ])
    limitations = [item for candidate in candidates for item in candidate.get("limitations", [])]
    if limitations:
        lines.extend(["", "Known limitations:"])
        lines.extend(f"- {item}" for item in dict.fromkeys(limitations))
    lines.extend([
        "",
        "Investigation protocol:",
        "INSPECT → FORM HYPOTHESIS → TEST → OBSERVE → REFINE → SOLVE → GENERALIZE",
        "",
        "Never modify original game files without a verified backup. Work on a copy and preserve negative results.",
    ])
    return "\n".join(lines) + "\n"


def _readme(analysis: dict) -> str:
    return f"""# Unity Translation Tool — Investigation Package

This package contains sanitized analysis context for a Unity game.

## Compatibility

**{analysis.get('compatibility_level', 'investigation').upper()}**

## Objective

Determine where translatable text lives and whether the solution can become a reusable adapter.

This package contains metadata and diagnostic evidence only. Original game assets, executables, DLL contents, saves, credentials and complete translations are not included.

## Safety

**Do not modify original files without a backup.** Work on a separate copy, test deterministically, and preserve the original installation.

## Investigation protocol

```text
INSPECT
→ FORM HYPOTHESIS
→ TEST
→ OBSERVE
→ REFINE
→ SOLVE
→ GENERALIZE
```

After a fix, stop and review:

1. What was specific to this game?
2. What belongs to a reusable family or framework?
3. Which observable signatures detect it?
4. Can it become an adapter without a game-name condition?
5. Which false positives and tests must be added?
"""


def _adapter_api() -> str:
    return """# Adapter API

Add compatibility as a reusable adapter, not as a game-name condition.

## Contract

An adapter should expose or declare:

```text
detect(analysis) -> candidate
a​​nalyze(context) -> structured findings
extract(context) -> Translation IR
validate(context) -> validation issues
inject(context) -> modified copy
verify(context) -> verification result
```

## Metadata

Each registered adapter declares:

```text
id
version
supported_formats / formats
capabilities
limitations
```

Candidates must preserve confidence and human-readable evidence explaining why the adapter was considered.

## Rules

- Prefer framework and format signatures over game names.
- Keep the core unaware of adapter-specific parsing.
- Never modify the source game directly.
- Add positive and negative fixtures before claiming support.
- If extraction or reinjection is not safe, expose a diagnostic-only candidate instead of guessing.
""".replace("a​​nalyze", "analyze")


def _expected_tests() -> str:
    return """# Expected Tests Before Accepting Compatibility

A reusable adapter should provide evidence for:

1. Detection and negative detection.
2. Stable confidence and explainable evidence.
3. Extraction into Translation IR.
4. CSV export/import round-trip.
5. Placeholder, tag and escape validation.
6. Backup creation and original-file preservation.
7. Injection of a controlled change on a copy.
8. Post-injection verification.
9. Failure handling without partial source modification.
10. At least one unrelated fixture to prove the adapter is not game-name-specific.

If any stage cannot be executed, document the exact reason and leave the compatibility level experimental, assisted or investigation.
"""


def generate_diagnostic_package(
    game_path: str | Path,
    output_path: str | Path | None = None,
    *,
    max_depth: int = 5,
    max_files: int = 500,
) -> DiagnosticPackage:
    game = Path(game_path).resolve()
    output = Path(output_path).resolve() if output_path else game / _PACKAGE_NAME
    directory = output / _PACKAGE_NAME
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)

    analysis = analyze_game(game)
    structure, tree_metadata = _tree(game, max_depth=max_depth, max_files=max_files)
    profile = {
        "unity_version": analysis.get("unity_version", "unknown"),
        "runtime": analysis.get("runtime", "unknown"),
        "data_root": analysis.get("data_dir", "<GameRoot>"),
        "compatibility_level": analysis.get("compatibility_level", "investigation"),
    }
    signatures = {
        "frameworks": analysis.get("frameworks", []),
        "framework_evidence": analysis.get("framework_evidence", []),
        "addressables": bool(analysis.get("addressables")),
        "asset_bundles": bool(analysis.get("bundles")),
        "streaming_assets": bool(analysis.get("streaming_assets")),
        "serialized_assets": bool(analysis.get("serialized_assets")),
        "resource_blobs": bool(analysis.get("resource_blobs")),
        "managed": bool(analysis.get("managed")),
        "globalgamemanagers": bool(analysis.get("globalgamemanagers")),
    }
    assemblies = {
        "names": sorted({Path(item).name for item in analysis.get("dlls", [])}),
        "contents_included": False,
    }
    diagnostics = {
        "schema_version": 1,
        "tool": "UnityTranslator",
        "game_profile": profile,
        "directory_structure": tree_metadata,
        "source_assets_included": False,
        "executables_included": False,
        "sensitive_files_included": False,
    }

    (directory / "README.md").write_text(_readme(analysis), encoding="utf-8")
    (directory / "problem.md").write_text(_problem(analysis), encoding="utf-8")
    _json(directory / "diagnostics.json", diagnostics)
    _json(directory / "game_profile.json", profile)
    _json(directory / "candidates.json", analysis.get("candidates", []))
    (directory / "directory_structure.txt").write_text(structure, encoding="utf-8")
    _json(directory / "detected_signatures.json", signatures)
    _json(directory / "assemblies.json", assemblies)
    logs = directory / "logs"
    logs.mkdir()
    logs.joinpath("analysis.log").write_text(
        "[ANALYZE] UnityTranslator diagnostic package\n"
        f"[ANALYZE] Compatibility: {profile['compatibility_level']}\n"
        f"[ANALYZE] Runtime: {profile['runtime']}\n"
        f"[ANALYZE] Candidates: {len(analysis.get('candidates', []))}\n"
        f"[ANALYZE] Tree truncated: {tree_metadata['truncated']}\n",
        encoding="utf-8",
    )
    (directory / "adapter_api.md").write_text(_adapter_api(), encoding="utf-8")
    (directory / "expected_tests.md").write_text(_expected_tests(), encoding="utf-8")

    zip_path = output / f"{_PACKAGE_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        files = sorted(directory.rglob("*"), key=lambda file: file.relative_to(directory).as_posix())
        for file in files:
            if file.is_file():
                archive.write(file, Path(_PACKAGE_NAME, file.relative_to(directory)).as_posix())
    return DiagnosticPackage(directory=directory, zip_path=zip_path)
