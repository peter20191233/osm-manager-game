@echo off
setlocal
chcp 65001 >nul
call "%~dp0Запустить игру.cmd" --lan %*
exit /b %errorlevel%
