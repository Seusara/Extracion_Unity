from __future__ import annotations

import csv
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .analyzer import analyze_game
from .storage import read_json, sha256_file, sha256_text, write_json_atomic
from .validation import validate_pair

TOOL_VERSION = "0.1.0"
CSV_FIELDS = ["id", "original", "translation", "intentionally_empty"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _log(project: Path, stage: str, message: str) -> None:
    log = project / "logs" / "pipeline.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"[{stage}] {message}\n")


def analyze(game_path: str | Path) -> dict:
    return analyze_game(Path(game_path))


def create_project(game_path: str | Path, project_path: str | Path, profile: dict) -> dict:
    game = Path(game_path).resolve()
    project = Path(project_path).resolve()
    analysis = analyze_game(game)
    if not analysis["is_unity"]:
        raise ValueError(analysis["reason"])
    if profile.get("extractor") != "streamingassets-csv":
        raise ValueError("MVP only supports extractor 'streamingassets-csv'")
    if not isinstance(profile.get("files"), list) or not profile["files"]:
        raise ValueError("Profile must declare at least one file rule")
    for folder in ("originals", "translations", "builds", "backups", "logs"):
        (project / folder).mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "tool_version": TOOL_VERSION,
        "created_at": _now(),
        "game_path": str(game),
        "analysis": analysis,
        "extractor": {"name": "streamingassets-csv", "version": 1, "support": "experimental"},
        "profile": deepcopy(profile),
        "source_files": {},
    }
    write_json_atomic(project / "manifest.json", manifest)
    _log(project, "PROJECT", f"Created for {game}")
    return manifest


def _project(project_path: str | Path) -> tuple[Path, dict]:
    project = Path(project_path).resolve()
    manifest_path = project / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Project manifest not found: {manifest_path}")
    return project, read_json(manifest_path)


def _source_paths(manifest: dict, rule: dict) -> list[Path]:
    data_dir = Path(manifest["analysis"]["data_dir"])
    streaming = data_dir / "StreamingAssets"
    paths = sorted(path for path in streaming.glob(rule["glob"]) if path.is_file())
    if not paths:
        raise FileNotFoundError(f"Profile glob matched no files: {rule['glob']}")
    return paths


def extract(project_path: str | Path) -> list[dict]:
    project, manifest = _project(project_path)
    data_dir_name = manifest["analysis"]["data_dir_name"]
    streaming = Path(manifest["analysis"]["data_dir"]) / "StreamingAssets"
    entries: list[dict] = []
    seen: set[str] = set()
    source_files: dict[str, str] = {}

    for rule in manifest["profile"]["files"]:
        columns = rule.get("columns")
        if not isinstance(columns, list) or not columns or not all(isinstance(col, int) and col >= 0 for col in columns):
            raise ValueError(f"Rule requires non-negative integer columns: {rule}")
        for source in _source_paths(manifest, rule):
            relative_streaming = source.relative_to(streaming).as_posix()
            relative_game = f"{data_dir_name}/StreamingAssets/{relative_streaming}"
            source_files[relative_game] = sha256_file(source)
            snapshot = project / "originals" / Path(relative_game)
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, snapshot)
            with source.open("r", encoding=rule.get("encoding", "utf-8-sig"), newline="") as handle:
                rows = list(csv.reader(handle, delimiter=rule.get("delimiter", ",")))
            start = 1 if rule.get("header", False) else 0
            for row_index in range(start, len(rows)):
                for column in columns:
                    if column >= len(rows[row_index]):
                        raise ValueError(f"Column {column} missing at {relative_game}:{row_index + 1}")
                    text = rows[row_index][column]
                    if not text.strip():
                        continue
                    entry_id = f"{relative_game}:{row_index + 1}:{column}"
                    if entry_id in seen:
                        raise ValueError(f"Duplicate extracted ID: {entry_id}")
                    seen.add(entry_id)
                    entries.append({
                        "id": entry_id,
                        "source_file": relative_game,
                        "asset_type": "StreamingAssetsCSV",
                        "object_identifier": f"{row_index + 1}:{column}",
                        "field": f"cell[{row_index + 1}][{column}]",
                        "original_text": text,
                        "translated_text": "",
                        "original_hash": sha256_text(text),
                        "status": "untranslated",
                        "metadata": {
                            "row": row_index + 1,
                            "column": column,
                            "encoding": rule.get("encoding", "utf-8-sig"),
                            "delimiter": rule.get("delimiter", ","),
                        },
                    })
    manifest["source_files"] = source_files
    manifest["extracted_at"] = _now()
    ir = {"schema_version": 1, "extractor": manifest["extractor"], "entries": entries}
    write_json_atomic(project / "manifest.json", manifest)
    write_json_atomic(project / "translation.json", ir)
    _log(project, "EXTRACT", f"Extracted {len(entries)} strings from {len(source_files)} files")
    return entries


def export_csv(project_path: str | Path, csv_path: str | Path) -> Path:
    project, _ = _project(project_path)
    ir = read_json(project / "translation.json")
    target = Path(csv_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for entry in ir["entries"]:
            writer.writerow({
                "id": entry["id"],
                "original": entry["original_text"],
                "translation": entry["translated_text"],
                "intentionally_empty": "true" if entry["status"] == "intentionally_empty" else "false",
            })
    _log(project, "CSV", f"Exported {len(ir['entries'])} rows to {target}")
    return target


def import_csv(project_path: str | Path, csv_path: str | Path) -> dict:
    project, _ = _project(project_path)
    ir = read_json(project / "translation.json")
    expected = {entry["id"]: entry for entry in ir["entries"]}
    imported: dict[str, dict] = {}
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CSV_FIELDS:
            raise ValueError(f"CSV header must be exactly: {','.join(CSV_FIELDS)}")
        for row in reader:
            entry_id = row["id"]
            if entry_id in imported:
                raise ValueError(f"Duplicate CSV ID: {entry_id}")
            if entry_id not in expected:
                raise ValueError(f"Unknown CSV ID: {entry_id}")
            if row["original"] != expected[entry_id]["original_text"]:
                raise ValueError(f"Original text changed for ID: {entry_id}")
            marker = row["intentionally_empty"].strip().lower()
            if marker not in {"true", "false"}:
                raise ValueError(f"Invalid intentionally_empty value for ID: {entry_id}")
            imported[entry_id] = row
    missing = sorted(set(expected) - set(imported))
    if missing:
        raise ValueError(f"Missing CSV IDs: {', '.join(missing[:5])}")

    counts = {"imported": 0, "pending": 0, "intentionally_empty": 0}
    for entry_id, entry in expected.items():
        row = imported[entry_id]
        translation = row["translation"]
        intentional = row["intentionally_empty"].strip().lower() == "true"
        if intentional:
            if translation:
                raise ValueError(f"Intentionally empty row contains translation: {entry_id}")
            entry["translated_text"] = ""
            entry["status"] = "intentionally_empty"
            counts["intentionally_empty"] += 1
        elif translation:
            entry["translated_text"] = translation
            entry["status"] = "translated"
            counts["imported"] += 1
        else:
            entry["translated_text"] = ""
            entry["status"] = "untranslated"
            counts["pending"] += 1
    write_json_atomic(project / "translation.json", ir)
    _log(project, "CSV", f"Imported {counts['imported']} translations; {counts['pending']} pending")
    return counts


def validate(project_path: str | Path) -> dict:
    project, manifest = _project(project_path)
    ir = read_json(project / "translation.json")
    issues: list[dict] = []
    for entry in ir["entries"]:
        if sha256_text(entry["original_text"]) != entry["original_hash"]:
            issues.append({"severity": "error", "code": "original_hash_mismatch", "entry_id": entry["id"]})
        for issue in validate_pair(entry):
            issues.append({**issue, "entry_id": entry["id"]})
    for relative, expected_hash in manifest["source_files"].items():
        live = Path(manifest["game_path"]) / Path(relative)
        if not live.is_file() or sha256_file(live) != expected_hash:
            issues.append({"severity": "error", "code": "source_file_changed", "source_file": relative})
    report = {
        "checked": len(ir["entries"]),
        "errors": sum(issue["severity"] == "error" for issue in issues),
        "warnings": sum(issue["severity"] == "warning" for issue in issues),
        "pending": sum(entry["status"] == "untranslated" for entry in ir["entries"]),
        "issues": issues,
    }
    _log(project, "VALIDATE", f"{report['errors']} errors, {report['warnings']} warnings, {report['pending']} pending")
    return report


def inject(project_path: str | Path) -> Path:
    project, manifest = _project(project_path)
    report = validate(project)
    if report["errors"]:
        raise ValueError(f"Injection blocked by {report['errors']} validation error(s)")
    ir = read_json(project / "translation.json")
    stamp = _stamp()
    backup = project / "backups" / stamp
    shutil.copytree(project / "originals", backup / "originals")
    write_json_atomic(backup / "manifest.json", {"created_at": _now(), "source_files": manifest["source_files"]})
    _log(project, "BACKUP", f"Created {backup}")

    staging = project / "builds" / f".{stamp}.staging"
    final = project / "builds" / stamp / "game"
    try:
        shutil.copytree(Path(manifest["game_path"]), staging)
        grouped: dict[str, list[dict]] = {}
        for entry in ir["entries"]:
            if entry["status"] in {"translated", "intentionally_empty"}:
                grouped.setdefault(entry["source_file"], []).append(entry)
        for relative, entries in grouped.items():
            path = staging / Path(relative)
            metadata = entries[0]["metadata"]
            with path.open("r", encoding=metadata["encoding"], newline="") as handle:
                rows = [list(row) for row in csv.reader(handle, delimiter=metadata["delimiter"])]
            for entry in entries:
                row = entry["metadata"]["row"] - 1
                column = entry["metadata"]["column"]
                if rows[row][column] != entry["original_text"]:
                    raise ValueError(f"Staging original mismatch for ID: {entry['id']}")
                rows[row][column] = entry["translated_text"]
            temporary = path.with_suffix(path.suffix + ".tmp")
            with temporary.open("w", encoding=metadata["encoding"], newline="") as handle:
                csv.writer(handle, delimiter=metadata["delimiter"]).writerows(rows)
            temporary.replace(path)
            with path.open("r", encoding=metadata["encoding"], newline="") as handle:
                verified = list(csv.reader(handle, delimiter=metadata["delimiter"]))
            for entry in entries:
                actual = verified[entry["metadata"]["row"] - 1][entry["metadata"]["column"]]
                if actual != entry["translated_text"]:
                    raise RuntimeError(f"Post-injection verification failed: {entry['id']}")
        final.parent.mkdir(parents=True, exist_ok=False)
        staging.replace(final)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(final.parent, ignore_errors=True)
        raise
    _log(project, "INJECT", f"Injected {sum(len(v) for v in grouped.values())} strings into {final}")
    _log(project, "VERIFY", "Completed cell-level verification")
    return final
