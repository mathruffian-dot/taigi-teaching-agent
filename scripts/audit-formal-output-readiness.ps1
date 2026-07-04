param(
    [string]$Config = "config.json",

    [switch]$LiveNetwork,

    [switch]$AttemptTtsSample
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    $Python = "python"
}

$argsList = @(
    (Join-Path $PSScriptRoot "audit_formal_output_readiness.py"),
    "--config",
    $Config
)

if ($LiveNetwork) {
    $argsList += "--live-network"
}

if ($AttemptTtsSample) {
    $argsList += "--attempt-tts-sample"
}

& $Python @argsList
