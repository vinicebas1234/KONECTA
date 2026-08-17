@echo off
setlocal enabledelayedexpansion

echo.
echo ════════════════════════════════════════════════════════════
echo      KONECTA Intelligence Hub - Inicialização
echo ════════════════════════════════════════════════════════════
echo.

REM Diretório do script
cd /d "%~dp0"

REM Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python não encontrado! Instale Python 3.10+
    pause
    exit /b 1
)

echo ✅ Python encontrado

REM Cria ambiente virtual se não existir
if not exist "venv" (
    echo 📦 Criando ambiente virtual...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Erro ao criar venv
        pause
        exit /b 1
    )
    echo ✅ Ambiente virtual criado
)

REM Ativa venv
echo 🔄 Ativando ambiente virtual...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ Erro ao ativar venv
    pause
    exit /b 1
)

REM Instala dependências
echo 📥 Verificando dependências...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ⚠️ Erro ao instalar dependências
    pause
    exit /b 1
)

echo ✅ Dependências OK

REM Cria diretórios
if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "cache" mkdir cache
if not exist "models\v1" (
    echo ⚠️ Modelos não encontrados em models\v1
    echo   Copie os arquivos do SIGNLAB:
    echo   - classifier.joblib
    echo   - metadata.json
    echo   - sequence_model.keras (opcional)
)

REM Verifica API keys
if not defined ANTHROPIC_API_KEY (
    echo ⚠️ ANTHROPIC_API_KEY não definida!
    echo   Configure a variável de ambiente antes de iniciar
    echo.
    echo   Windows (Prompt):
    echo   set ANTHROPIC_API_KEY=sk-...
    echo.
    echo   Windows (Permanente):
    echo   setx ANTHROPIC_API_KEY sk-...
    echo.
)

echo.
echo ════════════════════════════════════════════════════════════
echo      🚀 Iniciando KONECTA Intelligence Hub...
echo ════════════════════════════════════════════════════════════
echo.
echo ℹ️  Janela flutuante se abrirá em alguns segundos...
echo.

REM Executa aplicação
python app_central/main.py

echo.
echo ════════════════════════════════════════════════════════════
echo      Aplicação encerrada
echo ════════════════════════════════════════════════════════════
echo.

pause
