#!/usr/bin/env bash
set -euo pipefail

VERSION="${APP_VERSION:-0.0.0-dev}"
APPDIR="dist/AppDir"
APPIMAGE_TOOL="tools/appimagetool-x86_64.AppImage"
OUTPUT="dist/HandheldMIDI-linux-${VERSION}.AppImage"

rm -rf "${APPDIR}" "${OUTPUT}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications" "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

cp -R dist/HandheldMIDI/* "${APPDIR}/usr/bin/"

cat > "${APPDIR}/usr/share/icons/hicolor/256x256/apps/handheld-midi.png.base64" <<'EOF'
iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9yJ0QdQAAAAASUVORK5CYII=
EOF
base64 -d "${APPDIR}/usr/share/icons/hicolor/256x256/apps/handheld-midi.png.base64" > "${APPDIR}/usr/share/icons/hicolor/256x256/apps/handheld-midi.png"
rm "${APPDIR}/usr/share/icons/hicolor/256x256/apps/handheld-midi.png.base64"

cat > "${APPDIR}/AppRun" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
HERE="$(dirname "$(readlink -f "$0")")"
exec "${HERE}/usr/bin/HandheldMIDI" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

cat > "${APPDIR}/handheld-midi.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Handheld MIDI Controller
Exec=HandheldMIDI
Icon=handheld-midi
Categories=AudioVideo;Audio;Midi;
Terminal=false
EOF

cp "${APPDIR}/handheld-midi.desktop" "${APPDIR}/usr/share/applications/handheld-midi.desktop"

# AppImage tooling expects icon and desktop entry at AppDir root.
ln -sf "usr/share/icons/hicolor/256x256/apps/handheld-midi.png" "${APPDIR}/handheld-midi.png"

ARCH=x86_64 "${APPIMAGE_TOOL}" --appimage-extract-and-run "${APPDIR}" "${OUTPUT}"
chmod +x "${OUTPUT}"
