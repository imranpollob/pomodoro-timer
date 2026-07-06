# -*- mode: python ; coding: utf-8 -*-

import sys
import tomllib


def get_project_version():
    with open("pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["version"]


project_version = get_project_version()


a = Analysis(
    ['src/pomodoro.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/stopwatch.ico', '.'),
        ('src/stopwatch.png', '.'),
        ('src/stopwatch.icns', '.'),
        ('src/complete.oga', '.'),
        ('pyproject.toml', '.'),
    ],
    hiddenimports=['PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='pomodoro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/stopwatch.ico',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='Pomodoro.app',
        icon='src/stopwatch.icns',
        bundle_identifier='com.imranpollob.pomodoro-timer',
        info_plist={
            'CFBundleName': 'Pomodoro',
            'CFBundleDisplayName': 'Pomodoro',
            'CFBundleIdentifier': 'com.imranpollob.pomodoro-timer',
            'CFBundleVersion': project_version,
            'CFBundleShortVersionString': project_version,
            'NSHighResolutionCapable': True,
        }
    )
