$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    $Python = "python"
}

$env:PYTHONUTF8 = "1"
& $Python (Join-Path $PSScriptRoot "build_official_snippet_index.py")
