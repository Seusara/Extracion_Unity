from unity_translator.unity_json import apply_translations, extract_json_entries


def test_extract_json_entries_builds_stable_ir_locators() -> None:
    document = {"texts": [{"dataID": "Start", "ENG": "Start Game"}, {"dataID": "Quit", "ENG": "Quit"}]}
    entries = extract_json_entries(
        document,
        source_file="Game_Data/sharedassets0.assets",
        path_id=554,
        list_key="texts",
        id_field="dataID",
        text_field="ENG",
    )
    assert [entry["id"] for entry in entries] == [
        "Game_Data/sharedassets0.assets:554:ENG:Start",
        "Game_Data/sharedassets0.assets:554:ENG:Quit",
    ]
    assert entries[0]["metadata"]["item_index"] == 0


def test_apply_translations_changes_only_translated_items() -> None:
    document = {"texts": [{"dataID": "Start", "ENG": "Start Game"}, {"dataID": "Quit", "ENG": "Quit"}]}
    entries = extract_json_entries(
        document,
        source_file="Game_Data/sharedassets0.assets",
        path_id=554,
        list_key="texts",
        id_field="dataID",
        text_field="ENG",
    )
    entries[0]["translated_text"] = "Iniciar juego"
    entries[0]["status"] = "translated"

    changed = apply_translations(document, entries)

    assert changed == 1
    assert document == {"texts": [{"dataID": "Start", "ENG": "Iniciar juego"}, {"dataID": "Quit", "ENG": "Quit"}]}
