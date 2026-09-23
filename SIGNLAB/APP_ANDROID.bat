@echo off
setlocal
title SIGNLAB - app Android
cd /d "%~dp0"

REM Sobe o SIGNLAB se ainda nao estiver no ar.
curl -s -o nul -m 2 http://127.0.0.1:8100/entrar.html
if errorlevel 1 (
    echo [..]   Subindo o SIGNLAB...
    start "SIGNLAB" /min cmd /c "python -m uvicorn app.backend.main:app --port 8100"
    timeout /t 10 /nobreak >nul
)

REM Nunca publica um SIGNLAB sem senha. Se a API responde sem login, o que
REM esta rodando e' uma versao antiga e o Funnel a exporia na internet.
set CODIGO=
for /f %%c in ('curl -s -o nul -w "%%{http_code}" -m 3 http://127.0.0.1:8100/api/projects') do set CODIGO=%%c
if not "%CODIGO%"=="401" (
    echo [ERRO] O SIGNLAB na porta 8100 nao pediu senha como devia - codigo %CODIGO%.
    echo        Feche a janela do SIGNLAB e rode este arquivo de novo.
    pause
    exit /b 1
)

REM Publica a porta 8100 na internet com HTTPS: a camera do celular so abre
REM em HTTPS. Na primeira vez o Tailscale mostra um link para habilitar o Funnel.
set TS=C:\Program Files\Tailscale\tailscale.exe
if exist "%TS%" (
    "%TS%" funnel --bg 8100
) else (
    echo [AVISO] Tailscale nao encontrado. Veja APP_ANDROID.md, passo 1.
)

echo.
python scripts\link_do_app.py %*
echo.
pause
