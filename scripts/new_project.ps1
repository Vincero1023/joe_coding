# ================================
# 새 프로젝트 생성 스크립트 (입력형 + 자동구조)
# ================================

# 루트 경로 자동 설정 (중요)
$root = Split-Path -Parent $PSScriptRoot

# 사용자 입력
$name = Read-Host "Project name"
$desc = Read-Host "Project description"

$projectPath = Join-Path $root "projects\$name"

# 중복 체크
if (Test-Path $projectPath) {
    Write-Host "Project already exists!"
    exit
}

# 프로젝트 폴더 생성
New-Item -ItemType Directory -Path $projectPath | Out-Null

# 기본 구조
New-Item -ItemType Directory -Path "$projectPath\src" | Out-Null
New-Item -ItemType Directory -Path "$projectPath\tests" | Out-Null

# README 생성
@"
# $name

$desc
"@ | Out-File "$projectPath\README.md" -Encoding UTF8

# 템플릿 복사
Copy-Item "$root\templates\PROJECT_TEMPLATE.md" "$projectPath\PROJECT.md"
Copy-Item "$root\templates\DEVLOG_TEMPLATE.md" "$projectPath\DEVLOG.md"

# requirements 생성
New-Item "$projectPath\requirements.txt" -ItemType File | Out-Null

# Git 커밋
Set-Location $root
git add .
git commit -m "create project $name"

# 프로젝트 폴더 이동
Set-Location $projectPath

Write-Host ""
Write-Host "Project created:"
Write-Host $projectPath
Write-Host ""

# Codex 실행
codex --full-auto --no-alt-screen