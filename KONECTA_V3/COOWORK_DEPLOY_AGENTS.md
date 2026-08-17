# 🤖 KONECTA Intelligence Hub - Deploy Agents via Orca

**Para:** Seu Coowork / Equipe de Desenvolvimento  
**Data:** 2026-08-11  
**Status:** Pronto para produção

---

## 📋 IMPORTANTE - LEIA PRIMEIRO

### ⚠️ Regra #1: NÃO MEXER EM SIGNLAB

```
❌ PROIBIDO:
  • C:\KONECTA\SIGNLAB\
  • Qualquer arquivo em SIGNLAB
  • Banco de dados do SIGNLAB

✅ APENAS DESENVOLVER:
  • C:\KONECTA\KONECTA_V3\
  • Todo código novo em KONECTA_V3
```

SIGNLAB já está funcionando em produção. Deixar intocado!

---

## 🎯 Objetivo

Deploy automático de **8 agents** via Orca para desenvolver o **KONECTA Intelligence Hub** em paralelo.

```
✅ CLAUDE       → Revisar arquitetura
✅ CODEX        → Otimizar motores
✅ GEMINI       → Implementar Vision
✅ GROK         → Context Engine
✅ OPENCODE #1  → Code Quality
✅ OPENCODE #2  → Testing Suite
✅ CURSOR       → UI Polish
✅ OPENCODE #3  → Backend Setup
```

---

## 🚀 Passo a Passo (Super Simples)

### Passo 1: Abra PowerShell

```
Windows:
  • Win + X
  • Selecione "PowerShell"
  ou
  • Abra terminal no VS Code
```

### Passo 2: Navegue para pasta

```powershell
cd C:\KONECTA\KONECTA_V3
```

### Passo 3: Execute o script

**Para um agent específico:**

```powershell
# CLAUDE
.\extract_agent.ps1 claude

# CODEX
.\extract_agent.ps1 codex

# GEMINI
.\extract_agent.ps1 gemini

# GROK
.\extract_agent.ps1 grok

# OPENCODE #1
.\extract_agent.ps1 opencode1

# OPENCODE #2
.\extract_agent.ps1 opencode2

# CURSOR
.\extract_agent.ps1 cursor

# OPENCODE #3
.\extract_agent.ps1 opencode3
```

**Para menu interativo:**

```powershell
.\extract_agent.ps1
# Escolha 1-8 no menu
```

### Passo 4: Script copia para clipboard

O PowerShell vai exibir:

```
========================================
Agent: claude
Tamanho: XXXX caracteres
========================================

OK! Script do claude copiado!

AGORA:
1. Abra Orca (Ctrl+Shift+W)
2. Crie worktree
3. Cole aqui (Ctrl+V):
   - Campo: 'Name or Create From'
4. Click 'Create worktree'
```

### Passo 5: Abra Orca

**No VS Code:**
- Ctrl + Shift + W
- Ou use o menu da esquerda

### Passo 6: Create Worktree

No Orca:
```
1. Clique em "Create worktree"
2. Configure:
   • Project: KONECTA_V3
   • Run on: Local Windows
   • Agent: Claude (ou o que escolheu)
3. No campo "Name or 'Create From'": Cole (Ctrl+V)
4. Click "Create worktree"
```

### Passo 7: Pronto! ✅

Agent começa a trabalhar automaticamente!

---

## 📋 Checklist de Deploy

Para cada agent, siga:

```markdown
## CLAUDE - Architecture Review

- [ ] PowerShell: .\extract_agent.ps1 claude
- [ ] Script copiado para clipboard
- [ ] Orca aberto (Ctrl+Shift+W)
- [ ] Create worktree clicado
- [ ] Colei o script (Ctrl+V)
- [ ] Worktree criada com sucesso
- [ ] Agent começou a trabalhar
- [ ] ✅ COMPLETO

---

## CODEX - Motor Optimization

- [ ] PowerShell: .\extract_agent.ps1 codex
- [ ] Script copiado para clipboard
- [ ] Orca aberto
- [ ] Create worktree
- [ ] Colei (Ctrl+V)
- [ ] ✅ COMPLETO

---

## GEMINI - Vision Motor

- [ ] PowerShell: .\extract_agent.ps1 gemini
- [ ] Script copiado
- [ ] Orca aberto
- [ ] Create worktree
- [ ] Colei (Ctrl+V)
- [ ] ✅ COMPLETO

---

## GROK - Context Engine

- [ ] PowerShell: .\extract_agent.ps1 grok
- [ ] Script copiado
- [ ] Orca aberto
- [ ] Create worktree
- [ ] Colei (Ctrl+V)
- [ ] ✅ COMPLETO

---

## OPENCODE #1 - Code Quality

- [ ] PowerShell: .\extract_agent.ps1 opencode1
- [ ] Script copiado
- [ ] Orca aberto
- [ ] Create worktree
- [ ] Colei (Ctrl+V)
- [ ] ✅ COMPLETO

---

## OPENCODE #2 - Testing Suite

- [ ] PowerShell: .\extract_agent.ps1 opencode2
- [ ] Script copiado
- [ ] Orca aberto
- [ ] Create worktree
- [ ] Colei (Ctrl+V)
- [ ] ✅ COMPLETO

---

## CURSOR - UI Polish

- [ ] PowerShell: .\extract_agent.ps1 cursor
- [ ] Script copiado
- [ ] Orca aberto
- [ ] Create worktree
- [ ] Colei (Ctrl+V)
- [ ] ✅ COMPLETO

---

## OPENCODE #3 - Backend Setup

- [ ] PowerShell: .\extract_agent.ps1 opencode3
- [ ] Script copiado
- [ ] Orca aberto
- [ ] Create worktree
- [ ] Colei (Ctrl+V)
- [ ] ✅ COMPLETO
```

---

## ⚡ Quick Command (Copie e Cole)

### Deploy CLAUDE:
```powershell
cd C:\KONECTA\KONECTA_V3; .\extract_agent.ps1 claude
```

### Deploy CODEX:
```powershell
cd C:\KONECTA\KONECTA_V3; .\extract_agent.ps1 codex
```

### Deploy GEMINI:
```powershell
cd C:\KONECTA\KONECTA_V3; .\extract_agent.ps1 gemini
```

### Deploy GROK:
```powershell
cd C:\KONECTA\KONECTA_V3; .\extract_agent.ps1 grok
```

### Deploy OPENCODE #1:
```powershell
cd C:\KONECTA\KONECTA_V3; .\extract_agent.ps1 opencode1
```

### Deploy OPENCODE #2:
```powershell
cd C:\KONECTA\KONECTA_V3; .\extract_agent.ps1 opencode2
```

### Deploy CURSOR:
```powershell
cd C:\KONECTA\KONECTA_V3; .\extract_agent.ps1 cursor
```

### Deploy OPENCODE #3:
```powershell
cd C:\KONECTA\KONECTA_V3; .\extract_agent.ps1 opencode3
```

---

## 🐛 Troubleshooting

### Erro: "Script não pode ser executado"

**Solução:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Depois execute novamente:
```powershell
.\extract_agent.ps1 claude
```

---

### Erro: "Arquivo não encontrado"

**Solução:**
1. Verifique se está na pasta correta:
```powershell
cd C:\KONECTA\KONECTA_V3
ls  # Deve listar extract_agent.ps1
```

2. Se não encontrar, clone/baixe novamente de:
```
https://github.com/seu-repo/KONECTA
```

---

### Erro no Orca: "Couldn't create worktree"

**Solução:**
1. Verifique se é KONECTA_V3 é um repo Git:
```powershell
cd C:\KONECTA\KONECTA_V3
git status  # Deve funcionar
```

2. Se não funcionar, reinicialize:
```powershell
git init
```

---

### Erro: "Agent não encontrado"

**Solução:**
Verifique o nome exato:
```
claude    (não CLAUDE ou Claude)
codex     (não CODEX)
gemini    (não GEMINI)
grok      (não GROK)
opencode1 (não opencode-1 ou OPENCODE1)
opencode2
opencode3
cursor    (não CURSOR)
```

---

## 📊 Status de Deploy

Acompanhe aqui:

```markdown
| Agent | Status | Data | Responsável |
|-------|--------|------|-------------|
| CLAUDE | ⏳ Em progresso | 2026-08-11 | - |
| CODEX | ⏳ Em progresso | 2026-08-11 | - |
| GEMINI | ⏳ Em progresso | 2026-08-11 | - |
| GROK | ⏳ Em progresso | 2026-08-11 | - |
| OPENCODE #1 | ⏳ Em progresso | 2026-08-11 | - |
| OPENCODE #2 | ⏳ Em progresso | 2026-08-11 | - |
| CURSOR | ⏳ Em progresso | 2026-08-11 | - |
| OPENCODE #3 | ⏳ Em progresso | 2026-08-11 | - |
```

Atualize com:
- ⏳ Em progresso
- ✅ Completo
- ❌ Erro (especificar)

---

## 💡 Dicas Importantes

### Dica 1: Copiar/Colar
- O script **copia automaticamente** para clipboard
- Não precisa copiar manualmente
- Só colar (Ctrl+V) no Orca

### Dica 2: Um por Um
- Deploy **um agent por vez**
- Não tente todos simultaneamente
- Espere um terminar antes do próximo

### Dica 3: Branches Diferentes
Cada agent usa uma branch diferente:
- claude → `develop`
- codex → `feature/motor-optimizations`
- gemini → `feature/gemini-vision-validation`
- grok → `feature/grok-context`
- opencode1 → `chore/code-quality`
- opencode2 → `feature/test-coverage`
- cursor → `feature/ui-improvements`
- opencode3 → `feature/backend-infrastructure`

### Dica 4: Não Delete Branches
- Deixe todas as branches ativas
- Cada uma é um agent trabalhando
- Merge apenas quando agent terminar

---

## ✅ Validação Final

Depois de tudo deployado:

```markdown
- [ ] Todos os 8 agents criados em Orca
- [ ] Cada um com sua worktree
- [ ] Nenhum erro de "Couldn't create"
- [ ] Agents começaram a trabalhar
- [ ] Branches diferentes confirmadas
- [ ] Status atualizado neste documento
```

---

## 🎉 Resultado Final

```
KONECTA Intelligence Hub v1.0
✅ CLAUDE       - Arquitetura revisada
✅ CODEX        - Motores otimizados
✅ GEMINI       - Vision implementado
✅ GROK         - Context Engine pronto
✅ OPENCODE #1  - Código limpo
✅ OPENCODE #2  - Testes 80%+
✅ CURSOR       - UI polida
✅ OPENCODE #3  - Backend completo

TOTAL: 8 agents trabalhando em paralelo! 🚀
```

---

## 📞 Contato / Dúvidas

Se tiver erro:
1. Leia a seção "Troubleshooting"
2. Verifique o nome do agent (case-sensitive)
3. Confirme que está em C:\KONECTA\KONECTA_V3
4. Tente novamente

---

## 📝 Notas

- Documento criado: 2026-08-11
- Versão: 1.0.0
- Status: Pronto para uso
- Testado em: Windows PowerShell
- Compatibilidade: Orca CLI

**LEMBRE-SE: NÃO MEXER EM SIGNLAB! 🚫**

---

Última atualização: 2026-08-11
