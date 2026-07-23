#!/usr/bin/env bash
set -euo pipefail

PKG_NAME="pomodoro-timer_amd64"
APP_VERSION=$(uv run python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')

echo "==> Checking Linux GUI build dependencies..."
uv run python -c 'import tkinter; print(f"Tk {tkinter.TkVersion} is available")' || {
    echo "ERROR: Python's tkinter module is unavailable." >&2
    echo "Install it before building (on Ubuntu/Debian: sudo apt-get install python3-tk)." >&2
    exit 1
}

echo "==> Building binary with PyInstaller..."
uv run pyinstaller --clean --noconfirm pomodoro.spec

echo "==> Verifying that Tkinter was bundled..."
ARCHIVE_CONTENTS=$(uv run pyi-archive_viewer -l dist/pomodoro)
if [[ "${ARCHIVE_CONTENTS}" != *"_tkinter"* ]]; then
    echo "ERROR: PyInstaller produced an executable without Tkinter support." >&2
    exit 1
fi

echo "==> Assembling package structure..."
rm -rf deb_workspace
mkdir -p deb_workspace/DEBIAN
mkdir -p deb_workspace/usr/bin
mkdir -p deb_workspace/usr/share/applications
mkdir -p deb_workspace/usr/share/icons/hicolor/48x48/apps

cp dist/pomodoro                              deb_workspace/usr/bin/
cp linux_packaging/pomodoro.desktop          deb_workspace/usr/share/applications/
sed "s/@VERSION@/${APP_VERSION}/g" linux_packaging/control.in > deb_workspace/DEBIAN/control
cp linux_packaging/icons/pomodoro.png        deb_workspace/usr/share/icons/hicolor/48x48/apps/pomodoro.png

echo "==> Building .deb package..."
dpkg-deb --build deb_workspace "${PKG_NAME}.deb"

echo ""
echo "Done! Package created: ${PKG_NAME}.deb"
echo "Install with: sudo dpkg -i ${PKG_NAME}.deb"
