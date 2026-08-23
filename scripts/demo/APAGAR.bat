@echo off
setlocal
title Provecho ERP - Demo (apagar)
cd /d "%~dp0"

echo.
echo   Apagando la demo. Los datos que cargaste se conservan:
echo   la proxima vez que abras INICIAR.bat siguen ahi.
echo.

docker compose -f docker-compose.demo.yml down

echo.
echo   Apagado.
echo.
ping -n 11 127.0.0.1 >nul
endlocal
