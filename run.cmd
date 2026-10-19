@echo off
"%~dp0tools\windows-x64\python\python.exe" "%~dp0scripts\remix.py" %*
exit /b %errorlevel%
