@echo off

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update-from-github.ps1" -Update %*

exit /b %errorlevel%

