@echo off
setlocal
cd /d "%~dp0"
python main.py
if errorlevel 1 (
  echo.
  echo benchmark_tool failed.
  pause
  exit /b %errorlevel%
)
echo.
echo benchmark_tool finished.
pause
