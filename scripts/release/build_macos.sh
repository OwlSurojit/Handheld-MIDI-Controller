#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --upgrade pip
pip3 install -r requirements-core.txt
pip3 install -r requirements-mac.txt
pip3 install pyinstaller

rm -rf dist build
pyinstaller --clean --noconfirm HandheldMIDI-core.spec

pip3 install -r requirements-visualiser.txt
pyinstaller --clean --noconfirm HandheldMIDI-visualiser.spec
