@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

:menu
cls
echo.
echo ====================================================
echo            KONECTA - Libras Research
echo ====================================================
echo.
echo Projetos Ativos:
echo.
echo 1 - SIGNLAB (Teachable Machine) *RECOMENDADO*
echo 2 - KONECTA_V2 (Framework backend)
echo 3 - Ver estrutura do repositorio
echo 4 - Sair
echo.
set /p choice="Escolha uma opcao (1-4): "

if "%choice%"=="1" goto signlab
if "%choice%"=="2" goto v2
if "%choice%"=="3" goto structure
if "%choice%"=="4" goto exit
echo Opcao invalida!
timeout /t 2 >nul
goto menu

:signlab
cls
cd SIGNLAB
call scripts\signlab.bat
goto menu

:v2
cls
echo.
echo Abrindo KONECTA_V2...
cd KONECTA_V2
echo.
echo Consulte README.md para instruções de setup.
echo.
cd ..
timeout /t 3 >nul
goto menu

:structure
cls
echo.
echo ESTRUTURA DE KONECTA:
echo.
echo KONECTA/
echo  ^|- SIGNLAB/              ^(Teachable Machine - ATIVO^)
echo  ^|- KONECTA_V2/           ^(Framework - EM DESENVOLVIMENTO^)
echo  ^|- Datasets/             ^(V-LIBRASIL e outros^)
echo  ^|- docs/                 ^(Documentacao geral^)
echo  ^|- archive/              ^(Projetos antigos - 2025-08-11^)
echo  ^|- README_PROJETOS.md    ^(Guia completo^)
echo.
echo Para detalhes: README_PROJETOS.md
echo.
timeout /t 5 >nul
goto menu

:exit
exit /b 0
