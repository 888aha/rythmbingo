@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
set "EC=%ERRORLEVEL%"

echo.
echo Finished (exit code %EC%). Press any key to close...
pause >nul

endlocal & exit /b %EC%
