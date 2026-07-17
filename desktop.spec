# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


root = Path(SPECPATH)
datas = [
    (str(root / "app" / "static"), "app/static"),
    (str(root / "data" / "recruitment-talk-script-seed.md"), "data"),
    (str(root / "data" / "recruitment-safety-seed.md"), "data"),
    (str(root / "data" / "models" / "fastembed"), "data/models/fastembed"),
    (str(root / "assets" / "app-icon.png"), "assets"),
]
binaries = []
hiddenimports = []

for package in ("DrissionPage", "fastembed", "lancedb", "openai", "uvicorn", "webview"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports

analysis = Analysis(
    [str(root / "desktop.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="RecruitingAssistant",
    icon=str(root / "assets" / "app-icon.ico"),
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
)

bundle = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RecruitingAssistant",
)
