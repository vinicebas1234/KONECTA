# 🤖 Guia de Deploy Automático - KONECTA Agents

Três formas de fazer deploy automático dos agents! Escolha a que preferir.

---

## 🚀 Opção 1: Batch (Mais Simples)

Ideal para: Usuários Windows, sem experiência com scripts

### Como usar:

```bash
# No PowerShell/CMD, na pasta KONECTA_V3:
cd C:\KONECTA\KONECTA_V3
deploy_agents.bat
```

### O que faz:
1. Abre menu interativo
2. Você escolhe qual agent
3. Copia o script para clipboard automaticamente
4. Você abre Orca e cola

### Exemplo:
```
📋 Escolha um agent para deploy:
   1. 🔵 CLAUDE       - Architecture Review
   2. 🟠 CODEX        - Motor Optimization
   ...
   9. 🚀 TODOS (Deploy All)
   0. ❌ Sair

Digite sua escolha (0-9): 1

✅ Arquivo AGENT_SCRIPTS.md copiado!
```

---

## ⚡ Opção 2: PowerShell (Recomendado)

Ideal para: Usuários Windows com PowerShell

### Como usar:

```powershell
# Deploy um agent específico
cd C:\KONECTA\KONECTA_V3
.\deploy_agents.ps1 -Agent claude

# Deploy todos em paralelo
.\deploy_agents.ps1 -Agent all -Parallel

# Modo simulação (dry run)
.\deploy_agents.ps1 -Agent all -DryRun
```

### Opções disponíveis:

| Opção | Descrição |
|-------|-----------|
| `-Agent all` | Deploy todos os agents |
| `-Agent claude` | Deploy específico (claude, codex, gemini, grok, etc) |
| `-Parallel` | Executa em paralelo (mais rápido) |
| `-DryRun` | Simula sem executar |

### Exemplos:

```powershell
# Todos os agents em paralelo
.\deploy_agents.ps1 -Agent all -Parallel

# Apenas CLAUDE
.\deploy_agents.ps1 -Agent claude

# Simular tudo
.\deploy_agents.ps1 -Agent all -DryRun
```

### Se der erro de execução:

```powershell
# Permitir execução de scripts
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser

# Depois executar
.\deploy_agents.ps1 -Agent all
```

---

## 🐍 Opção 3: Python (Mais Funcional)

Ideal para: Desenvolvedores, controle fino

### Como usar:

```bash
# Deploy um agent
cd C:\KONECTA\KONECTA_V3
python deploy_agents.py --agent claude

# Deploy todos
python deploy_agents.py --agent all

# Menu interativo
python deploy_agents.py --interactive

# Simulação
python deploy_agents.py --agent all --dry-run
```

### Opções disponíveis:

```bash
python deploy_agents.py --help

usage: deploy_agents.py [-h] 
  [--agent {all,claude,codex,gemini,grok,opencode1,opencode2,cursor,opencode3}]
  [--dry-run] [--parallel] [--interactive]

optional arguments:
  -h, --help            show this help message
  --agent AGENT         Agent para deploy
  --dry-run             Simular sem executar
  --parallel            Deploy paralelo (beta)
  --interactive, -i     Modo interativo
```

### Exemplos:

```bash
# Modo interativo (menu)
python deploy_agents.py -i

# Deploy com feedback colorido
python deploy_agents.py --agent all

# Simular primeiro
python deploy_agents.py --agent all --dry-run

# Depois executar
python deploy_agents.py --agent all
```

---

## 📊 Comparação dos 3 Scripts

| Aspecto | Batch | PowerShell | Python |
|---------|-------|-----------|--------|
| **Facilidade** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Funcionalidades** | Básica | Avançada | Máxima |
| **Plataforma** | Windows | Windows | Windows/Mac/Linux |
| **Velocidade** | Rápido | Muito rápido | Rápido |
| **Paralelo** | ❌ | ✅ | ✅ (beta) |
| **Dry Run** | ❌ | ✅ | ✅ |
| **Requer setup** | ❌ | ⚠️ Policy | ⚠️ Python |

---

## ⚠️ IMPORTANTE: Workflow Correto

Qualquer que seja o script que usar, o fluxo é:

```
1️⃣ Executar script
   └─ Script copia o conteúdo para clipboard

2️⃣ Abrir Orca
   └─ C:\Users\vrsantos\.claude\orca

3️⃣ Create Worktree
   └─ Ctrl+Shift+W (ou UI)

4️⃣ Configurar:
   ├─ Project: KONECTA_V3
   ├─ Branch: (automático do script)
   ├─ Agent: (Claude, Codex, etc)
   └─ "Name or 'Create From'": Cole aqui (Ctrl+V)

5️⃣ Create
   └─ Clique "Create worktree"

6️⃣ Esperar
   └─ Agent começa a trabalhar!
```

---

## 🎯 Meu Recomendado

Para máxima simplicidade:

```bash
# Use o Batch
deploy_agents.bat
```

Ele vai:
1. Mostrar menu bonito
2. Você escolhe o agent
3. Copia automaticamente
4. Você cola no Orca

---

## 🔄 Deploy Múltiplos Agents

### Sequencial (um de cada vez):

```bash
# Batch
deploy_agents.bat
# Escolhe 1
# Depois executa novamente para o próximo

# PowerShell
.\deploy_agents.ps1 -Agent claude
.\deploy_agents.ps1 -Agent codex
# etc...

# Python
python deploy_agents.py -i
# Usa menu interativo
```

### Paralelo (todos de uma vez):

```powershell
# Apenas PowerShell suporta
.\deploy_agents.ps1 -Agent all -Parallel
```

---

## 📋 Troubleshooting

### Erro: "Script não pode ser carregado"

**Solução:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Erro: "Python não encontrado"

**Solução:**
- Instale Python: https://python.org
- Ou use Batch/PowerShell

### Script não copia para clipboard

**Solução:**
- Windows: Abre arquivo AGENT_SCRIPTS.md manualmente
- Linux: Instale `xclip` ou `xsel`
- macOS: Funciona nativamente

### Orca não encontra a worktree

**Reticências:**
1. Verifique se Orca está rodando
2. Confirme que KONECTA_V3 é um projeto Git
3. Tente colar manualmente no Orca

---

## 🚀 Quick Start (30 segundos)

```bash
# 1. Abra PowerShell em KONECTA_V3
cd C:\KONECTA\KONECTA_V3

# 2. Execute deploy de todos
powershell -Command "Set-ExecutionPolicy Bypass -Scope Process; .\deploy_agents.ps1 -Agent all"

# 3. Abra Orca
# C:\Users\vrsantos\.claude\orca

# 4. Cole script (Ctrl+V) em cada worktree

# Pronto! ✅
```

---

## 📞 Ajuda

Qual script usar?

- **Windows, sem experiência?** → `deploy_agents.bat`
- **Windows, PowerShell?** → `.\deploy_agents.ps1`
- **Controle fino?** → `python deploy_agents.py`
- **Mac/Linux?** → `python deploy_agents.py` (colha Python antes)

---

## 🎉 Resultado Final

Todos os 8 agents deployados e trabalhando:

```
✅ CLAUDE       → Revisando arquitetura
✅ CODEX        → Otimizando motores  
✅ GEMINI       → Implementando Vision
✅ GROK         → Context Engine
✅ OPENCODE #1  → Code quality
✅ OPENCODE #2  → Testes
✅ CURSOR       → UI Polish
✅ OPENCODE #3  → Backend setup
```

Tudo em paralelo, sem bloquear nada! 🚀

---

**Criado:** 2026-08-11  
**Status:** Pronto para uso  
**Feedback:** Veja AGENT_SCRIPTS.md
