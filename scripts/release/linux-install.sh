#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${HOME}/.local/opt/HandheldMIDI"
BIN_DIR="${HOME}/.local/bin"

mkdir -p "${INSTALL_ROOT}" "${BIN_DIR}"
cp -R HandheldMIDI/* "${INSTALL_ROOT}/"

cat > "${BIN_DIR}/handheld-midi" <<'EOF'
#!/usr/bin/env bash
exec "${HOME}/.local/opt/HandheldMIDI/HandheldMIDI" "$@"
EOF

chmod +x "${BIN_DIR}/handheld-midi"

echo "Installed to ${INSTALL_ROOT}"
echo "Launcher created at ${BIN_DIR}/handheld-midi"
if command -v nmcli >/dev/null 2>&1; then
  echo "nmcli detected"
else
  echo "Warning: nmcli not found. Install NetworkManager to use Wi-Fi provisioning."
fi
