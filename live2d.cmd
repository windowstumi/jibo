@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0live2d.ps1" %*
exit /b %errorlevel%
