#!/usr/bin/env bash
set -e

PKG_NAME="pomodoro-timer_amd64"

echo "==> Building binary with PyInstaller..."
uv run pyinstaller --clean pomodoro.spec

echo "==> Assembling package structure..."
rm -rf deb_workspace
mkdir -p deb_workspace/DEBIAN
mkdir -p deb_workspace/usr/bin
mkdir -p deb_workspace/usr/share/applications

cp dist/pomodoro                              deb_workspace/usr/bin/
cp linux_packaging/pomodoro.desktop          deb_workspace/usr/share/applications/
cp linux_packaging/control                   deb_workspace/DEBIAN/

echo "==> Building .deb package..."
dpkg-deb --build deb_workspace "${PKG_NAME}.deb"

echo ""
echo "Done! Package created: ${PKG_NAME}.deb"
echo "Install with: sudo dpkg -i ${PKG_NAME}.deb"
