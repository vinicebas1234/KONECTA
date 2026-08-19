@echo off
setlocal
title KONECTA V3 - Teste com interprete
cd /d "%~dp0"

echo.
echo ============================================================
echo   KONECTA V3 - sessao de teste
echo ============================================================
echo.

REM ---------- 1. ambiente ----------
if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] .venv nao encontrada.
    echo        Rode:  python -m venv .venv
    echo               .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
echo [OK]   Ambiente principal

REM ---------- 2. modelo ----------
dir /b models\*.zip models\*.joblib models\*.keras >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Nenhum modelo em models\
    echo        Exporte um experimento no SIGNLAB e copie o .zip para:
    echo        %cd%\models\
    pause
    exit /b 1
)
echo [OK]   Modelo encontrado:
for %%f in (models\*.zip models\*.joblib models\*.keras) do echo        - %%~nxf

REM ---------- 3. sinais dinamicos ----------
if exist ".venv-temporal\Scripts\python.exe" (
    echo [OK]   Sinais dinamicos habilitados
) else (
    echo [AVISO] .venv-temporal ausente: modelos temporais NAO vao funcionar.
    echo         Para habilitar sinais dinamicos:
    echo           python -m venv .venv-temporal
    echo           .venv-temporal\Scripts\pip install keras tensorflow-cpu numpy
)

REM ---------- 3.5 backup das gravacoes ----------
REM projects e data do SIGNLAB nao estao no git. Copia antes de abrir, porque
REM ja perdemos 50 videos e o banco sem ter como recuperar.
if exist "C:\KONECTA\BACKUP_SIGNLAB.bat" call "C:\KONECTA\BACKUP_SIGNLAB.bat"

REM ---------- 4. avatar (audio para Libras) ----------
REM Sobe apenas o SERVIDOR do TEXTO_PARA_LIBRAS, sem a janela dele: o avatar
REM aparece embutido no KONECTA. Abrir o app completo criava uma segunda janela
REM competindo com esta.
curl -s -o nul -m 2 http://127.0.0.1:8300/ >nul 2>&1
if errorlevel 1 (
    echo [..]   Subindo o servidor do avatar...
    if exist "C:\KONECTA\TEXTO_PARA_LIBRAS\server.py" (
        start "avatar" /min cmd /c "cd /d C:\KONECTA\TEXTO_PARA_LIBRAS && python server.py"
    )
    timeout /t 6 /nobreak >nul
    curl -s -o nul -m 3 http://127.0.0.1:8300/ >nul 2>&1
    if errorlevel 1 (echo [AVISO] Avatar nao subiu; o audio ainda vira texto na janela.) else (echo [OK]   Avatar no ar)
) else (
    echo [OK]   Avatar ja estava no ar
)

REM ---------- 5. parametros da sessao ----------
REM Limiar de confianca. Se nada confirmar, baixe para 0.50.
if not defined KONECTA_LIMIAR set KONECTA_LIMIAR=0.60
REM KONECTA_HOLD_S NAO e' definido de proposito: o app escolhe sozinho conforme
REM o modelo. Temporal ja integra 30 frames e precisa de hold curto; definir
REM aqui rejeitava predicoes de 100% de confianca. Defina so' para forcar.
REM Liga a escuta do audio do PC.
if not defined KONECTA_AUDIO_ATIVO set KONECTA_AUDIO_ATIVO=true

echo.
echo        limiar de confianca : %KONECTA_LIMIAR%
if defined KONECTA_HOLD_S (echo        tempo de hold       : %KONECTA_HOLD_S%s) else (echo        tempo de hold       : automatico pelo modelo)
echo        audio para Libras   : %KONECTA_AUDIO_ATIVO%
echo.
echo ============================================================
echo   Iniciando. A janela abre em alguns segundos.
echo   Sinal dinamico leva ~2s para responder (janela de 30 frames).
echo ============================================================
echo.

.venv\Scripts\python.exe app_central\main.py

echo.
if errorlevel 1 (
    echo [ERRO] Encerrou com erro. Veja logs\app_central.log
) else (
    echo Encerrado.
)
pause
