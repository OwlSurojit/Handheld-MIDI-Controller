# Release Workflow

This repository uses a tag-driven GitHub Actions workflow at `.github/workflows/release-installers.yml`.

## What it produces

- Windows: single Inno Setup installer (`.exe`) with optional Visualiser feature checkbox
- macOS: separate core and visualiser DMGs (`.dmg`)
- Linux: separate core and visualiser AppImages (`.AppImage`) and tar.gz packages (`.tar.gz`)

## Triggering a production build

1. Commit and push your changes.
2. Create and push a version tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

3. Wait for the `Release Installers` workflow to complete.
4. Download artifacts from the GitHub Release page.

## Local dry run commands

### Windows

```powershell
scripts/release/build_windows.ps1
```

### macOS

```bash
chmod +x scripts/release/build_macos.sh scripts/release/package_macos.sh
scripts/release/build_macos.sh
BUILD_VARIANT=core scripts/release/package_macos.sh
BUILD_VARIANT=visualiser scripts/release/package_macos.sh
```

### Linux

```bash
chmod +x scripts/release/build_linux.sh scripts/release/package_linux.sh scripts/release/package_appimage.sh scripts/release/linux-install.sh
scripts/release/build_linux.sh
BUILD_VARIANT=core scripts/release/package_linux.sh
BUILD_VARIANT=visualiser scripts/release/package_linux.sh
BUILD_VARIANT=core scripts/release/package_appimage.sh
BUILD_VARIANT=visualiser scripts/release/package_appimage.sh
```

## Runtime dependency notes

- Linux Wi-Fi provisioning requires `nmcli` (NetworkManager).
- Windows virtual MIDI loopback still requires a loopback endpoint provider. The app now falls back to the first available MIDI out port if the preferred name is unavailable.

## macOS without paid Apple account

You can ship a working macOS build without a paid Apple Developer account, but you cannot notarize it. That means users will still see Gatekeeper warnings on first launch.

- The release script now performs ad-hoc signing by default (`codesign -s -`) if `codesign` is available.
- To disable signing entirely, set `MACOS_SIGN_APP=0` when running `scripts/release/package_macos.sh`.
- To use a specific local identity, set `MACOS_SIGN_IDENTITY="<identity>"`.
- The package step also generates `dist/RELEASE_NOTES-macos-<variant>-<version>.txt` and includes it in the DMG.

Recommended launch instructions for users (unsigned/not-notarized app):

1. Open the DMG and drag the app to `Applications`.
2. In Finder, right-click the app and choose `Open`.
3. Confirm the prompt with `Open`.

If the app is still blocked, users can run:

```bash
xattr -dr com.apple.quarantine "/Applications/Handheld MIDI Controller.app"
```

Notes:

- Notarization and seamless double-click launch require an Apple Developer account.
- There is no legitimate way to fully bypass Gatekeeper for unknown third-party apps on end-user machines.

## Future improvements

- Add code signing for Windows installer.
- Add macOS signing and notarization.
- Add distro-specific Linux packages (`.deb`/`.rpm`) if needed.
