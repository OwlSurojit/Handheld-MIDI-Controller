#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Handheld MIDI Controller"
APP_BUNDLE="dist/${APP_NAME}.app"
CONTENTS_DIR="${APP_BUNDLE}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"
VERSION="${APP_VERSION:-0.0.0-dev}"

rm -rf "${APP_BUNDLE}" "dist/HandheldMIDI-macos-${VERSION}.dmg"
mkdir -p "${MACOS_DIR}" "${RESOURCES_DIR}"

cp -R dist/HandheldMIDI/* "${MACOS_DIR}/"

cat > "${CONTENTS_DIR}/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key><string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key><string>com.handheldmidi.controller</string>
  <key>CFBundleVersion</key><string>${VERSION}</string>
  <key>CFBundleShortVersionString</key><string>${VERSION}</string>
  <key>CFBundleExecutable</key><string>HandheldMIDI</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict>
</plist>
EOF

chmod +x "${MACOS_DIR}/HandheldMIDI"

hdiutil create -volname "${APP_NAME}" -srcfolder "${APP_BUNDLE}" -ov -format UDZO "dist/HandheldMIDI-macos-${VERSION}.dmg"
