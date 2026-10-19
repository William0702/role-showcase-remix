@echo off

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-latest.ps1" %*

exit /b %errorlevel%

