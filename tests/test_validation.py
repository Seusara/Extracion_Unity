from unity_translator.validation import validate_pair


def _entry(original: str, translated: str) -> dict:
    return {
        "id": "x",
        "original_text": original,
        "translated_text": translated,
        "status": "translated",
    }


def test_missing_placeholder_is_blocking() -> None:
    issues = validate_pair(_entry("Hello {playerName}, score %d", "Hola, puntuación"))
    assert "placeholder_mismatch" in {issue["code"] for issue in issues}


def test_modified_rich_text_attribute_is_detected() -> None:
    issues = validate_pair(_entry("<color=#fff>Hello</color>", "<color=#000>Hola</color>"))
    assert "tag_attribute_mismatch" in {issue["code"] for issue in issues}


def test_broken_tag_nesting_is_detected() -> None:
    issues = validate_pair(_entry("<b><i>Hello</i></b>", "<b><i>Hola</b></i>"))
    assert "broken_tags" in {issue["code"] for issue in issues}


def test_required_escape_sequence_is_preserved() -> None:
    issues = validate_pair(_entry(r"Line one\nLine two", "Línea uno Línea dos"))
    assert "escape_mismatch" in {issue["code"] for issue in issues}
