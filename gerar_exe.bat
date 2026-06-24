@echo off
REM Script para gerar EXE do Libras OCR usando PyInstaller

setlocal enabledelayedexpansion

cls
echo.
echo ==========================================
echo   Gerando EXE - Libras OCR
echo ==========================================
echo.

set SCRIPT_DIR=%~dp0
set OCR_DIR=%SCRIPT_DIR%OCR
set VENV_PYTHON=%OCR_DIR%\.venv2\Scripts\python.exe
set DIST_DIR=%SCRIPT_DIR%dist

REM Verifica se venv existe
if not exist "%VENV_PYTHON%" (
    echo ERRO: Ambiente virtual nao encontrado!
    echo Execute run.bat uma vez primeiro para criar o venv.
    pause
    exit /b 1
)

echo [1/4] Instalando PyInstaller...
"%VENV_PYTHON%" -m pip install -q pyinstaller

if errorlevel 1 (
    echo ERRO ao instalar PyInstaller
    pause
    exit /b 1
)

echo [2/4] Gerando EXE (isso pode levar 1-2 minutos)...
cd /d "%OCR_DIR%"
"%VENV_PYTHON%" -m PyInstaller ^
    --onefile ^
    --windowed ^
    --icon="%OCR_DIR%\icon.ico" ^
    --add-data "dados_libras;dados_libras" ^
    --add-data "modelos;modelos" ^
    --hidden-import=mediapipe ^
    --hidden-import=tensorflow ^
    --hidden-import=sklearn ^
    --hidden-import=cv2 ^
    --distpath "%DIST_DIR%" ^
    --name "Libras_OCR" ^
    libras_recognizer.py

if errorlevel 1 (
    echo ERRO ao gerar EXE
    pause
    exit /b 1
)

echo [3/4] Copiando arquivos necessarios...

REM Cria pasta com suporte
if not exist "%DIST_DIR%\dados_libras" (
    xcopy "%OCR_DIR%\dados_libras" "%DIST_DIR%\dados_libras\" /E /I /Y >nul 2>&1
)

if not exist "%DIST_DIR%\modelos" (
    xcopy "%OCR_DIR%\modelos" "%DIST_DIR%\modelos\" /E /I /Y >nul 2>&1
)

echo [4/4] Limpando arquivos temporarios...
cd /d "%SCRIPT_DIR%"
if exist "build\" rmdir /s /q "build\" >nul 2>&1
if exist "*.spec" del "*.spec" >nul 2>&1

echo.
echo ==========================================
echo   SUCESSO!
echo ==========================================
echo.
echo EXE criado em: %DIST_DIR%\Libras_OCR.exe
echo.
echo Opcoes:
echo   1. Duplo-clique em: %DIST_DIR%\Libras_OCR.exe
echo   2. Crie atalho no Desktop
echo   3. Adicione ao Menu Iniciar
echo.
echo Para criar atalho no Desktop, execute:
echo   create_shortcut.bat
echo.
pause
