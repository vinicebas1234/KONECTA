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

REM /XD pula o V-LIBRASIL: sao 11 GB que ja existem intactos em
REM C:\KONECTA\Datasets e se reimportam com scripts\import_vlibrasil.py.
REM Sem isto, cada dia de uso somaria 11 GB ao backup e o disco encheria em 3.
REM Os landmarks do V-LIBRASIL (sequences dentro dele) saem junto: derivados.
REM ATENCAO: nos outros projetos, sequences NAO e' cache. As gravacoes do app
REM de celular apagam o video e ficam so' como .npy la' - e' a unica copia.
REM Nunca exclua sequences deste backup.
if exist "%ORIGEM%\projects" (
    robocopy "%ORIGEM%\projects" "%ALVO%\projects" /E /XD "%ORIGEM%\projects\vlibrasil-completo" /NFL /NDL /NJH /NJS /NP >nul 2>&1
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
