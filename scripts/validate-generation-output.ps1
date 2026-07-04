param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$OutputDir
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    $Python = "python"
}

$env:PYTHONUTF8 = "1"
& $Python (Join-Path $PSScriptRoot "validate_generation_output.py") $OutputDir
