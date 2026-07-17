$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "项目环境尚未安装，请先运行 .\setup.ps1"
}

& $python -m uvicorn "app.main:create_app" --factory --host 127.0.0.1 --port 8765
