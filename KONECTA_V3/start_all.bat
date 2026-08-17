@echo off
REM ============================================
REM KONECTA V3 - Iniciar Todos os Servidores
REM ============================================

setlocal enabledelayedexpansion

echo.
echo ============================================
echo KONECTA V3 - INICIANDO SERVIDORES
echo ============================================
echo.

REM Get the project directory
cd /d "%~dp0"

REM Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao esta instalado ou nao esta no PATH!
    pause
    exit /b 1
)

REM Backend (FastAPI)
echo [1/2] Iniciando Backend (FastAPI)...
echo Aguarde alguns segundos...
start "KONECTA V3 - Backend" cmd /k "python vision_lab/app.py"

REM Wait for backend to start
timeout /t 4 /nobreak

REM Frontend (Tkinter GUI)
echo.
echo [2/2] Iniciando Frontend (GUI)...
start "KONECTA V3 - Frontend" cmd /k "python app_gui_v2.py"

echo.
echo ============================================
echo [OK] TUDO INICIADO!
echo ============================================
echo.
echo Backend:  http://localhost:8000
echo GUI:      Janela Tkinter aberta
echo.
echo Para PARAR tudo, execute: stop_all.bat
echo ============================================
echo.

timeout /t 2 /nobreak
