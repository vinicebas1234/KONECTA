# KONECTA Intelligence Hub - Deploy Agents
# Script PowerShell simples para deploy automatico

param(
    [ValidateSet('all', 'claude', 'codex', 'gemini', 'grok', 'opencode1', 'opencode2', 'cursor', 'opencode3')]
    [string]$Agent = 'all',
    [switch]$DryRun
)

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$AgentScriptsFile = Join-Path $ScriptRoot "AGENT_SCRIPTS.md"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "KONECTA Intelligence Hub - Deploy" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar arquivo
if (-not (Test-Path $AgentScriptsFile)) {
    Write-Host "ERRO: AGENT_SCRIPTS.md nao encontrado" -ForegroundColor Red
    exit 1
}

Write-Host "Lendo AGENT_SCRIPTS.md..." -ForegroundColor Blue

$content = Get-Content $AgentScriptsFile -Raw

# Define agents
$agents = @{
    'claude' = 'develop'
    'codex' = 'feature/motor-optimizations'
    'gemini' = 'feature/gemini-vision-validation'
    'grok' = 'feature/grok-context'
    'opencode1' = 'chore/code-quality'
    'opencode2' = 'feature/test-coverage'
    'cursor' = 'feature/ui-improvements'
    'opencode3' = 'feature/backend-infrastructure'
}

function Get-AgentScript {
    param([string]$AgentName)

    $pattern = "## .*$AgentName.*?``````\r`n(.*?)``````"

    if ($content -match $pattern) {
        return $matches[1].Trim()
    }

    return $null
}

function Deploy-Agent {
    param([string]$AgentName, [string]$Branch)

    $script = Get-AgentScript $AgentName

    if (-not $script) {
        Write-Host "PULANDO: $AgentName (nao encontrado)" -ForegroundColor Yellow
        return
    }

    Write-Host ""
    Write-Host "Deployando: $AgentName" -ForegroundColor Green
    Write-Host "Branch: $Branch" -ForegroundColor Blue
    Write-Host "Tamanho: $($script.Length) caracteres" -ForegroundColor Blue

    if ($DryRun) {
        Write-Host "DRY RUN - Nao vai copiar" -ForegroundColor Yellow
        return
    }

    # Copia para clipboard
    $script | Set-Clipboard
    Write-Host "OK - Script copiado para clipboard!" -ForegroundColor Green
}

# Deploy
Write-Host ""
Write-Host "ATENCAO: NAO MEXER EM SIGNLAB!" -ForegroundColor Yellow
Write-Host "Trabalhar APENAS em KONECTA_V3" -ForegroundColor Yellow
Write-Host ""

if ($Agent -eq 'all') {
    Write-Host "Deployando TODOS os agents..." -ForegroundColor Green
    Write-Host ""

    foreach ($agentName in $agents.Keys) {
        Deploy-Agent -AgentName $agentName -Branch $agents[$agentName]
    }
}
else {
    if ($agents.ContainsKey($Agent)) {
        Deploy-Agent -AgentName $Agent -Branch $agents[$Agent]
    }
    else {
        Write-Host "Agent nao encontrado: $Agent" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "PRONTO!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Proximos passos:" -ForegroundColor Cyan
Write-Host "1. Abra Orca (Ctrl+Shift+W)"
Write-Host "2. Crie worktree"
Write-Host "3. Cole script (Ctrl+V ja esta no clipboard)"
Write-Host "4. Click Create worktree"
Write-Host ""
