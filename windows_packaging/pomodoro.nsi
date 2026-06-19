; Pomodoro Timer - NSIS Installer Script
; Requires NSIS: https://nsis.sourceforge.io/Download

!include "MUI2.nsh"

; ── App metadata ──────────────────────────────────────────────
Name "Pomodoro Timer"
OutFile "..\dist\pomodoro-timer-setup.exe"
InstallDir "$LOCALAPPDATA\Pomodoro Timer"
InstallDirRegKey HKCU "Software\Pomodoro Timer" "InstallDir"
RequestExecutionLevel user

!define APP_NAME      "Pomodoro Timer"
!define APP_EXE       "pomodoro.exe"
!define APP_VERSION   "0.1.0"
!define APP_PUBLISHER "Imran Pollob"
!define APP_WEBURL    "https://github.com/imranpollob/pomodoro-timer"

; ── Interface ─────────────────────────────────────────────────
!define MUI_ICON "..\src\stopwatch.ico"
!define MUI_UNICON "..\src\stopwatch.ico"
!define MUI_ABORTWARNING

; ── Pages ─────────────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; ── Languages ─────────────────────────────────────────────────
!insertmacro MUI_LANGUAGE "English"

; ── Installer sections ────────────────────────────────────────
Section "Install"
    SetOutPath "$INSTDIR"

    File "..\dist\pomodoro.exe"
    File /nonfatal "..\src\stopwatch.ico"
    File /nonfatal "..\src\stopwatch.png"
    File /nonfatal "..\src\complete.oga"

    ; Write registry keys for Add/Remove Programs
    WriteRegStr HKCU "Software\Pomodoro Timer" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Pomodoro Timer" \
        "DisplayName" "${APP_NAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Pomodoro Timer" \
        "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Pomodoro Timer" \
        "DisplayIcon" '"$INSTDIR\${APP_EXE}"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Pomodoro Timer" \
        "Publisher" "${APP_PUBLISHER}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Pomodoro Timer" \
        "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Pomodoro Timer" \
        "URLInfoAbout" "${APP_WEBURL}"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Pomodoro Timer" \
        "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Pomodoro Timer" \
        "NoRepair" 1

    ; Create uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"

    ; Create Start Menu shortcut
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk" "$INSTDIR\uninstall.exe"

    ; Create desktop shortcut
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
SectionEnd

; ── Uninstaller section ───────────────────────────────────────
Section "Uninstall"
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\stopwatch.ico"
    Delete "$INSTDIR\stopwatch.png"
    Delete "$INSTDIR\complete.oga"
    Delete "$INSTDIR\uninstall.exe"
    RMDir "$INSTDIR"

    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"

    Delete "$DESKTOP\${APP_NAME}.lnk"

    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Pomodoro Timer"
    DeleteRegKey HKCU "Software\Pomodoro Timer"
SectionEnd
