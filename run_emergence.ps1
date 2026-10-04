[CmdletBinding()]
param(
    [switch]$Full,
    [switch]$All,
    [switch]$Preview,
    [switch]$Compare,
    [switch]$Bank,
    [switch]$Lineage,
    [switch]$Map,
    [switch]$Runs,
    [string]$CustomArg = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = "C:\Kageyoni" }

$env:PYTHONPATH = $ScriptDir
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$CliScript = Join-Path $ScriptDir "constellation_emergence_cli.py"
$AllScript = Join-Path $ScriptDir "run_emergence_all.py"

# Locate python executable
$PythonExe = "python"
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    $Potential = "C:\Users\flowe\AppData\Local\Programs\Python\Python313\python.exe"
    if (Test-Path $Potential) {
        $PythonExe = $Potential
    }
}

if ($Full -or $All) {
    Write-Host "[LAUNCHING CONSTELLATION EMERGENCE: ALL-IN-ONE COMPLETE WORKFLOW]" -ForegroundColor Cyan
    & $PythonExe $AllScript
} elseif ($Preview) {
    & $PythonExe $CliScript --preview
} elseif ($Compare) {
    & $PythonExe $CliScript --compare
} elseif ($Bank) {
    & $PythonExe $CliScript --bank
} elseif ($Lineage) {
    & $PythonExe $CliScript --lineage
} elseif ($Map) {
    & $PythonExe $CliScript --map
} elseif ($Runs) {
    & $PythonExe $CliScript --runs
} elseif ($CustomArg) {
    & $PythonExe $CliScript $CustomArg
} else {
    Write-Host "[LAUNCHING CONSTELLATION EMERGENCE: 10-ROUND AUTOMATIC ENCOUNTER]" -ForegroundColor Cyan
    & $PythonExe $CliScript --run --auto
}
