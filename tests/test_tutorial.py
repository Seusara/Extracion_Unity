from pathlib import Path

from unity_translator.ui import ASSET_DIR, TUTORIAL_STEPS, load_tutorial_preference, save_tutorial_preference


def test_tutorial_is_brief_and_covers_the_complete_workflow() -> None:
    assert len(TUTORIAL_STEPS) == 4
    content = " ".join(f"{step['title']} {step['body']}" for step in TUTORIAL_STEPS).casefold()

    for concept in ("juego", "extra", "csv", "valid", "inyect", "copia"):
        assert concept in content


def test_tutorial_uses_packaged_gameplay_examples() -> None:
    images = [step["image"] for step in TUTORIAL_STEPS if step.get("image")]

    assert len(images) >= 2
    assert all((ASSET_DIR / image).is_file() for image in images)


def test_tutorial_preference_defaults_to_visible_and_can_be_disabled(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"

    assert load_tutorial_preference(settings) is True

    save_tutorial_preference(settings, False)

    assert load_tutorial_preference(settings) is False
