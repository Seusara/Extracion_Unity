from unity_translator.providers.manual import ManualProvider


def test_manual_provider_sets_explicit_translation_without_external_services() -> None:
    entry = {"translated_text": "", "status": "untranslated"}
    ManualProvider().apply(entry, "Hola", intentionally_empty=False)
    assert entry == {"translated_text": "Hola", "status": "translated"}


def test_manual_provider_distinguishes_intentionally_empty() -> None:
    entry = {"translated_text": "old", "status": "translated"}
    ManualProvider().apply(entry, "", intentionally_empty=True)
    assert entry == {"translated_text": "", "status": "intentionally_empty"}
