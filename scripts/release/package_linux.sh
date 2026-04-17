#!/usr/bin/env bash
set -euo pipefail

VERSION="${APP_VERSION:-0.0.0-dev}"
OUT_DIR="dist/linux-package"
ARCHIVE="dist/HandheldMIDI-linux-${VERSION}.tar.gz"

rm -rf "${OUT_DIR}" "${ARCHIVE}"
mkdir -p "${OUT_DIR}"

cp -R dist/HandheldMIDI "${OUT_DIR}/HandheldMIDI"
cp scripts/release/linux-install.sh "${OUT_DIR}/install.sh"
chmod +x "${OUT_DIR}/install.sh"

cat > "${OUT_DIR}/README.txt" <<EOF
Handheld MIDI Controller Linux package

Prerequisites:
- NetworkManager (nmcli) for Wi-Fi provisioning features

Install:
./install.sh

Run:
~/.local/opt/HandheldMIDI/HandheldMIDI
EOF

tar -czf "${ARCHIVE}" -C "${OUT_DIR}" .
