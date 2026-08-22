from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPEC).resolve().parent
unitypy_datas, unitypy_binaries, unitypy_hiddenimports = collect_all("UnityPy")

analysis = Analysis(
    [str(ROOT / "packaging" / "unity_translator_gui.py")],
    pathex=[str(ROOT / "src")],
    binaries=unitypy_binaries,
    datas=unitypy_datas
    + [(str(ROOT / "src" / "unity_translator" / "assets"), "unity_translator/assets")],
    hiddenimports=unitypy_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="UnityTranslator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(ROOT / "src" / "unity_translator" / "assets" / "app-icon.ico")],
    version=str(ROOT / "packaging" / "version_info.txt"),
)
