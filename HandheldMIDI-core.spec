# -*- mode: python ; coding: utf-8 -*-

import os
import sys

APP_NAME = "HandheldMIDI"
APP_BUNDLE_NAME = "Handheld MIDI Controller Core.app"
APP_VERSION = os.getenv("APP_VERSION", "0.0.0-dev")
BUNDLE_IDENTIFIER = "com.handheldmidi.controller"

is_macos = sys.platform == "darwin"

a = Analysis(
    ["server/main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("server/config.yaml", "server"),
        ("server/app_settings.yaml", "server"),
        ("server/ui/img/yy_logo.jpg", "server/ui/img"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pyqtgraph", "OpenGL"],
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
    name="HandheldMIDI-core",
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
            "HandheldMIDIVariant": "core",
            "CFBundleExecutable": APP_NAME,
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "LSMinimumSystemVersion": "11.0",
        },
    )
