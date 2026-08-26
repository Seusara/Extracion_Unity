from pathlib import Path

from unity_translator.naninovel import detect_naninovel


def test_naninovel_detection_uses_family_signatures_not_game_name(tmp_path: Path) -> None:
    data = tmp_path / "Arbitrary_Data"
    (data / "Managed").mkdir(parents=True)
    (data / "Managed" / "Elringus.Naninovel.Runtime.dll").write_bytes(b"")
    (data / "Managed" / "Naninovel.Common.dll").write_bytes(b"")
    (data / "StreamingAssets" / "aa" / "StandaloneWindows64" / "naninovel" / "scripts").mkdir(parents=True)
    (data / "StreamingAssets" / "aa" / "StandaloneWindows64" / "naninovel" / "scripts" / "scene.bundle").write_bytes(b"")

    result = detect_naninovel(tmp_path)

    assert result["family"] == "Naninovel"
    assert result["confidence"] > 0
    assert len(result["evidence"]) == 2


def test_naninovel_detection_has_no_false_positive_from_unrelated_bundle(tmp_path: Path) -> None:
    data = tmp_path / "Unrelated_Data"
    (data / "Managed").mkdir(parents=True)
    (data / "StreamingAssets" / "aa" / "StandaloneWindows64" / "scripts").mkdir(parents=True)
    (data / "StreamingAssets" / "aa" / "StandaloneWindows64" / "scripts" / "scene.bundle").write_bytes(b"")

    result = detect_naninovel(tmp_path)

    assert result["family"] is None
    assert result["confidence"] == 0.0