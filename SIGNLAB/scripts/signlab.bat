@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0\.."

:menu
cls
echo.
echo ========================================
echo       SIGNLAB Server Manager
echo ========================================
echo.
echo 1 - Iniciar servidor (porta 8100)
echo 2 - Parar servidor
echo 3 - Sair
echo.
set /p choice="Escolha uma opcao (1-3): "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto exit
echo Opcao invalida!
timeout /t 2 >nul
goto menu

:start
cls
echo Iniciando SIGNLAB na porta 8100...
echo Acesse: http://localhost:8100
echo.
python -m uvicorn app.backend.main:app --port 8100 --reload
goto menu

:stop
cls
echo Parando servidor SIGNLAB...
netstat -ano | findstr :8100 > nul
if %errorlevel% == 0 (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8100') do taskkill /pid %%a /f
    echo Servidor parado com sucesso!
) else (
    echo Servidor nao esta rodando.
)
timeout /t 2 >nul
goto menu

:exit
exit /b 0
