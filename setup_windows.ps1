$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11 or 3.12 is required. Install Python first."
}

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .

Write-Host ""
Write-Host "Dependencies installed." -ForegroundColor Green
Write-Host "Create the first administrator now:" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m flask --app wsgi create-admin

Write-Host ""
Write-Host "Done. Start with: .\\start_windows.ps1" -ForegroundColor Green
