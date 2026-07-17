$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Project environment is missing. Run setup.ps1 first."
}

& $python -m PyInstaller --noconfirm --clean desktop.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$app = Join-Path $PSScriptRoot "dist\RecruitingAssistant\RecruitingAssistant.exe"
if (-not (Test-Path -LiteralPath $app)) {
    throw "Desktop executable was not produced."
}

$compiler = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
    "C:\Program Files\Inno Setup 7\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if ($compiler) {
    & $compiler "installer.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Installer build failed."
    }
} else {
    Write-Warning "Inno Setup 6 is not installed; the onedir desktop app is ready."
}

Write-Output $app
