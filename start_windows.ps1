$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Run .\\setup_windows.ps1 first."
}
& .\.venv\Scripts\python.exe -m flask --app wsgi run --host 127.0.0.1 --port 5000
