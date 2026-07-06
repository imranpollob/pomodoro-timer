# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/pomodoro.py'],
    pathex=[],
    binaries=[],
    datas=[('src/stopwatch.ico', '.'), ('src/stopwatch.png', '.'), ('src/stopwatch.icns', '.'), ('src/complete.oga', '.')],
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

import sys
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
            'CFBundleVersion': '0.1.1',
            'CFBundleShortVersionString': '0.1.1',
            'NSHighResolutionCapable': True,
        }
    )
