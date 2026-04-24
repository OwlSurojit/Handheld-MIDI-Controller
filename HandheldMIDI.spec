# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_submodules

APP_NAME = "HandheldMIDI"
APP_BUNDLE_NAME = "Handheld MIDI Controller.app"
APP_VERSION = os.getenv("APP_VERSION", "0.0.0-dev")
BUNDLE_IDENTIFIER = "com.handheldmidi.controller"

is_macos = sys.platform == "darwin"

hiddenimports = [
    "server.ui.dialogs.visualiser_window",
    "OpenGL",
] + collect_submodules("pyqtgraph.opengl")

datas = [
    ("server/config.yaml", "server"),
    ("server/app_settings.yaml", "server"),
    ("server/ui/img/yy_logo.png", "server/ui/img"),
]

a = Analysis(
    ["server/main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
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
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)

if is_macos:
    app = BUNDLE(
        coll,
        name=APP_BUNDLE_NAME,
        icon=None,
        bundle_identifier=BUNDLE_IDENTIFIER,
        info_plist={
            "CFBundleName": "Handheld MIDI Controller",
            "CFBundleDisplayName": "Handheld MIDI Controller",
            "CFBundleExecutable": APP_NAME,
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "LSMinimumSystemVersion": "11.0",
        },
    )