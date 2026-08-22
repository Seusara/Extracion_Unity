from __future__ import annotations


class ManualProvider:
    """Apply text supplied by a human; performs no translation or network call."""

    name = "manual"

    def apply(self, entry: dict, text: str, *, intentionally_empty: bool = False) -> None:
        if intentionally_empty:
            if text:
                raise ValueError("Intentionally empty translation must not contain text")
            entry["translated_text"] = ""
            entry["status"] = "intentionally_empty"
        elif text:
            entry["translated_text"] = text
            entry["status"] = "translated"
        else:
            entry["translated_text"] = ""
            entry["status"] = "untranslated"
