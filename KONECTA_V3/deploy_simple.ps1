# KONECTA Intelligence Hub - Deploy Simples
# Versao ultra-simples que copia para clipboard

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "KONECTA Intelligence Hub - Deploy" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "ATENCAO: NAO MEXER EM SIGNLAB!" -ForegroundColor Yellow
Write-Host "Trabalhar APENAS em KONECTA_V3" -ForegroundColor Yellow
Write-Host ""

Write-Host "Opcoes:" -ForegroundColor Green
Write-Host "1. CLAUDE"
Write-Host "2. CODEX"
Write-Host "3. GEMINI"
Write-Host "4. GROK"
Write-Host "5. OPENCODE #1"
Write-Host "6. OPENCODE #2"
Write-Host "7. CURSOR"
Write-Host "8. OPENCODE #3"
Write-Host "9. TODOS os agents"
Write-Host "0. Sair"
Write-Host ""

$choice = Read-Host "Digite sua escolha (0-9)"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$AgentFile = Join-Path $ScriptDir "AGENT_SCRIPTS.md"

if (-not (Test-Path $AgentFile)) {
    Write-Host "ERRO: AGENT_SCRIPTS.md nao encontrado!" -ForegroundColor Red
    exit 1
}

$content = Get-Content $AgentFile -Raw

switch ($choice) {
    "0" {
        Write-Host "Saindo..." -ForegroundColor Yellow
        exit 0
    }
    "1" {
        Write-Host "Copiando CLAUDE..." -ForegroundColor Green
        $content | Set-Clipboard
        Write-Host "OK! Cole no Orca (Ctrl+V)" -ForegroundColor Green
    }
    "2" {
        Write-Host "Copiando CODEX..." -ForegroundColor Green
        $content | Set-Clipboard
        Write-Host "OK! Cole no Orca (Ctrl+V)" -ForegroundColor Green
    }
    "3" {
        Write-Host "Copiando GEMINI..." -ForegroundColor Green
        $content | Set-Clipboard
        Write-Host "OK! Cole no Orca (Ctrl+V)" -ForegroundColor Green
    }
    "4" {
        Write-Host "Copiando GROK..." -ForegroundColor Green
        $content | Set-Clipboard
        Write-Host "OK! Cole no Orca (Ctrl+V)" -ForegroundColor Green
    }
    "5" {
        Write-Host "Copiando OPENCODE #1..." -ForegroundColor Green
        $content | Set-Clipboard
        Write-Host "OK! Cole no Orca (Ctrl+V)" -ForegroundColor Green
    }
    "6" {
        Write-Host "Copiando OPENCODE #2..." -ForegroundColor Green
        $content | Set-Clipboard
        Write-Host "OK! Cole no Orca (Ctrl+V)" -ForegroundColor Green
    }
    "7" {
        Write-Host "Copiando CURSOR..." -ForegroundColor Green
        $content | Set-Clipboard
        Write-Host "OK! Cole no Orca (Ctrl+V)" -ForegroundColor Green
    }
    "8" {
        Write-Host "Copiando OPENCODE #3..." -ForegroundColor Green
        $content | Set-Clipboard
        Write-Host "OK! Cole no Orca (Ctrl+V)" -ForegroundColor Green
    }
    "9" {
        Write-Host "Copiando TODOS os agents..." -ForegroundColor Green
        $content | Set-Clipboard
        Write-Host "OK! Cole no Orca (Ctrl+V)" -ForegroundColor Green
    }
    default {
        Write-Host "Opcao invalida!" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "PRONTO!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Proximos passos:" -ForegroundColor Cyan
Write-Host "1. Abra Orca (Ctrl+Shift+W no VS Code)"
Write-Host "2. Crie worktree"
Write-Host "3. Cole script (Ctrl+V)"
Write-Host "4. Click Create worktree"
Write-Host ""
