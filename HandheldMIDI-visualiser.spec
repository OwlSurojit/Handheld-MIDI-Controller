# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_submodules

APP_NAME = "HandheldMIDI"
APP_BUNDLE_NAME = "Handheld MIDI Controller Visualiser.app"
APP_VERSION = os.getenv("APP_VERSION", "0.0.0-dev")
BUNDLE_IDENTIFIER = "com.handheldmidi.controller"

is_macos = sys.platform == "darwin"
is_windows = sys.platform.startswith("win")
is_linux = sys.platform.startswith("linux")

hiddenimports = [
    "server.ui.dialogs.visualiser_window",
    "OpenGL",
] + collect_submodules("pyqtgraph.opengl")

datas = [
    ("server/config.yaml", "server"),
    ("server/app_settings.yaml", "server"),
    ("server/ui/img/yy_logo.jpg", "server/ui/img"),
]

binaries = []

excludes = []

# Add platform-specific adjustments here if needed.
# Example:
# if is_windows:
#     hiddenimports += ["some_windows_only_module"]
#     datas += [("path/to/windows/file", "dest")]
#
# if is_linux:
#     hiddenimports += ["some_linux_only_module"]
#
# if is_macos:
#     hiddenimports += ["some_macos_only_module"]
#     binaries += [("path/to/libsomething.dylib", ".")]

a = Analysis(
    ["server/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
    name="HandheldMIDI-visualiser",
)

if is_macos:
    app = BUNDLE(
        coll,
        name=APP_BUNDLE_NAME,
        icon=None,  # set to path to .icns if you have one
        bundle_identifier=BUNDLE_IDENTIFIER,
        info_plist={
            "CFBundleName": "Handheld MIDI Controller",
            "CFBundleDisplayName": "Handheld MIDI Controller",
            "HandheldMIDIVariant": "visualiser",
            "CFBundleExecutable": APP_NAME,
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "LSMinimumSystemVersion": "11.0",
        },
    )