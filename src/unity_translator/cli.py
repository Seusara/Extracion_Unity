from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

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

    init_cmd = commands.add_parser("init")
    init_cmd.add_argument("game")
    init_cmd.add_argument("project")
    init_cmd.add_argument("--profile", required=True)

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
        if args.command == "init":
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
