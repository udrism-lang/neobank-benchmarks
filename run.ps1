# Runs the benchmarks and tests from PowerShell. Usage: .\run.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv")) {
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe run.py
Invoke-Item .\output
