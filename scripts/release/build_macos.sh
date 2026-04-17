#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --upgrade pip
pip3 install -r requirements.txt
pip3 install pyinstaller

rm -rf dist build
pyinstaller --clean --noconfirm HandheldMIDI.spec
