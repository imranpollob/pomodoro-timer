#!/usr/bin/env bash
set -e

PKG_NAME="pomodoro-timer_amd64"
APP_VERSION=$(uv run python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')

echo "==> Building binary with PyInstaller..."
uv run pyinstaller --clean pomodoro.spec

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
