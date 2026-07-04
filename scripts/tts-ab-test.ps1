param(
    [string]$Engines = "",
    [string]$Output = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    $Python = "python"
}

$env:PYTHONUTF8 = "1"
$ScriptArgs = @()
if ($Engines) { $ScriptArgs += @("--engines", $Engines) }
if ($Output)  { $ScriptArgs += @("--output", $Output) }
if ($Force)   { $ScriptArgs += "--force" }

& $Python (Join-Path $PSScriptRoot "tts_ab_test.py") @ScriptArgs
