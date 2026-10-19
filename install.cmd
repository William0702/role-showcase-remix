@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set "taskInstallExit=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %taskInstallExit%
