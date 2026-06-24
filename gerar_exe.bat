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

echo [1/4] Instalando dependencias...
"%VENV_PYTHON%" -m pip install -q pyinstaller
"%VENV_PYTHON%" -m pip install -q --upgrade setuptools wheel

if errorlevel 1 (
    echo ERRO ao instalar dependencias
    pause
    exit /b 1
)

echo [2/4] Limpando arquivos antigos...
if exist "%DIST_DIR%\Libras_OCR.exe" del "%DIST_DIR%\Libras_OCR.exe"
if exist "build\" rmdir /s /q "build\" >nul 2>&1
if exist "*.spec" del "*.spec" >nul 2>&1

echo [3/4] Gerando EXE (isso pode levar 2-3 minutos)...
cd /d "%OCR_DIR%"
"%VENV_PYTHON%" -m PyInstaller ^
    --onedir ^
    --windowed ^
    --collect-all=mediapipe ^
    --collect-all=tensorflow ^
    --collect-all=sklearn ^
    --hidden-import=mediapipe ^
    --hidden-import=tensorflow ^
    --hidden-import=sklearn ^
    --hidden-import=cv2 ^
    --hidden-import=numpy ^
    --hidden-import=tkinter ^
    --distpath "%DIST_DIR%" ^
    --name "Libras_OCR" ^
    libras_recognizer.py

if errorlevel 1 (
    echo ERRO ao gerar EXE
    pause
    exit /b 1
)

echo [4/4] Copiando arquivos e limpando temporarios...

REM Cria pasta com suporte
if not exist "%DIST_DIR%\Libras_OCR\dados_libras" (
    if exist "%OCR_DIR%\dados_libras" (
        xcopy "%OCR_DIR%\dados_libras" "%DIST_DIR%\Libras_OCR\dados_libras\" /E /I /Y >nul 2>&1
    )
)

if not exist "%DIST_DIR%\Libras_OCR\modelos" (
    if exist "%OCR_DIR%\modelos" (
        xcopy "%OCR_DIR%\modelos" "%DIST_DIR%\Libras_OCR\modelos\" /E /I /Y >nul 2>&1
    )
)

REM Limpa temporarios
cd /d "%SCRIPT_DIR%"
if exist "build\" rmdir /s /q "build\" >nul 2>&1
if exist "*.spec" del "*.spec" >nul 2>&1

echo.
echo ==========================================
echo   SUCESSO!
echo ==========================================
echo.
echo EXE criado em: %DIST_DIR%\Libras_OCR\Libras_OCR.exe
echo.
echo Opcoes:
echo   1. Duplo-clique em: %DIST_DIR%\Libras_OCR\Libras_OCR.exe
echo   2. Crie atalho no Desktop
echo.
echo Para criar atalho no Desktop, execute:
echo   create_shortcut.bat
echo.
pause
