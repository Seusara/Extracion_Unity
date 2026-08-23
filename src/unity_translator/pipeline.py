from __future__ import annotations

import csv
import json
import shutil
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import UnityPy

from .analyzer import analyze_game
from .holyknight import extract as extract_holyknight
from .holyknight import inject_file as inject_holyknight_file
from .providers.manual import ManualProvider
from .storage import read_json, sha256_file, sha256_text, write_json_atomic
from .unity_json import apply_translations, extract_json_entries
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
    extractor = profile.get("extractor")
    if extractor == "streamingassets-csv":
        if not isinstance(profile.get("files"), list) or not profile["files"]:
            raise ValueError("Profile must declare at least one file rule")
    elif extractor == "unity-textasset-json":
        required = ("asset_file", "list_key", "id_field", "text_field", "textasset")
        missing = [field for field in required if field not in profile]
        if missing:
            raise ValueError(f"Unity JSON profile missing fields: {', '.join(missing)}")
    elif extractor == "holyknight-encrypted-tsv":
        if not isinstance(profile.get("source_root"), str) or not profile["source_root"]:
            raise ValueError("Holy Knight profile must declare source_root")
    else:
        raise ValueError("Supported extractors: streamingassets-csv, unity-textasset-json, holyknight-encrypted-tsv")
    for folder in ("originals", "translations", "builds", "backups", "logs"):
        (project / folder).mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "tool_version": TOOL_VERSION,
        "created_at": _now(),
        "game_path": str(game),
        "analysis": analysis,
        "extractor": {"name": extractor, "version": 1, "support": "experimental"},
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


def _find_text_asset(env, selector: dict):
    matches = []
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        if "path_id" in selector and obj.path_id != selector["path_id"]:
            continue
        data = obj.read()
        if "name" in selector and getattr(data, "m_Name", "") != selector["name"]:
            continue
        matches.append((obj, data))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one TextAsset, found {len(matches)} for {selector}")
    return matches[0]


def _resolve_asset_file(data_dir: Path, configured_asset_file: str) -> Path:
    """Resolve a profile asset path while tolerating Unity subfolders.

    Unity builds can place the same-named asset under ``il2cpp_data`` or
    another data subdirectory. The explicit profile path remains preferred;
    basename fallback is allowed only when it identifies one file.
    """
    configured = data_dir / configured_asset_file
    if configured.is_file():
        return configured

    basename = Path(configured_asset_file).name
    candidates = sorted(path for path in data_dir.rglob(basename) if path.is_file())
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        listed = ", ".join(str(path.relative_to(data_dir)) for path in candidates)
        raise FileNotFoundError(
            f"Profile asset_file '{configured_asset_file}' matched multiple Unity asset files: {listed}. "
            "Specify the relative path in the profile."
        )

    asset_candidates = sorted(
        str(path.relative_to(data_dir))
        for path in data_dir.rglob("*")
        if path.is_file() and (path.suffix.lower() in {".assets", ".bundle"} or "sharedassets" in path.name.lower())
    )
    hint = f" Available Unity assets: {', '.join(asset_candidates[:20])}." if asset_candidates else ""
    raise FileNotFoundError(
        f"Unity asset file not found: {configured}. Check the profile asset_file and the game's *_Data folder.{hint}"
    )


def _close_unity_environment(env) -> None:
    """Release UnityPy file handles so Windows can replace the source asset."""
    for asset_file in env.files.values():
        stream = getattr(getattr(asset_file, "reader", None), "stream", None)
        if stream is not None and hasattr(stream, "close"):
            stream.close()


def _extract_streaming_csv(project: Path, manifest: dict) -> tuple[list[dict], dict[str, str]]:
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
    return entries, source_files


def _extract_unity_json(project: Path, manifest: dict) -> tuple[list[dict], dict[str, str]]:
    profile = manifest["profile"]
    data_dir = Path(manifest["analysis"]["data_dir"])
    source = _resolve_asset_file(data_dir, profile["asset_file"])
    relative_asset = source.relative_to(data_dir).as_posix()
    relative_game = f"{manifest['analysis']['data_dir_name']}/{relative_asset}"
    snapshot = project / "originals" / Path(relative_game)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, snapshot)
    env = UnityPy.load(str(source))
    obj, data = _find_text_asset(env, profile["textasset"])
    script = data.m_Script.decode("utf-8-sig") if isinstance(data.m_Script, bytes) else data.m_Script
    document = json.loads(script)
    entries = extract_json_entries(
        document,
        source_file=relative_game,
        path_id=obj.path_id,
        list_key=profile["list_key"],
        id_field=profile["id_field"],
        text_field=profile["text_field"],
    )
    _close_unity_environment(env)
    return entries, {relative_game: sha256_file(source)}


def extract(project_path: str | Path) -> list[dict]:
    project, manifest = _project(project_path)
    if manifest["extractor"]["name"] == "streamingassets-csv":
        entries, source_files = _extract_streaming_csv(project, manifest)
    elif manifest["extractor"]["name"] == "unity-textasset-json":
        entries, source_files = _extract_unity_json(project, manifest)
    elif manifest["extractor"]["name"] == "holyknight-encrypted-tsv":
        entries, source_files = extract_holyknight(project, manifest)
    else:
        raise ValueError(f"Unsupported project extractor: {manifest['extractor']['name']}")
    manifest["source_files"] = source_files
    manifest["extracted_at"] = _now()
    ir = {"schema_version": 1, "extractor": manifest["extractor"], "entries": entries}
    write_json_atomic(project / "manifest.json", manifest)
    write_json_atomic(project / "translation.json", ir)
    _log(project, "EXTRACT", f"Extracted {len(entries)} strings from {len(source_files)} files")
    return entries


def update_translation(
    project_path: str | Path,
    entry_id: str,
    text: str,
    *,
    intentionally_empty: bool = False,
) -> dict:
    project, _manifest = _project(project_path)
    ir_path = project / "translation.json"
    ir = read_json(ir_path)
    matches = [entry for entry in ir["entries"] if entry["id"] == entry_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one Translation IR entry for ID {entry_id!r}, found {len(matches)}")
    entry = matches[0]
    ManualProvider().apply(entry, text, intentionally_empty=intentionally_empty)
    write_json_atomic(ir_path, ir)
    _log(project, "EDITOR", f"Updated {entry_id}")
    return deepcopy(entry)


def list_entries(project_path: str | Path) -> list[dict]:
    project, _manifest = _project(project_path)
    ir = read_json(project / "translation.json")
    return deepcopy(ir["entries"])


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
    provider = ManualProvider()
    for entry_id, entry in expected.items():
        row = imported[entry_id]
        translation = row["translation"]
        intentional = row["intentionally_empty"].strip().lower() == "true"
        provider.apply(entry, translation, intentionally_empty=intentional)
        if entry["status"] == "translated":
            counts["imported"] += 1
        elif entry["status"] == "intentionally_empty":
            counts["intentionally_empty"] += 1
        else:
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
    entries_by_id = {entry["id"]: entry for entry in ir["entries"]}
    detailed_issues = []
    for issue in issues:
        detail = dict(issue)
        entry = entries_by_id.get(issue.get("entry_id"))
        if entry:
            detail.update({
                "source_file": entry.get("source_file"),
                "original_text": entry.get("original_text"),
                "translated_text": entry.get("translated_text"),
                "status": entry.get("status"),
            })
        detailed_issues.append(detail)
    report = {
        "checked": len(ir["entries"]),
        "errors": sum(issue["severity"] == "error" for issue in detailed_issues),
        "warnings": sum(issue["severity"] == "warning" for issue in detailed_issues),
        "pending": sum(entry["status"] == "untranslated" for entry in ir["entries"]),
        "issues": detailed_issues,
    }
    report["report_json"] = str(project / "logs" / "validation-report.json")
    report["report_csv"] = str(project / "logs" / "validation-report.csv")
    write_json_atomic(Path(report["report_json"]), report)
    with Path(report["report_csv"]).open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["severity", "code", "entry_id", "source_file", "status", "message", "sequence", "original_text", "translated_text"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(detailed_issues)
    _log(project, "VALIDATE", f"{report['errors']} errors, {report['warnings']} warnings, {report['pending']} pending")
    _log(project, "VALIDATE", f"Detailed reports: {report['report_json']} and {report['report_csv']}")
    return report


def auto_fix_validation(project_path: str | Path) -> dict:
    """Apply only non-destructive validation fixes and re-run validation."""
    project, _manifest = _project(project_path)
    ir = read_json(project / "translation.json")
    fixed = 0
    for entry in ir["entries"]:
        if entry["status"] == "translated" and entry["translated_text"] == entry["original_text"]:
            entry["translated_text"] = ""
            entry["status"] = "untranslated"
            fixed += 1
    write_json_atomic(project / "translation.json", ir)
    _log(project, "VALIDATE", f"Automatically reset {fixed} unchanged translations to pending")
    report = validate(project)
    report["auto_fixed"] = fixed
    return report


def _inject_csv_file(path: Path, entries: list[dict]) -> None:
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


def _inject_unity_json_file(path: Path, entries: list[dict], profile: dict) -> None:
    env = UnityPy.load(str(path))
    before_count = len(list(env.objects))
    _obj, data = _find_text_asset(env, profile["textasset"])
    script = data.m_Script.decode("utf-8-sig") if isinstance(data.m_Script, bytes) else data.m_Script
    expected = json.loads(script)
    changed = apply_translations(expected, entries)
    if changed != len(entries):
        raise RuntimeError(f"Expected {len(entries)} JSON changes, applied {changed}")
    data.m_Script = json.dumps(expected, ensure_ascii=False, separators=(",", ":"))
    data.save()
    with tempfile.TemporaryDirectory() as output_dir:
        env.save(pack="none", out_path=output_dir)
        generated = Path(output_dir) / path.name
        if not generated.is_file():
            raise RuntimeError(f"UnityPy did not generate expected file: {generated}")
        _close_unity_environment(env)
        shutil.move(str(generated), str(path))

    check = UnityPy.load(str(path))
    if len(list(check.objects)) != before_count:
        raise RuntimeError("Unity object count changed during injection")
    _verified_obj, verified_data = _find_text_asset(check, profile["textasset"])
    verified_script = (
        verified_data.m_Script.decode("utf-8-sig")
        if isinstance(verified_data.m_Script, bytes)
        else verified_data.m_Script
    )
    if json.loads(verified_script) != expected:
        raise RuntimeError("Post-injection JSON verification failed")
    _close_unity_environment(check)


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
            if entries[0]["asset_type"] == "StreamingAssetsCSV":
                _inject_csv_file(path, entries)
            elif entries[0]["asset_type"] == "TextAssetJSON":
                _inject_unity_json_file(path, entries, manifest["profile"])
            elif entries[0]["asset_type"] == "HolyKnightEncryptedTSV":
                inject_holyknight_file(path, entries)
            else:
                raise ValueError(f"Unsupported asset type: {entries[0]['asset_type']}")
        final.parent.mkdir(parents=True, exist_ok=False)
        shutil.move(str(staging), str(final))
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(final.parent, ignore_errors=True)
        raise
    _log(project, "INJECT", f"Injected {sum(len(v) for v in grouped.values())} strings into {final}")
    _log(project, "VERIFY", "Completed cell-level verification")
    return final


def latest_build(project_path: str | Path) -> Path:
    project, _ = _project(project_path)
    builds = sorted(
        (candidate / "game" for candidate in (project / "builds").iterdir()),
        reverse=True,
    )
    for build in builds:
        if build.is_dir():
            return build
    raise FileNotFoundError("No generated builds are available")


def launchable_executable(project_path: str | Path) -> Path:
    build = latest_build(project_path)
    candidates = [
        executable
        for executable in build.glob("*.exe")
        if not executable.name.casefold().startswith("unitycrashhandler")
        and (build / f"{executable.stem}_Data").is_dir()
    ]
    if len(candidates) != 1:
        raise ValueError(f"Expected one Unity game executable, found {len(candidates)}")
    return candidates[0]


def restore(project_path: str | Path, backup_name: str, destination: str | Path) -> int:
    project, _ = _project(project_path)
    backups_root = (project / "backups").resolve()
    backup = (backups_root / backup_name).resolve()
    if backup.parent != backups_root or not backup.is_dir():
        raise ValueError(f"Backup not found: {backup_name}")
    backup_manifest = read_json(backup / "manifest.json")
    destination_path = Path(destination).resolve()
    if not destination_path.is_dir():
        raise FileNotFoundError(f"Restore destination not found: {destination_path}")

    restored = 0
    for relative, expected_hash in backup_manifest["source_files"].items():
        source = backup / "originals" / Path(relative)
        if not source.is_file() or sha256_file(source) != expected_hash:
            raise ValueError(f"Backup hash mismatch: {relative}")
        target = destination_path / Path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".restore.tmp")
        shutil.copy2(source, temporary)
        temporary.replace(target)
        restored += 1
    _log(project, "RESTORE", f"Restored {restored} files from {backup_name} into {destination_path}")
    return restored


def restore_latest_build(project_path: str | Path) -> tuple[int, Path]:
    project, _ = _project(project_path)
    build = latest_build(project)
    backup_name = build.parent.name
    restored = restore(project, backup_name, build)
    return restored, build
