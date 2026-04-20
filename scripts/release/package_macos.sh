#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Handheld MIDI Controller"
VARIANT="${BUILD_VARIANT:-core}"
APP_BUNDLE="dist/${APP_NAME}.app"
CONTENTS_DIR="${APP_BUNDLE}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"
VERSION="${APP_VERSION:-0.0.0-dev}"
SRC_DIR="dist/HandheldMIDI-${VARIANT}"
DMG_PATH="dist/HandheldMIDI-macos-${VARIANT}-${VERSION}.dmg"
DMG_STAGING_DIR="dist/dmg-staging-${VARIANT}-${VERSION}"
RELEASE_NOTES_PATH="dist/RELEASE_NOTES-macos-${VARIANT}-${VERSION}.txt"
SIGN_APP="${MACOS_SIGN_APP:-1}"
SIGNING_IDENTITY="${MACOS_SIGN_IDENTITY:--}"

rm -rf "${APP_BUNDLE}" "${DMG_PATH}" "${DMG_STAGING_DIR}" "${RELEASE_NOTES_PATH}"
mkdir -p "${MACOS_DIR}" "${RESOURCES_DIR}"

cp -R "${SRC_DIR}"/* "${MACOS_DIR}/"

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
  <key>HandheldMIDIVariant</key><string>${VARIANT}</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict>
</plist>
EOF

chmod +x "${MACOS_DIR}/HandheldMIDI"

if [[ "${SIGN_APP}" == "1" ]]; then
  if command -v codesign >/dev/null 2>&1; then
    echo "Signing app bundle with identity: ${SIGNING_IDENTITY}"
    codesign --force --deep --timestamp=none --sign "${SIGNING_IDENTITY}" "${APP_BUNDLE}"
    codesign --verify --deep --strict --verbose=2 "${APP_BUNDLE}"
  else
    echo "Warning: codesign not found, creating unsigned app bundle"
  fi
fi

# Clear inherited quarantine metadata before DMG creation.
if command -v xattr >/dev/null 2>&1; then
  xattr -cr "${APP_BUNDLE}" || true
fi

cat > "${RELEASE_NOTES_PATH}" <<EOF
Handheld MIDI Controller - macOS Install Notes

Variant: ${VARIANT}
Version: ${VERSION}

Because this build is not notarized, macOS may block first launch.

Install and launch:
1. Open the DMG.
2. Drag ${APP_NAME}.app to Applications.
3. In Finder, right-click the app and choose Open.
4. Confirm by clicking Open in the warning dialog.

If macOS still blocks launch, run:
xattr -dr com.apple.quarantine "/Applications/${APP_NAME}.app"
EOF

mkdir -p "${DMG_STAGING_DIR}"
cp -R "${APP_BUNDLE}" "${DMG_STAGING_DIR}/"
cp "${RELEASE_NOTES_PATH}" "${DMG_STAGING_DIR}/"

hdiutil create -volname "${APP_NAME} (${VARIANT})" -srcfolder "${DMG_STAGING_DIR}" -ov -format UDZO "${DMG_PATH}"
