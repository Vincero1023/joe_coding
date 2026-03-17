# ================================
# 새 프로젝트 생성 스크립트 (최적화 버전)
# ================================

param (
    [string]$ProjectName = "benchmark_tool"
)

# 프로젝트 생성
Write-Host "Creating project: $ProjectName"

New-Item -ItemType Directory -Path $ProjectName -Force | Out-Null

Set-Location $ProjectName

# 기본 폴더 구조
New-Item -ItemType Directory -Path "core" -Force | Out-Null
New-Item -ItemType Directory -Path "analyzer" -Force | Out-Null
New-Item -ItemType Directory -Path "input" -Force | Out-Null
New-Item -ItemType Directory -Path "output" -Force | Out-Null

# 기본 파일 생성
New-Item -ItemType File -Path "main.py" -Force | Out-Null
New-Item -ItemType File -Path "PROJECT_GUIDE.md" -Force | Out-Null

# 기본 가이드 작성 (핵심만)
@"
benchmark_tool 프로젝트

목표:
HTML → site_analysis.json 생성

핵심 기능:
- HTML 분석
- UI 구조 추출
- 기능 추론

현재 상태:
v1 개발 중
"@ | Set-Content "PROJECT_GUIDE.md"

Write-Host "Project structure created successfully!"
Write-Host "Run Codex manually using: cx"