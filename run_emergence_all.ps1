[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = "C:\Kageyoni" }

$env:PYTHONPATH = $ScriptDir
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$PythonScript = Join-Path $ScriptDir "run_emergence_all.py"

# Locate python executable
$PythonExe = "python"
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    $Potential = "C:\Users\flowe\AppData\Local\Programs\Python\Python313\python.exe"
    if (Test-Path $Potential) {
        $PythonExe = $Potential
    }
}

Write-Host "[LAUNCHING CONSTELLATION EMERGENCE: ALL-IN-ONE COMPLETE WORKFLOW]" -ForegroundColor Cyan
& $PythonExe $PythonScript
