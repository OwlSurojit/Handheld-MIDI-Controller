#!/usr/bin/env bash
set -euo pipefail

VERSION="${APP_VERSION:-0.0.0-dev}"
APP_BUNDLE_NAME="Handheld MIDI Controller.app"
DMG_PATH="dist/HandheldMIDI-macos-${VERSION}.dmg"
DMG_STAGING_DIR="dist/dmg-staging-${VERSION}"
RELEASE_NOTES_PATH="dist/RELEASE_NOTES-macos-${VERSION}.txt"
SIGN_APP="${MACOS_SIGN_APP:-1}"
SIGNING_IDENTITY="${MACOS_SIGN_IDENTITY:--}"

SOURCE_APP_BUNDLE="dist/${APP_BUNDLE_NAME}"

if [[ ! -d "${SOURCE_APP_BUNDLE}" ]]; then
  echo "Expected app bundle not found: ${SOURCE_APP_BUNDLE}"
  echo "Run scripts/release/build_macos.sh first."
  exit 1
fi

rm -rf "${DMG_PATH}" "${DMG_STAGING_DIR}" "${RELEASE_NOTES_PATH}"
mkdir -p "${DMG_STAGING_DIR}"
cp -R "${SOURCE_APP_BUNDLE}" "${DMG_STAGING_DIR}/"

APP_BUNDLE="${DMG_STAGING_DIR}/${APP_BUNDLE_NAME}"

APP_DISPLAY_NAME="${APP_BUNDLE_NAME%.app}"

if [[ "${SIGN_APP}" == "1" ]]; then
  if command -v codesign >/dev/null 2>&1; then
    echo "Signing app bundle with identity: ${SIGNING_IDENTITY}"

    # Sign only actual Mach-O code objects first. Using --deep here can fail on
    # non-code files that exist inside PyInstaller bundles (e.g. *.dist-info).
    while IFS= read -r -d '' candidate; do
      if file "${candidate}" | grep -q "Mach-O"; then
        codesign --force --timestamp=none --sign "${SIGNING_IDENTITY}" "${candidate}"
      fi
    done < <(find "${APP_BUNDLE}/Contents" -type f -print0)

    # Finally sign the outer app bundle.
    codesign --force --timestamp=none --sign "${SIGNING_IDENTITY}" "${APP_BUNDLE}"
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

Version: ${VERSION}

Because this build is not notarized, macOS may block first launch.
Unfortunately, we cannot notarize the app without a paid Apple Developer account.
Since we don't have the funds for that, we have to ask you to jump through some hoops to get the app running on macOS.

Install and launch:
1. Open the DMG.
2. Drag ${APP_BUNDLE_NAME} to Applications.
3. In Finder, right-click the app and choose Open.
4. Confirm by clicking Open in the warning dialog.
5. If you see a warning like 'Apple could not verify "Handheld MIDI Controller" is free of malware...':
  a. Click OK to dismiss the warning.
  b. Open System Settings and go to Security & Privacy.
  c. Scroll down to "Security", where you should see a message about "Handheld MIDI Controller" being blocked.
  d. Click the "Open Anyway" button next to that message.
  e. Confirm by clicking Open in the next dialog.
  f. You might need to wait a while until the app launches, as macOS performs additional checks.
6. If macOS still blocks launch, run:
xattr -dr com.apple.quarantine "/Applications/${APP_BUNDLE_NAME}"
EOF

cp "${RELEASE_NOTES_PATH}" "${DMG_STAGING_DIR}/"

hdiutil create -volname "${APP_DISPLAY_NAME}" -srcfolder "${DMG_STAGING_DIR}" -ov -format UDZO "${DMG_PATH}"
