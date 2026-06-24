# Script para executar Libras OCR com variáveis de ambiente

$KONECTA_PATH = Split-Path -Parent $MyInvocation.MyCommand.Path
$LIBRAS_BASE_DIR = Join-Path $KONECTA_PATH "OCR"
$VENV_PYTHON = Join-Path $LIBRAS_BASE_DIR ".venv2\Scripts\python.exe"

Write-Host ""
Write-Host "========================================"
Write-Host "  Libras OCR - Sistema de Reconhecimento"
Write-Host "========================================"
Write-Host ""
Write-Host "LIBRAS_BASE_DIR: $LIBRAS_BASE_DIR"
Write-Host ""

# Verifica se venv existe
if (-not (Test-Path $VENV_PYTHON)) {
    Write-Host "ERRO: Ambiente virtual nao encontrado em $LIBRAS_BASE_DIR\.venv2" -ForegroundColor Red
    Write-Host "Por favor, crie o ambiente virtual primeiro." -ForegroundColor Yellow
    Read-Host "Pressione ENTER para sair"
    exit 1
}

# Define variáveis de ambiente
$env:LIBRAS_BASE_DIR = $LIBRAS_BASE_DIR
$env:PYTHONPATH = $LIBRAS_BASE_DIR

# Executa
Write-Host "Iniciando aplicacao..." -ForegroundColor Green
Write-Host ""

Set-Location $LIBRAS_BASE_DIR
& $VENV_PYTHON libras_recognizer.py

Read-Host "Pressione ENTER para sair"
