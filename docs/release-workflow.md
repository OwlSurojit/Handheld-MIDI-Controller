# Release Workflow

This repository uses a tag-driven GitHub Actions workflow at `.github/workflows/release-installers.yml`.

## What it produces

- Windows: Inno Setup installer (`.exe`)
- macOS: DMG package (`.dmg`)
- Linux: tar.gz package with installer script (`.tar.gz`)

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
scripts/release/package_macos.sh
```

### Linux

```bash
chmod +x scripts/release/build_linux.sh scripts/release/package_linux.sh scripts/release/linux-install.sh
scripts/release/build_linux.sh
scripts/release/package_linux.sh
```

## Runtime dependency notes

- Linux Wi-Fi provisioning requires `nmcli` (NetworkManager).
- Windows virtual MIDI loopback still requires a loopback endpoint provider. The app now falls back to the first available MIDI out port if the preferred name is unavailable.

## Future improvements

- Add code signing for Windows installer.
- Add macOS signing and notarization.
- Replace Linux tar.gz with AppImage or distro-specific package(s) if needed.
