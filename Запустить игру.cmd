@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

py -3 -c "import sys; sys.exit(sys.version_info[:2] < (3, 10))" >nul 2>&1
if not errorlevel 1 (
    py -3 launcher.py %*
    goto finished
)

python -c "import sys; sys.exit(sys.version_info[:2] < (3, 10))" >nul 2>&1
if not errorlevel 1 (
    python launcher.py %*
    goto finished
)

set "OSM_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%OSM_PYTHON%" (
    "%OSM_PYTHON%" -c "import sys; sys.exit(sys.version_info[:2] < (3, 10))" >nul 2>&1
    if not errorlevel 1 (
        "%OSM_PYTHON%" launcher.py %*
        goto finished
    )
)

echo Python 3.10 или новее не найден.
echo Установите Python с https://www.python.org/downloads/windows/
echo При установке включите Add Python to PATH, затем запустите этот файл снова.
echo Если есть готовый OSMGame.exe, его можно запустить без установки Python.
pause
exit /b 1

:finished
if errorlevel 1 (
    echo.
    echo Не удалось запустить игру. Сообщение об ошибке приведено выше.
    pause
    exit /b 1
)
exit /b 0
