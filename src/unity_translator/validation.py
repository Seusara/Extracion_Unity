from __future__ import annotations

import re
from collections import Counter

_PLACEHOLDER = re.compile(r"\{[^{}]+\}|%(?:\d+\$)?[sdif]")
_TAG = re.compile(r"<\s*(/?)\s*([A-Za-z][\w-]*)(?:\s+[^<>]*?)?\s*(/?)>")
_REQUIRED_ESCAPES = (r"\n", r"\r", r"\t", r"\\")


def _tags(text: str) -> Counter[tuple[str, bool]]:
    result: Counter[tuple[str, bool]] = Counter()
    stack: list[str] = []
    for closing, name, self_closing in _TAG.findall(text):
        normalized = name.lower()
        is_void = bool(self_closing) or normalized in {"br", "sprite"}
        result[(normalized, bool(closing))] += 1
        if is_void:
            continue
        if closing:
            if not stack or stack.pop() != normalized:
                raise ValueError(f"broken closing tag: {name}")
        else:
            stack.append(normalized)
    if stack:
        raise ValueError("unclosed tags: " + ", ".join(stack))
    return result


def validate_pair(entry: dict) -> list[dict]:
    translation = entry["translated_text"]
    if entry["status"] == "untranslated":
        return []
    issues: list[dict] = []
    original = entry["original_text"]
    if Counter(_PLACEHOLDER.findall(original)) != Counter(_PLACEHOLDER.findall(translation)):
        issues.append({"severity": "error", "code": "placeholder_mismatch"})
    try:
        original_tags = _tags(original)
        translated_tags = _tags(translation)
        if original_tags != translated_tags:
            issues.append({"severity": "error", "code": "tag_mismatch"})
    except ValueError as error:
        issues.append({"severity": "error", "code": "broken_tags", "message": str(error)})
    for sequence in _REQUIRED_ESCAPES:
        if original.count(sequence) != translation.count(sequence):
            issues.append({"severity": "error", "code": "escape_mismatch", "sequence": sequence})
    if translation == original:
        issues.append({"severity": "warning", "code": "unchanged_translation"})
    if entry["status"] == "intentionally_empty":
        issues.append({"severity": "warning", "code": "intentionally_empty"})
    return issues
