$root = "F:\Joe_Coding"

$name = Read-Host "Project name"
$idea = Read-Host "Project idea"

$projectPath = Join-Path $root "projects\$name"

if (Test-Path $projectPath) {
    Write-Host "Project already exists!"
    exit
}

New-Item -ItemType Directory -Path $projectPath | Out-Null

Copy-Item (Join-Path $root "templates\PROJECT_TEMPLATE.md") (Join-Path $projectPath "PROJECT.md")
Copy-Item (Join-Path $root "templates\DEVLOG_TEMPLATE.md") (Join-Path $projectPath "DEVLOG.md")

Add-Content (Join-Path $projectPath "PROJECT.md") "`n## Idea`n$idea"

Set-Location $projectPath

Write-Host "Project created at $projectPath"
Write-Host "Starting Codex..."

git init

codex --full-auto

Read-Host "Press Enter to exit"