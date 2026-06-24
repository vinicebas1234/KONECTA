@echo off
REM Forma manual: cria atalho usando "Enviar para"

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set DIST_DIR=%SCRIPT_DIR%dist
set EXE_PATH=%DIST_DIR%\Libras_OCR.exe

cls
echo.
echo ==========================================
echo   Criar Atalho no Desktop
echo ==========================================
echo.

REM Verifica se EXE existe
if not exist "%EXE_PATH%" (
    echo ERRO: EXE nao encontrado em %EXE_PATH%
    echo Execute gerar_exe.bat primeiro!
    pause
    exit /b 1
)

echo.
echo Opcao 1: Clique direito no EXE abaixo e selecione:
echo          "Enviar para" ^> "Desktop (atalho)"
echo.
echo Opcao 2: Ou execute este comando (copie e cole):
echo.
echo %EXE_PATH%
echo.
echo Abrindo a pasta do EXE...
echo.
explorer.exe /select,"%EXE_PATH%"

pause
