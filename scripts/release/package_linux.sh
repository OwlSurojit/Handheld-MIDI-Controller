#!/usr/bin/env bash
set -euo pipefail

VERSION="${APP_VERSION:-0.0.0-dev}"
VARIANT="${BUILD_VARIANT:-core}"
OUT_DIR="dist/linux-package"
SRC_DIR="dist/HandheldMIDI-${VARIANT}"
ARCHIVE="dist/HandheldMIDI-linux-${VARIANT}-${VERSION}.tar.gz"

rm -rf "${OUT_DIR}" "${ARCHIVE}"
mkdir -p "${OUT_DIR}"

cp -R "${SRC_DIR}" "${OUT_DIR}/HandheldMIDI"
cp scripts/release/linux-install.sh "${OUT_DIR}/install.sh"
chmod +x "${OUT_DIR}/install.sh"

cat > "${OUT_DIR}/README.txt" <<EOF
Handheld MIDI Controller Linux package
Variant: ${VARIANT}

Prerequisites:
- NetworkManager (nmcli) for Wi-Fi provisioning features

Install:
./install.sh

Run:
~/.local/opt/HandheldMIDI/HandheldMIDI
EOF

tar -czf "${ARCHIVE}" -C "${OUT_DIR}" .
