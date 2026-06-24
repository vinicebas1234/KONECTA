@echo off
REM Script para criar atalho no Desktop

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set DIST_DIR=%SCRIPT_DIR%dist
set EXE_PATH=%DIST_DIR%\Libras_OCR.exe
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT_PATH=%DESKTOP%\Libras OCR.lnk

REM Verifica se EXE existe
if not exist "%EXE_PATH%" (
    echo ERRO: EXE nao encontrado em %EXE_PATH%
    echo Execute gerar_exe.bat primeiro!
    pause
    exit /b 1
)

echo Criando atalho no Desktop...

REM Cria atalho usando PowerShell
powershell -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$sc = $ws.CreateShortcut('%SHORTCUT_PATH%'); " ^
    "$sc.TargetPath = '%EXE_PATH%'; " ^
    "$sc.WorkingDirectory = '%DIST_DIR%'; " ^
    "$sc.Description = 'Sistema de Reconhecimento de LIBRAS'; " ^
    "$sc.Save()"

if errorlevel 1 (
    echo ERRO ao criar atalho
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   SUCESSO!
echo ==========================================
echo.
echo Atalho criado no Desktop: %DESKTOP%
echo.
echo Agora pode duplo-clicar em "Libras OCR" no Desktop!
echo.
pause
