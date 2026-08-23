@echo off
setlocal
title Provecho ERP - Demo (reiniciar)
cd /d "%~dp0"

echo.
echo   REINICIAR LA DEMO
echo   =================
echo.
echo   Esto BORRA todo lo que cargaste o vendiste en la demo y deja
echo   el sistema como recien instalado. No se puede deshacer.
echo.
set /p RESPUESTA=  Escribe BORRAR y pulsa Enter para continuar:
if /i not "%RESPUESTA%"=="BORRAR" (
  echo.
  echo   Cancelado. No se toco nada.
  echo.
  ping -n 11 127.0.0.1 >nul
  exit /b 0
)

echo.
echo   Borrando los datos...
docker compose -f docker-compose.demo.yml down -v
if errorlevel 1 (
  echo.
  echo   [ERROR] No se pudo borrar. Revisa que Docker Desktop este abierto.
  echo.
  pause
  exit /b 1
)

echo   Volviendo a sembrar los datos de prueba...
call "%~dp0INICIAR.bat"
endlocal
