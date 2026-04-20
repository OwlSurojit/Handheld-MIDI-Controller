$ErrorActionPreference = 'Stop'

python -m pip install --upgrade pip
pip install -r requirements-core.txt
pip install pyinstaller

if (Test-Path dist) { Remove-Item -Recurse -Force dist }
if (Test-Path build) { Remove-Item -Recurse -Force build }

pyinstaller --clean --noconfirm HandheldMIDI-core.spec

pip install -r requirements-visualiser.txt
pyinstaller --clean --noconfirm HandheldMIDI-visualiser.spec
