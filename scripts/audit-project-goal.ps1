param(
    [string]$GenerationOutput = "output/smoke_full_goal_all_outputs",
    [string]$Json = "docs/project-goal-audit.json",
    [string]$Markdown = "docs/project-goal-audit.md"
)

$ErrorActionPreference = "Stop"

$python = ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

& $python scripts/audit_project_goal.py `
    --generation-output $GenerationOutput `
    --json $Json `
    --markdown $Markdown
