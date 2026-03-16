@echo off

set /p NAME=새 프로젝트 이름 입력:

mkdir "%NAME%"
cd "%NAME%"

copy "..\AI_CONTEXT_TEMPLATE.md" "AI_CONTEXT.md"
copy "..\TASK_TEMPLATE.md" "TASK.md"
copy "..\DEVLOG_TEMPLATE.md" "DEVLOG.md"
copy "..\AI_RULES_TEMPLATE.md" "AI_RULES.md"

echo.
echo 프로젝트 생성 완료: %NAME%
echo 이제 VS Code로 이 폴더를 열고 codex 실행하세요.
pause