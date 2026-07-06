@echo off
setlocal

for /f "usebackq delims=" %%V in (`uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"`) do set "APP_VERSION=%%V"
if not defined APP_VERSION (
    echo ERROR: Could not read project version from pyproject.toml.
    exit /b 1
)

echo ==> Building executable with PyInstaller...
uv run pyinstaller --clean --noconfirm pomodoro.spec
if %ERRORLEVEL% neq 0 (
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

echo ==> Building Windows installer with NSIS...
set "MAKENSIS="
where makensis >nul 2>&1 && set "MAKENSIS=makensis"
if not defined MAKENSIS if exist "C:\Program Files (x86)\NSIS\makensis.exe" set "MAKENSIS=C:\Program Files (x86)\NSIS\makensis.exe"
if not defined MAKENSIS if exist "C:\Program Files\NSIS\makensis.exe" set "MAKENSIS=C:\Program Files\NSIS\makensis.exe"
if not defined MAKENSIS (
    echo ERROR: NSIS not found. Install it from https://nsis.sourceforge.io/Download
    echo        Make sure "makensis" is in your PATH.
    exit /b 1
)

"%MAKENSIS%" /DAPP_VERSION=%APP_VERSION% windows_packaging\pomodoro.nsi
if %ERRORLEVEL% neq 0 (
    echo ERROR: NSIS build failed.
    exit /b 1
)

echo.
echo Done! Installer created: dist\pomodoro-timer-setup.exe
