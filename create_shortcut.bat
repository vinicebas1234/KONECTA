@echo off
REM Script para criar atalho no Desktop

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set DIST_DIR=%SCRIPT_DIR%dist
set EXE_PATH=%DIST_DIR%\Libras_OCR\Libras_OCR.exe
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT_PATH=%DESKTOP%\Libras OCR.lnk

REM Verifica se EXE existe
if not exist "%EXE_PATH%" (
    echo ERRO: EXE nao encontrado em %EXE_PATH%
    echo.
    echo Verifique se executou: gerar_exe.bat
    echo.
    pause
    exit /b 1
)

REM Verifica se Desktop existe, se nao, cria
if not exist "%DESKTOP%" (
    echo Criando pasta Desktop...
    mkdir "%DESKTOP%"
)

echo Criando atalho no Desktop...
echo.

REM Cria arquivo VBS temporario para criar atalho (mais confiavel)
set VBS_FILE=%TEMP%\create_shortcut_%RANDOM%.vbs

(
    echo Set oWS = WScript.CreateObject("WScript.Shell"^)
    echo sLinkFile = "%SHORTCUT_PATH%"
    echo Set oLink = oWS.CreateShortcut(sLinkFile^)
    echo oLink.TargetPath = "%EXE_PATH%"
    echo oLink.WorkingDirectory = "%DIST_DIR%"
    echo oLink.Description = "Sistema de Reconhecimento de LIBRAS"
    echo oLink.Save
) > "%VBS_FILE%"

cscript //nologo "%VBS_FILE%"
set VBS_RESULT=%errorlevel%

REM Deleta arquivo VBS temporario
del "%VBS_FILE%" >nul 2>&1

if not %VBS_RESULT% equ 0 (
    echo.
    echo ERRO ao criar atalho no Desktop.
    echo.
    echo Opcoes alternativas:
    echo 1. Duplo-clique manualmente em: %DIST_DIR%\Libras_OCR.exe
    echo 2. Crie um atalho manualmente:
    echo    - Clique direito no EXE
    echo    - Enviar para ^> Desktop
    echo.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   SUCESSO!
echo ==========================================
echo.
echo Atalho criado no Desktop: %DESKTOP%
echo Nome: Libras OCR.lnk
echo.
echo Agora pode duplo-clicar em "Libras OCR" no Desktop!
echo.
pause
