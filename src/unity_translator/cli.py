from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .analyzer import detect_profile
from .diagnostic_package import generate_diagnostic_package
from .pipeline import analyze, create_project, export_csv, extract, import_csv, inject, restore, validate


def _print_analysis(result: dict) -> None:
    print("Unity game detected" if result["is_unity"] else "Unity game not detected")
    print(f"Unity: {result.get('unity_version', 'unknown')}")
    print(f"Runtime: {result.get('runtime', 'unknown')}")
    print(f"Compatibility: {result.get('compatibility_level', 'investigation').upper()}")
    if result.get("reason") and not result["is_unity"]:
        print(f"Reason: {result['reason']}")
    print("\nCandidates:")
    for index, candidate in enumerate(result.get("candidates", []), start=1):
        print(f"\n{index}. {candidate['adapter_id']} (v{candidate['adapter_version']})")
        print(f"   Confidence: {candidate['confidence']:.2f}")
        print("   Evidence:")
        for item in candidate["evidence"]:
            print(f"   - {item}")
        print("   Limitations:")
        for item in candidate["limitations"]:
            print(f"   - {item}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="unity-translator")
    commands = parser.add_subparsers(dest="command", required=True)

    analyze_cmd = commands.add_parser("analyze")
    analyze_cmd.add_argument("game")
    analyze_cmd.add_argument("--json", action="store_true")

    diagnose_cmd = commands.add_parser("diagnose", help="Generate a sanitized investigation package")
    diagnose_cmd.add_argument("game")
    diagnose_cmd.add_argument("--output", help="Output directory for AI_CONTEXT and AI_CONTEXT.zip")
    diagnose_cmd.add_argument("--max-depth", type=int, default=5)
    diagnose_cmd.add_argument("--max-files", type=int, default=500)

    init_cmd = commands.add_parser("init")
    init_cmd.add_argument("game")
    init_cmd.add_argument("project")
    profile_source = init_cmd.add_mutually_exclusive_group(required=True)
    profile_source.add_argument("--profile", help="Path to a profile JSON file")
    profile_source.add_argument(
        "--auto", action="store_true",
        help="Auto-detect a zero-config profile (e.g. naninovel-addressables) instead of --profile",
    )

    extract_cmd = commands.add_parser("extract")
    extract_cmd.add_argument("project")

    export_cmd = commands.add_parser("export")
    export_cmd.add_argument("project")
    export_cmd.add_argument("csv")

    import_cmd = commands.add_parser("import")
    import_cmd.add_argument("project")
    import_cmd.add_argument("csv")

    validate_cmd = commands.add_parser("validate")
    validate_cmd.add_argument("project")
    validate_cmd.add_argument("--json", action="store_true")

    inject_cmd = commands.add_parser("inject")
    inject_cmd.add_argument("project")

    restore_cmd = commands.add_parser("restore")
    restore_cmd.add_argument("project")
    restore_cmd.add_argument("backup")
    restore_cmd.add_argument("destination")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "analyze":
            result = analyze(args.game)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                _print_analysis(result)
            return 0 if result["is_unity"] else 1
        if args.command == "diagnose":
            package = generate_diagnostic_package(
                args.game,
                args.output,
                max_depth=args.max_depth,
                max_files=args.max_files,
            )
            result = json.loads((package.directory / "game_profile.json").read_text(encoding="utf-8"))
            print("Analysis complete.")
            print(f"Compatibility: {result.get('compatibility_level', 'investigation').upper()}")
            print(f"Diagnostic package: {package.zip_path}")
            print("Contains: game profile, candidates, signatures, directory structure, logs, adapter API, expected tests")
            print("Original game assets included: NO")
            return 0
        if args.command == "init":
            if args.auto:
                profile = detect_profile(Path(args.game))
                if profile is None:
                    print("ERROR: No auto-detected profile is available for this game; use --profile instead", file=sys.stderr)
                    return 2
            else:
                profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
            create_project(args.game, args.project, profile)
            print(f"[PROJECT] Created {Path(args.project).resolve()}")
        elif args.command == "extract":
            entries = extract(args.project)
            print(f"[EXTRACT] {len(entries)} strings")
        elif args.command == "export":
            target = export_csv(args.project, args.csv)
            print(f"[CSV] Exported to {target}")
        elif args.command == "import":
            result = import_csv(args.project, args.csv)
            print(f"[CSV] Imported {result['imported']}; pending {result['pending']}; intentionally empty {result['intentionally_empty']}")
        elif args.command == "validate":
            result = validate(args.project)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"[VALIDATE] {result['errors']} errors, {result['warnings']} warnings, {result['pending']} pending")
                for issue in result["issues"]:
                    print(f"  {issue['severity'].upper()} {issue['code']}: {issue.get('entry_id', issue.get('source_file', ''))}")
            return 2 if result["errors"] else 0
        elif args.command == "inject":
            build = inject(args.project)
            print(f"[INJECT] Build generated at {build}")
        elif args.command == "restore":
            restored = restore(args.project, args.backup, args.destination)
            print(f"[RESTORE] Restored {restored} files")
        return 0
    except (OSError, ValueError, KeyError, csv.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
