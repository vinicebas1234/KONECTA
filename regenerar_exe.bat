@echo off
REM Script para limpar e regenerar EXE do zero

setlocal enabledelayedexpansion

cls
echo.
echo ==========================================
echo   Regenerando EXE (limpeza completa)
echo ==========================================
echo.

set SCRIPT_DIR=%~dp0
set DIST_DIR=%SCRIPT_DIR%dist

REM Verifica e deleta pasta dist
if exist "%DIST_DIR%" (
    echo Deletando pasta anterior: %DIST_DIR%
    rmdir /s /q "%DIST_DIR%"
    timeout /t 2 /nobreak
)

REM Deleta arquivos temporarios
if exist "build\" rmdir /s /q "build\"
if exist "*.spec" del "*.spec"

echo.
echo Agora execute: gerar_exe.bat
echo.
pause
