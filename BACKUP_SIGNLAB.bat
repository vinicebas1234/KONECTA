@echo off
REM Copia gravacoes e banco do SIGNLAB para fora do repositorio.
REM
REM Motivo: projects e data\*.db estao no .gitignore, nunca foram versionados.
REM Perdemos 50 videos gravados e o banco inteiro assim, sem recuperacao pelo
REM git. Isto roda a cada abertura do KONECTA_V3.
REM
REM Usa /E e NAO /MIR de proposito: espelhar apagaria do backup o que sumiu da
REM origem, que e' justamente o acidente contra o qual isto protege. Aqui o
REM backup so' acumula.

setlocal
set ORIGEM=C:\KONECTA\SIGNLAB
set DESTINO=C:\KONECTA_BACKUP

for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set HOJE=%%c-%%b-%%a
set ALVO=%DESTINO%\%HOJE%

set COPIADOS=0

if exist "%ORIGEM%\projects" (
    robocopy "%ORIGEM%\projects" "%ALVO%\projects" /E /NFL /NDL /NJH /NJS /NP >nul 2>&1
    if errorlevel 8 (echo   [AVISO] falha ao copiar projects) else (set COPIADOS=1)
)

if exist "%ORIGEM%\data" (
    robocopy "%ORIGEM%\data" "%ALVO%\data" /E /NFL /NDL /NJH /NJS /NP >nul 2>&1
    if errorlevel 8 (echo   [AVISO] falha ao copiar data) else (set COPIADOS=1)
)

if "%COPIADOS%"=="1" (
    echo   [OK] backup em %ALVO%
) else (
    echo   [AVISO] nada foi copiado - verifique %ORIGEM%
)

endlocal
