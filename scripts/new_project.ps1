$root = "F:\joe_coding"

$name = Read-Host "Project name"
$desc = Read-Host "Project description"

$projectPath = Join-Path $root "projects\$name"

if (Test-Path $projectPath) {
    Write-Host "Project already exists"
    exit
}

# 프로젝트 폴더 생성
New-Item -ItemType Directory -Path $projectPath | Out-Null
New-Item -ItemType Directory -Path "$projectPath\src" | Out-Null
New-Item -ItemType Directory -Path "$projectPath\tests" | Out-Null

# README 생성
$readme = @"
# $name

$desc

## Development
src : main code  
tests : test code
"@

$readme | Out-File "$projectPath\README.md"

# PROJECT 템플릿 복사
Copy-Item "$root\templates\PROJECT_TEMPLATE.md" "$projectPath\PROJECT.md"

# DEVLOG 템플릿 복사
Copy-Item "$root\templates\DEVLOG_TEMPLATE.md" "$projectPath\DEVLOG.md"

# requirements 생성
New-Item "$projectPath\requirements.txt" -ItemType File | Out-Null

# git commit
Set-Location $root

git add .
git commit -m "create project $name"

# 프로젝트 폴더 이동
Set-Location $projectPath

Write-Host ""
Write-Host "Project created:"
Write-Host $projectPath
Write-Host ""

# codex 실행
codex --full-auto