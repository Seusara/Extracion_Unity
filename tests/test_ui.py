from unity_translator.ui import format_analysis, format_validation


def test_format_analysis_reports_detected_runtime_and_sources() -> None:
    message = format_analysis(
        {
            "is_unity": True,
            "unity_version": "2022.3.26f1",
            "runtime": "mono",
            "streaming_assets": False,
            "asset_files": ["resources.assets", "sharedassets0.assets"],
            "compatibility": "experimental",
        }
    )

    assert "Unity 2022.3.26f1 detected" in message
    assert "Runtime: mono" in message
    assert "Assets: 2" in message
    assert "Compatibility: experimental" in message


def test_format_validation_surfaces_errors_warnings_and_pending() -> None:
    message = format_validation({"checked": 12, "errors": 1, "warnings": 2, "pending": 9})

    assert message == "Checked: 12 | Errors: 1 | Warnings: 2 | Pending: 9"
