# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("pyqtgraph.opengl") + ["OpenGL"]

a = Analysis(
    ["server/main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("server/config.yaml", "server"),
        ("server/app_settings.yaml", "server"),
        ("server/ui/img/yy_logo.jpg", "server/ui/img"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HandheldMIDI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="HandheldMIDI",
)
