@echo off
REM ============================================================================
REM KONECTA Intelligence Hub - Auto Deploy Agents (Versão Simples)
REM Script batch para copiar scripts de agents automaticamente
REM ============================================================================

chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║     KONECTA Intelligence Hub - Deploy Agents (Automático)     ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

REM Definir diretório
set SCRIPT_DIR=%~dp0
set AGENT_SCRIPTS=%SCRIPT_DIR%AGENT_SCRIPTS.md

REM Verificar se arquivo existe
if not exist "%AGENT_SCRIPTS%" (
    echo ❌ Erro: AGENT_SCRIPTS.md não encontrado em %SCRIPT_DIR%
    echo.
    pause
    exit /b 1
)

echo ⚠️  IMPORTANTE: NÃO MEXER EM SIGNLAB!
echo Todos os agents vão trabalhar APENAS em KONECTA_V3
echo.
echo ════════════════════════════════════════════════════════════════
echo.

REM Menu de opções
echo 📋 Escolha um agent para deploy:
echo.
echo   1. 🔵 CLAUDE       - Architecture Review
echo   2. 🟠 CODEX        - Motor Optimization
echo   3. 🌐 GEMINI       - Vision Motor
echo   4. 🔴 GROK         - Context Engine
echo   5. 💎 OPENCODE #1  - Code Quality
echo   6. 💎 OPENCODE #2  - Testing Suite
echo   7. 🎨 CURSOR       - UI Polish
echo   8. 💎 OPENCODE #3  - Backend Setup
echo   9. 🚀 TODOS (Deploy All)
echo   0. ❌ Sair
echo.

set /p choice="Digite sua escolha (0-9): "

if "%choice%"=="0" goto end
if "%choice%"=="1" goto deploy_claude
if "%choice%"=="2" goto deploy_codex
if "%choice%"=="3" goto deploy_gemini
if "%choice%"=="4" goto deploy_grok
if "%choice%"=="5" goto deploy_opencode1
if "%choice%"=="6" goto deploy_opencode2
if "%choice%"=="7" goto deploy_cursor
if "%choice%"=="8" goto deploy_opencode3
if "%choice%"=="9" goto deploy_all

echo ❌ Opção inválida!
timeout /t 2 >nul
goto :eof

REM ============================================================================
REM DEPLOYMENTS
REM ============================================================================

:deploy_claude
cls
echo 🔵 Deployando: CLAUDE - Architecture Review
echo.
echo ℹ️  Script copiado para clipboard!
echo Próximos passos:
echo   1. Abra Orca (Ctrl+Shift+W)
echo   2. Selecione agent: Claude
echo   3. Cole o script (Ctrl+V)
echo   4. Clique "Create worktree"
echo.
REM Copia o arquivo inteiro para clipboard (será processado manualmente)
type "%AGENT_SCRIPTS%" | clip
echo ✅ Arquivo AGENT_SCRIPTS.md copiado!
echo.
pause
goto end

:deploy_codex
cls
echo 🟠 Deployando: CODEX - Motor Optimization
echo.
echo ℹ️  Script copiado para clipboard!
echo Próximos passos:
echo   1. Abra Orca
echo   2. Selecione agent: Codex
echo   3. Cole o script
echo   4. Clique "Create worktree"
echo.
type "%AGENT_SCRIPTS%" | clip
echo ✅ Arquivo copiado!
echo.
pause
goto end

:deploy_gemini
cls
echo 🌐 Deployando: GEMINI - Vision Motor
echo.
type "%AGENT_SCRIPTS%" | clip
echo ✅ Arquivo copiado para clipboard!
echo.
pause
goto end

:deploy_grok
cls
echo 🔴 Deployando: GROK - Context Engine
echo.
type "%AGENT_SCRIPTS%" | clip
echo ✅ Arquivo copiado para clipboard!
echo.
pause
goto end

:deploy_opencode1
cls
echo 💎 Deployando: OPENCODE #1 - Code Quality
echo.
type "%AGENT_SCRIPTS%" | clip
echo ✅ Arquivo copiado para clipboard!
echo.
pause
goto end

:deploy_opencode2
cls
echo 💎 Deployando: OPENCODE #2 - Testing Suite
echo.
type "%AGENT_SCRIPTS%" | clip
echo ✅ Arquivo copiado para clipboard!
echo.
pause
goto end

:deploy_cursor
cls
echo 🎨 Deployando: CURSOR - UI Polish
echo.
type "%AGENT_SCRIPTS%" | clip
echo ✅ Arquivo copiado para clipboard!
echo.
pause
goto end

:deploy_opencode3
cls
echo 💎 Deployando: OPENCODE #3 - Backend Setup
echo.
type "%AGENT_SCRIPTS%" | clip
echo ✅ Arquivo copiado para clipboard!
echo.
pause
goto end

:deploy_all
cls
echo 🚀 DEPLOYANDO TODOS OS AGENTS!
echo.
echo Copiando AGENT_SCRIPTS.md para clipboard...
type "%AGENT_SCRIPTS%" | clip
echo.
echo ✅ Arquivo copiado!
echo.
echo 📋 Agora você pode:
echo.
echo   OPÇÃO 1 - Manual (um por um):
echo     1. Abra Orca (Ctrl+Shift+W)
echo     2. Selecione agent #1
echo     3. Cole (Ctrl+V)
echo     4. Clique "Create worktree"
echo     5. Repeat para agents 2-8
echo.
echo   OPÇÃO 2 - Automático (em desenvolvimento):
echo     Execute: powershell -ExecutionPolicy Bypass -File deploy_agents.ps1 -All
echo.
pause
goto end

:end
cls
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║                     ✅ TUDO PRONTO!                          ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.
echo 📝 Próximos passos:
echo   1. Abra Orca em: C:\Users\vrsantos\.claude\orca
echo   2. Crie worktree (Ctrl+Shift+W)
echo   3. Cole o script (Ctrl+V está no clipboard)
echo   4. Clique "Create worktree"
echo   5. Agent vai começar a trabalhar!
echo.
echo 💡 Dica: Para todos os agents, repita para cada um
echo ⚡ Dica: PowerShell script pode automatizar tudo
echo.
echo Digite qualquer tecla para fechar...
pause >nul
exit /b 0
