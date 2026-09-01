from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import UnityPy

from .naninovel import TEXT_FIELDS, NaninovelParser, _close_environment

_MIN_TEXT_LENGTH = 3


def _looks_like_text(value: Any) -> str | None:
    """Heuristic filter for engine noise: fonts, shader/animation IDs, GUIDs."""
    if isinstance(value, dict) and isinstance(value.get("value"), str):
        value = value["value"]
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if len(candidate) < _MIN_TEXT_LENGTH or " " not in candidate:
        return None
    return candidate


def audit_command_coverage(game_root: str | Path) -> dict[str, int]:
    """Report Naninovel command fields that look like text but have no ``TEXT_FIELDS`` rule.

    This does not extend extraction by itself; it only surfaces evidence for a
    human to review before deciding whether ``TEXT_FIELDS`` needs a new entry.
    """
    parser = NaninovelParser(game_root)
    covered_fields = {fullname: set(fields) for fullname, (fields, _category) in TEXT_FIELDS.items()}
    findings: Counter[str] = Counter()
    script_root = parser.data_dir / "StreamingAssets" / "aa"
    bundles = sorted(script_root.glob("StandaloneWindows64/**/*.bundle"))
    for bundle_path in bundles:
        environment = None
        try:
            environment = UnityPy.load(str(bundle_path))
            for obj in environment.objects:
                if obj.type.name != "MonoBehaviour":
                    continue
                _script_name, entries = parser._parse_script(obj)
                for fullname, parsed in entries:
                    if not parsed:
                        continue
                    already_covered = covered_fields.get(fullname, set())
                    for field, value in parsed.items():
                        if field in already_covered:
                            continue
                        if _looks_like_text(value) is not None:
                            findings[f"{fullname}.{field}"] += 1
        except Exception:
            # One unreadable/custom bundle must not hide other candidates.
            continue
        finally:
            if environment is not None:
                _close_environment(environment)
    return dict(findings)
