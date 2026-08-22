from unity_translator.ui import filter_entries


def test_filter_entries_matches_text_and_status() -> None:
    entries = [
        {"id": "one", "original_text": "Start Game", "translated_text": "Iniciar", "status": "translated"},
        {"id": "two", "original_text": "Quit", "translated_text": "", "status": "untranslated"},
    ]

    assert [entry["id"] for entry in filter_entries(entries, "start", "all")] == ["one"]
    assert [entry["id"] for entry in filter_entries(entries, "", "untranslated")] == ["two"]
