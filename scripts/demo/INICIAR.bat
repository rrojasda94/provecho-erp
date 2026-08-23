@echo off
setlocal
title Provecho ERP - Demo
cd /d "%~dp0"

if "%PUERTO_WEB%"=="" set PUERTO_WEB=3000

echo.
echo   PROVECHO ERP - DEMO
echo   ===================
echo.

docker info >nul 2>&1
if errorlevel 1 (
  echo   [ATENCION] Docker Desktop no esta corriendo.
  echo.
  echo   1. Abre Docker Desktop desde el menu Inicio.
  echo   2. Espera a que el icono de la ballena deje de moverse.
  echo   3. Vuelve a hacer doble clic en INICIAR.bat
  echo.
  echo   Si no lo tienes instalado: https://docs.docker.com/desktop/
  echo.
  pause
  exit /b 1
)

REM La carga de imagenes es de una sola vez: pesa y tarda, asi que se
REM comprueba antes en vez de repetirla en cada arranque.
docker image inspect provecho-demo-api:latest >nul 2>&1
if errorlevel 1 (
  echo   Instalando por primera vez. Esto tarda varios minutos,
  echo   no cierres esta ventana...
  echo.
  docker load -i imagenes.tar
  if errorlevel 1 (
    echo.
    echo   [ERROR] No se pudieron cargar las imagenes.
    echo   Revisa que el archivo imagenes.tar este junto a este INICIAR.bat
    echo   y que el ZIP se haya descomprimido completo.
    echo.
    pause
    exit /b 1
  )
)

echo   Encendiendo el sistema...
docker compose -f docker-compose.demo.yml up -d --no-build
if errorlevel 1 (
  echo.
  echo   [ERROR] No se pudo levantar la demo.
  echo   Mandale este mensaje a Renato junto con lo que dice arriba.
  echo.
  pause
  exit /b 1
)

echo   Preparando los datos de prueba...
set INTENTOS=0
:esperar
set /a INTENTOS+=1
curl -fsS -o nul http://localhost:%PUERTO_WEB%/login >nul 2>&1
if not errorlevel 1 goto listo
if %INTENTOS% GEQ 100 goto lento
ping -n 4 127.0.0.1 >nul
goto esperar

:lento
echo.
echo   [ATENCION] Esta tardando mas de lo normal (5 minutos).
echo   Puede que siga trabajando. Prueba abrir a mano:
echo   http://localhost:%PUERTO_WEB%
echo.
pause
exit /b 1

:listo
echo.
echo   Listo. Abriendo el navegador.
echo.
echo   Direccion: http://localhost:%PUERTO_WEB%
echo   Usuario:   admin
echo   PIN:       123456
echo.
echo   Desde el celular o la tablet, en la misma red WiFi, usa la IP
echo   de esta PC en vez de localhost (ejemplo: http://192.168.1.20:%PUERTO_WEB%).
echo   La ves con el comando: ipconfig
echo.
echo   Puedes cerrar esta ventana. Para apagar: APAGAR.bat
echo.
start "" "http://localhost:%PUERTO_WEB%"
REM Pausa para que se alcancen a leer el usuario y el PIN antes de que la
REM ventana se cierre. Con `ping` y no con `timeout`, que aborta con un error
REM cuando el .bat no se lanza desde una consola interactiva.
ping -n 21 127.0.0.1 >nul
endlocal
