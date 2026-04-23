#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

"${PYTHON_BIN}" -m pip install --upgrade pip
"${PYTHON_BIN}" -m pip install -r requirements.txt
"${PYTHON_BIN}" -m pip install -r requirements-mac.txt
"${PYTHON_BIN}" -m pip install pyinstaller

rm -rf dist build
"${PYTHON_BIN}" -m PyInstaller --clean --noconfirm HandheldMIDI.spec
