#!/bin/bash

echo ""
echo "════════════════════════════════════════════════════════════"
echo "     KONECTA Intelligence Hub - Inicialização"
echo "════════════════════════════════════════════════════════════"
echo ""

# Diretório do script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Verifica Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 não encontrado! Instale Python 3.10+"
    exit 1
fi

echo "✅ Python encontrado"

# Cria ambiente virtual se não existir
if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Erro ao criar venv"
        exit 1
    fi
    echo "✅ Ambiente virtual criado"
fi

# Ativa venv
echo "🔄 Ativando ambiente virtual..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "❌ Erro ao ativar venv"
    exit 1
fi

# Instala dependências
echo "📥 Verificando dependências..."
pip install -q -r requirements.txt
if [ $? -ne 0 ]; then
    echo "⚠️ Erro ao instalar dependências"
    exit 1
fi

echo "✅ Dependências OK"

# Cria diretórios
mkdir -p logs data cache models/v1

# Verifica API keys
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️ ANTHROPIC_API_KEY não definida!"
    echo "  Configure antes de iniciar:"
    echo ""
    echo "  export ANTHROPIC_API_KEY=sk-..."
    echo ""
fi

# Verifica modelos
if [ ! -f "models/v1/classifier.joblib" ]; then
    echo "⚠️ Modelos não encontrados em models/v1"
    echo "  Copie os arquivos do SIGNLAB:"
    echo "  - classifier.joblib"
    echo "  - metadata.json"
    echo "  - sequence_model.keras (opcional)"
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "     🚀 Iniciando KONECTA Intelligence Hub..."
echo "════════════════════════════════════════════════════════════"
echo ""
echo "ℹ️  Janela flutuante se abrirá em alguns segundos..."
echo ""

# Executa aplicação
python3 app_central/main.py

echo ""
echo "════════════════════════════════════════════════════════════"
echo "     Aplicação encerrada"
echo "════════════════════════════════════════════════════════════"
echo ""
