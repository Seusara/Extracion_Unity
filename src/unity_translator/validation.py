from __future__ import annotations

import re
from collections import Counter

_PLACEHOLDER = re.compile(r"\{[^{}]+\}|%(?:\d+\$)?[sdif]")
_TAG = re.compile(r"<\s*(/?)\s*([A-Za-z][\w-]*)([^<>]*?)(/?)>")
_REQUIRED_ESCAPES = (r"\n", r"\r", r"\t", r"\\")


def _tags(text: str) -> tuple[Counter[tuple[str, bool]], Counter[tuple[str, str]]]:
    structure: Counter[tuple[str, bool]] = Counter()
    attributes: Counter[tuple[str, str]] = Counter()
    stack: list[str] = []
    for closing, name, raw_attributes, self_closing in _TAG.findall(text):
        normalized = name.lower()
        is_closing = bool(closing)
        is_void = bool(self_closing) or normalized in {"br", "sprite"}
        structure[(normalized, is_closing)] += 1
        if not is_closing:
            attributes[(normalized, " ".join(raw_attributes.split()))] += 1
        if is_void:
            continue
        if is_closing:
            if not stack or stack.pop() != normalized:
                raise ValueError(f"broken closing tag: {name}")
        else:
            stack.append(normalized)
    if stack:
        raise ValueError("unclosed tags: " + ", ".join(stack))
    return structure, attributes


def validate_pair(entry: dict) -> list[dict]:
    translation = entry["translated_text"]
    if entry["status"] == "untranslated":
        return []
    issues: list[dict] = []
    original = entry["original_text"]
    if Counter(_PLACEHOLDER.findall(original)) != Counter(_PLACEHOLDER.findall(translation)):
        issues.append({"severity": "error", "code": "placeholder_mismatch"})
    try:
        original_structure, original_attributes = _tags(original)
        translated_structure, translated_attributes = _tags(translation)
        if original_structure != translated_structure:
            issues.append({"severity": "error", "code": "tag_mismatch"})
        elif original_attributes != translated_attributes:
            issues.append({"severity": "error", "code": "tag_attribute_mismatch"})
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
