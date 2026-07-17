$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    & "D:\python\python.exe" -m venv .venv
}

& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
if (-not $env:HTTPS_PROXY -and (Test-NetConnection 127.0.0.1 -Port 7890 -InformationLevel Quiet)) {
    $env:HTTP_PROXY = "http://127.0.0.1:7890"
    $env:HTTPS_PROXY = "http://127.0.0.1:7890"
}
& $python scripts\setup_semantic_search.py

Write-Host "安装完成，运行 .\run.ps1 启动系统。"
