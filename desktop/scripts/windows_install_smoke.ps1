param(
    [Parameter(Mandatory = $true)][string]$Installer,
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$installerFile = (Resolve-Path -LiteralPath $Installer).Path
$probeRoot = Join-Path $workspaceRoot ('build\windows-install-' + [guid]::NewGuid().ToString('N'))
$installDir = [IO.Path]::GetFullPath((Join-Path $probeRoot 'application'))
if (-not $installDir.StartsWith($workspaceRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Install target must remain inside this workspace.'
}
$registryPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'
$existing = Get-ItemProperty -Path "$registryPath\*" -ErrorAction SilentlyContinue | Where-Object DisplayName -eq 'Pomodoro'
if ($existing) { throw 'A beta installation already exists; refusing to replace or uninstall it.' }
New-Item -ItemType Directory -Path $probeRoot | Out-Null
$installed = $false
try {
    $setup = Start-Process -FilePath $installerFile -ArgumentList @('/S', "/D=$installDir") -WindowStyle Hidden -PassThru -Wait
    if ($setup.ExitCode -ne 0) { throw "Installer failed: $($setup.ExitCode)" }
    $installed = $true
    $binary = Join-Path $installDir 'pomodoro-desktop-beta.exe'
    if (-not (Test-Path -LiteralPath $binary)) { throw 'Installed executable is missing.' }
    $registration = Get-ItemProperty -Path "$registryPath\*" -ErrorAction SilentlyContinue | Where-Object DisplayName -eq 'Pomodoro'
    if (-not $registration -or [IO.Path]::GetFullPath($registration.InstallLocation.Trim('"')).TrimEnd('\') -ne $installDir.TrimEnd('\')) {
        throw 'Installer registration does not match the verified test directory.'
    }
    & $Python (Join-Path $PSScriptRoot 'windows_ui_smoke.py') $binary (Join-Path $probeRoot 'uia-report.json')
    if ($LASTEXITCODE -ne 0) { throw 'Installed normal-build UI Automation smoke failed.' }
    Write-Output "Installed application checks passed; report: $probeRoot\uia-report.json"
}
finally {
    if ($installed) {
        $uninstaller = Get-ChildItem -LiteralPath $installDir -Filter '*uninstall*.exe' | Select-Object -First 1
        if (-not $uninstaller) { throw "Uninstaller missing; test install retained at $installDir" }
        # /S leaves the optional delete-app-data checkbox unchecked. Only this verified install is removed.
        $remove = Start-Process -FilePath $uninstaller.FullName -ArgumentList '/S' -WindowStyle Hidden -PassThru -Wait
        if ($remove.ExitCode -ne 0) { throw "Uninstaller failed: $($remove.ExitCode)" }
        # Normal NSIS uninstall relaunches from a temporary executable; wait for that child to finish.
        $deadline = [DateTime]::UtcNow.AddSeconds(20)
        while ((Test-Path -LiteralPath (Join-Path $installDir 'pomodoro-desktop-beta.exe')) -and [DateTime]::UtcNow -lt $deadline) {
            Start-Sleep -Milliseconds 200
        }
        if (Test-Path -LiteralPath (Join-Path $installDir 'pomodoro-desktop-beta.exe')) { throw 'Uninstall left the executable behind.' }
        $remaining = Get-ItemProperty -Path "$registryPath\*" -ErrorAction SilentlyContinue | Where-Object DisplayName -eq 'Pomodoro'
        if ($remaining) { throw 'Uninstall left the beta registration behind.' }
        Write-Output 'Current-user NSIS install/uninstall passed; application data was retained.'
    }
}
