@echo off
REM Script para executar Libras OCR com variáveis de ambiente configuradas

setlocal enabledelayedexpansion

REM Define caminho base
set LIBRAS_BASE_DIR=%~dp0OCR
set PYTHONPATH=%LIBRAS_BASE_DIR%

echo.
echo ========================================
echo   Libras OCR - Sistema de Reconhecimento
echo ========================================
echo.
echo LIBRAS_BASE_DIR: %LIBRAS_BASE_DIR%
echo PYTHONPATH: %PYTHONPATH%
echo.

REM Verifica se venv existe
if not exist "%LIBRAS_BASE_DIR%\.venv2\Scripts\python.exe" (
    echo ERRO: Ambiente virtual nao encontrado em %LIBRAS_BASE_DIR%\.venv2
    echo Por favor, crie o ambiente virtual primeiro.
    pause
    exit /b 1
)

REM Executa
echo Iniciando aplicacao...
echo.
cd /d "%LIBRAS_BASE_DIR%"
call ".venv2\Scripts\python.exe" libras_recognizer.py

pause
