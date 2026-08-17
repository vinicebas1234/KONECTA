# KONECTA - Extrai um agent de cada vez

param([string]$AgentName = "")

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$AgentFile = Join-Path $ScriptDir "AGENT_SCRIPTS.md"

if (-not (Test-Path $AgentFile)) {
    Write-Host "ERRO: AGENT_SCRIPTS.md nao encontrado!" -ForegroundColor Red
    exit 1
}

if (-not $AgentName) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "KONECTA - Extrair Agent" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Qual agent?"
    Write-Host "1. claude"
    Write-Host "2. codex"
    Write-Host "3. gemini"
    Write-Host "4. grok"
    Write-Host "5. opencode1"
    Write-Host "6. opencode2"
    Write-Host "7. cursor"
    Write-Host "8. opencode3"
    Write-Host ""

    $choice = Read-Host "Digite (1-8 ou nome)"

    $agentMap = @{
        "1" = "claude"
        "2" = "codex"
        "3" = "gemini"
        "4" = "grok"
        "5" = "opencode1"
        "6" = "opencode2"
        "7" = "cursor"
        "8" = "opencode3"
    }

    if ($agentMap.ContainsKey($choice)) {
        $AgentName = $agentMap[$choice]
    } else {
        $AgentName = $choice
    }
}

# Lê arquivo
$content = Get-Content $AgentFile -Raw

# Encontra o agent (busca por ## seguido do nome)
if ($content -match "## .*?$AgentName.*?``````\s+(.*?)```") {
    $script = $matches[1].Trim()

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Agent: $AgentName" -ForegroundColor Green
    Write-Host "Tamanho: $($script.Length) caracteres" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""

    # Copia apenas o script
    $script | Set-Clipboard

    Write-Host "OK! Script do $AgentName copiado!" -ForegroundColor Green
    Write-Host ""
    Write-Host "AGORA:" -ForegroundColor Cyan
    Write-Host "1. Abra Orca (Ctrl+Shift+W)"
    Write-Host "2. Crie worktree"
    Write-Host "3. Cole aqui (Ctrl+V):"
    Write-Host "   - Campo: 'Name or Create From'"
    Write-Host "4. Click 'Create worktree'"
    Write-Host ""
} else {
    Write-Host "ERRO: Agent '$AgentName' nao encontrado!" -ForegroundColor Red
    exit 1
}
