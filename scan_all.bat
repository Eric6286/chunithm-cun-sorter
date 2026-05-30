@echo off
chcp 65001 >nul
rem One-shot: classify existing CHUNITHM screenshots (source mode; needs Python).
where python.exe >nul 2>nul
if %errorlevel%==0 (
  python "%~dp0scan_all.py" %*
) else (
  py "%~dp0scan_all.py" %*
)
echo.
pause
