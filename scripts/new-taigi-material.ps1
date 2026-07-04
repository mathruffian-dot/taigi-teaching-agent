param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Request,

    [string]$Config = "config.json",

    [string]$Output = "",

    [switch]$Video,

    [switch]$NoVideo,

    [switch]$NoMedia,

    [switch]$NoValidate
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    $Python = "python"
}

$env:PYTHONPATH = Join-Path $ProjectRoot "src"

$argsList = @(
    "-m",
    "agent.natural_language_runner",
    $Request,
    "--config",
    $Config
)

if ($Output) {
    $argsList += @("--output", $Output)
}
if ($Video) {
    $argsList += "--video"
}
if ($NoVideo) {
    $argsList += "--no-video"
}
if ($NoMedia) {
    $argsList += "--no-media"
}
if ($NoValidate) {
    $argsList += "--no-validate"
}

& $Python @argsList
