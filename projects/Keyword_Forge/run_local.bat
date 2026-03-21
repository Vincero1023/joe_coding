@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "INTERACTIVE=0"
set "APP_URL=http://127.0.0.1:8000"

call :resolve_python
if errorlevel 1 goto :end

if "%~1"=="" goto :run_api
if /I "%~1"=="menu" (
    set "INTERACTIVE=1"
    goto :menu
)
if /I "%~1"=="collector" goto :run_collector
if /I "%~1"=="expander" goto :run_expander
if /I "%~1"=="analyzer" goto :run_analyzer
if /I "%~1"=="selector" goto :run_selector
if /I "%~1"=="title" goto :run_title
if /I "%~1"=="all" goto :run_all
if /I "%~1"=="api" goto :run_api

echo 알 수 없는 옵션입니다: %~1
echo 기본 실행: run_local.bat  ^(FastAPI 서버 실행 + 브라우저 열기^)
echo 메뉴 실행: run_local.bat menu
echo 사용 예시: run_local.bat title
goto :end

:menu
cls
echo ==============================================
echo           Keyword Forge 로컬 실행 메뉴
echo ==============================================
echo.
echo [1] Collector 예시 실행
echo [2] Expander 예시 실행
echo [3] Analyzer 예시 실행
echo [4] Selector 예시 실행
echo [5] Title 예시 실행
echo [6] 전체 예시 순차 실행
echo [7] FastAPI 서버 실행 + 브라우저 열기
echo [0] 종료
echo.
choice /C 12345670 /N /M "실행할 번호를 선택하세요: "
if errorlevel 8 goto :end
if errorlevel 7 goto :run_api
if errorlevel 6 goto :run_all
if errorlevel 5 goto :run_title
if errorlevel 4 goto :run_selector
if errorlevel 3 goto :run_analyzer
if errorlevel 2 goto :run_expander
if errorlevel 1 goto :run_collector

:run_collector
call :banner "collector 예시 실행"
"%PYTHON_CMD%" app\collector\main.py
call :maybe_pause
if "%INTERACTIVE%"=="1" goto :menu
goto :end

:run_expander
call :banner "expander 예시 실행"
"%PYTHON_CMD%" app\expander\main.py
call :maybe_pause
if "%INTERACTIVE%"=="1" goto :menu
goto :end

:run_analyzer
call :banner "analyzer 예시 실행"
"%PYTHON_CMD%" app\analyzer\main.py
call :maybe_pause
if "%INTERACTIVE%"=="1" goto :menu
goto :end

:run_selector
call :banner "selector 예시 실행"
"%PYTHON_CMD%" app\selector\main.py
call :maybe_pause
if "%INTERACTIVE%"=="1" goto :menu
goto :end

:run_title
call :banner "title 예시 실행"
"%PYTHON_CMD%" app\title\main.py
call :maybe_pause
if "%INTERACTIVE%"=="1" goto :menu
goto :end

:run_all
call :banner "전체 예시 순차 실행"
call :run_collector_no_pause
call :run_expander_no_pause
call :run_analyzer_no_pause
call :run_selector_no_pause
call :run_title_no_pause
echo.
echo 전체 예시 실행이 끝났습니다.
call :maybe_pause
if "%INTERACTIVE%"=="1" goto :menu
goto :end

:run_api
call :banner "FastAPI 서버 실행"
echo 주소: %APP_URL%
echo 브라우저: 자동 열기
echo 종료: Ctrl + C
echo.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process '%APP_URL%'" >nul 2>nul
"%PYTHON_CMD%" -m uvicorn app.main:app --reload
call :maybe_pause
if "%INTERACTIVE%"=="1" goto :menu
goto :end

:run_collector_no_pause
call :banner "collector 예시 실행"
"%PYTHON_CMD%" app\collector\main.py
goto :eof

:run_expander_no_pause
call :banner "expander 예시 실행"
"%PYTHON_CMD%" app\expander\main.py
goto :eof

:run_analyzer_no_pause
call :banner "analyzer 예시 실행"
"%PYTHON_CMD%" app\analyzer\main.py
goto :eof

:run_selector_no_pause
call :banner "selector 예시 실행"
"%PYTHON_CMD%" app\selector\main.py
goto :eof

:run_title_no_pause
call :banner "title 예시 실행"
"%PYTHON_CMD%" app\title\main.py
goto :eof

:resolve_python
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
    goto :eof
)
if exist "venv\Scripts\python.exe" (
    set "PYTHON_CMD=venv\Scripts\python.exe"
    goto :eof
)
where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto :eof
)

echo Python 실행 파일을 찾지 못했습니다.
echo .venv\Scripts\python.exe 또는 venv\Scripts\python.exe를 만들거나 Python을 PATH에 추가하세요.
exit /b 1

:banner
echo.
echo ----------------------------------------------
echo %~1
echo ----------------------------------------------
echo.
goto :eof

:maybe_pause
if "%INTERACTIVE%"=="1" pause
goto :eof

:end
endlocal
