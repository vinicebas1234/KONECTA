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

echo [1/5] Instalando dependencias essenciais...
"%VENV_PYTHON%" -m pip install -q pyinstaller

REM Garante que OpenCV e outras dependências estão instaladas
"%VENV_PYTHON%" -m pip install -q opencv-python mediapipe numpy scikit-learn pillow
"%VENV_PYTHON%" -m pip install -q --upgrade setuptools wheel

if errorlevel 1 (
    echo ERRO ao instalar dependencias
    pause
    exit /b 1
)

echo [2/5] Limpando arquivos antigos...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%" >nul 2>&1
if exist "build\" rmdir /s /q "build\" >nul 2>&1
if exist "*.spec" del /q "*.spec" >nul 2>&1

echo [3/5] Gerando EXE com PyInstaller (isso pode levar 3-5 minutos)...
cd /d "%OCR_DIR%"

"%VENV_PYTHON%" -m PyInstaller ^
    --onedir ^
    --windowed ^
    --collect-all=cv2 ^
    --collect-all=mediapipe ^
    --collect-all=sklearn ^
    --collect-all=numpy ^
    --hidden-import=cv2 ^
    --hidden-import=mediapipe ^
    --hidden-import=tensorflow ^
    --hidden-import=sklearn ^
    --hidden-import=sklearn.ensemble ^
    --hidden-import=sklearn.preprocessing ^
    --hidden-import=sklearn.neighbors ^
    --hidden-import=sklearn.metrics ^
    --hidden-import=sklearn.model_selection ^
    --hidden-import=numpy ^
    --hidden-import=tkinter ^
    --hidden-import=PIL ^
    --distpath "%DIST_DIR%" ^
    --name "Libras_OCR" ^
    main.py

if errorlevel 1 (
    echo ERRO ao gerar EXE
    pause
    exit /b 1
)

echo [4/5] Copiando dados e modelos...

REM Cria pasta com suporte
if exist "%OCR_DIR%\dados_libras" (
    if not exist "%DIST_DIR%\Libras_OCR\dados_libras" (
        xcopy "%OCR_DIR%\dados_libras" "%DIST_DIR%\Libras_OCR\dados_libras\" /E /I /Y >nul 2>&1
    )
)

if exist "%OCR_DIR%\modelos" (
    if not exist "%DIST_DIR%\Libras_OCR\modelos" (
        xcopy "%OCR_DIR%\modelos" "%DIST_DIR%\Libras_OCR\modelos\" /E /I /Y >nul 2>&1
    )
)

echo [5/5] Finalizando (limpando arquivos temporarios)...
cd /d "%SCRIPT_DIR%"
if exist "build\" rmdir /s /q "build\" >nul 2>&1
if exist "*.spec" del /q "*.spec" >nul 2>&1

echo.
echo ==========================================
echo   SUCESSO!
echo ==========================================
echo.
echo EXE criado em:
echo   %DIST_DIR%\Libras_OCR\Libras_OCR.exe
echo.
echo O EXE ja inclui:
echo   - Python runtime completo
echo   - OpenCV, MediaPipe, TensorFlow
echo   - Todos os dados/modelos
echo   - Tudo que precisa para funcionar!
echo.
echo Agora pode:
echo   1. Duplo-clique direto: %DIST_DIR%\Libras_OCR\Libras_OCR.exe
echo   2. Criar atalho: execute create_shortcut.bat
echo   3. Compartilhar: copie pasta Libras_OCR para outro PC
echo.
pause
