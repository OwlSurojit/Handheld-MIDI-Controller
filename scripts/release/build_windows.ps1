$ErrorActionPreference = 'Stop'

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

if (Test-Path dist) { Remove-Item -Recurse -Force dist }
if (Test-Path build) { Remove-Item -Recurse -Force build }

python -m PyInstaller --clean --noconfirm HandheldMIDI.spec
