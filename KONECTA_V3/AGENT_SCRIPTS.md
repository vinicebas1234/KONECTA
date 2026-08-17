# 🤖 Scripts para Agents - KONECTA Intelligence Hub

Use cada script abaixo com o Orca. Copie, cole em "Create worktree" e envie para o agent apropriado.

---

## ⚠️ IMPORTANTE - LEIA ANTES DE COMEÇAR

**🔴 NÃO MEXER EM SIGNLAB!**

```
❌ PROIBIDO TOCAR:
  - C:\KONECTA\SIGNLAB/
  - Qualquer arquivo em SIGNLAB
  - Configurações do SIGNLAB
  - Banco de dados do SIGNLAB

✅ APENAS DESENVOLVER EM:
  - C:\KONECTA\KONECTA_V3/
  - Código Python em KONECTA_V3
  - Configurações de KONECTA_V3
  - Banco de dados de KONECTA_V3
```

**POR QUÊ?**
- SIGNLAB está funcionando perfeitamente em produção
- KONECTA V3 é a nova camada de reconhecimento
- SIGNLAB apenas treina e exporta modelos
- KONECTA V3 consome os modelos do SIGNLAB

---

---

## 🔵 CLAUDE (Architecture & Synthesis)

**Melhor habilidade:** Síntese, design, documentação, decisões arquiteturais

**Nome:** `claude-architecture-design`  
**Branch:** `develop`

```
Seu trabalho: Revisar e refinar a arquitetura do KONECTA Intelligence Hub

⚠️ IMPORTANTE:
- NÃO MEXER em C:\KONECTA\SIGNLAB
- SIGNLAB está funcionando, deixar como está
- Apenas revisar KONECTA_V3

CONTEXTO:
- Sistema de reconhecimento de Libras com múltiplas IAs
- Latência alvo: < 1 segundo
- Trabalho em equipe: você coordena, 3 colegas implementam motores

TAREFA:
1. Revisar arquivos:
   - C:\KONECTA\ARQUITETURA_INTEGRACAO.md
   - C:\KONECTA\APP_CENTRAL_ARQUITETURA.md

2. Validar decisões de design:
   - Pipeline paralelo é ótimo?
   - Decisão por confiança faz sentido?
   - Cache local está bem pensado?

3. Documentar possíveis problemas:
   - Gargalos potenciais
   - Trade-offs não explícitos
   - Riscos não considerados

4. Sugerir melhorias:
   - Simplicificações possíveis
   - Pontos de falha
   - Alternativas viáveis

5. Entregar:
   - ARCHITECTURE_REVIEW.md com findings
   - Recomendações prioritizadas
   - Diagrama alternativo (se tiver ideia melhor)

DEADLINE: Hoje
FORMATO: Markdown com exemplos de código onde aplicável
```

---

## 🟠 CODEX (Code Generation & Optimization)

**Melhor habilidade:** Gerar código otimizado, refatorar, performance

**Nome:** `codex-motor-optimization`  
**Branch:** `feature/motor-optimizations`

```
Seu trabalho: Otimizar e completar os motores KONECTA V3

⚠️ IMPORTANTE:
- NÃO MEXER em C:\KONECTA\SIGNLAB
- APENAS trabalhar em: C:\KONECTA\KONECTA_V3\app_central\motors\
- SIGNLAB já está pronto, só precisa usar seus modelos

CONTEXTO:
- Arquivo base: C:\KONECTA\KONECTA_V3\app_central\motors\motor_konecta_v3.py
- Objetivo: < 150ms latência
- Métrica: Maximizar FPS sem sacrificar acurácia

TAREFA:
1. Analisar motor_konecta_v3.py:
   - Encontrar gargalos
   - Identificar redundâncias
   - Otimizar loops

2. Implementar otimizações:
   - Cache de landmarks
   - Batch processing
   - Lazy loading de modelos
   - NumPy vectorization
   - GPU acceleration (opcional)

3. Adicionar benchmarking:
   - Função benchmark_performance()
   - Profiling de cada etapa
   - Comparação antes/depois

4. Testes:
   - Teste com 100 frames
   - Medir latência média, P95, P99
   - Validar acurácia não cai

5. Entregar:
   - motor_konecta_v3.py otimizado
   - performance_report.md
   - benchmark_results.json

RESTRIÇÕES:
- Não alterar API do motor
- Manter compatibilidade com MediaPipe
- Código deve rodar em CPU (GPU opcional)

DEADLINE: Hoje
```

---

## 🌐 GEMINI (Multimodal & Vision)

**Melhor habilidade:** Análise visual, processamento de imagem, validação

**Nome:** `gemini-vision-motor`  
**Branch:** `feature/gemini-vision-validation`

```
Seu trabalho: Implementar Motor Gemini Vision para validação

⚠️ IMPORTANTE:
- NÃO MEXER em C:\KONECTA\SIGNLAB
- APENAS em: C:\KONECTA\KONECTA_V3\app_central\motors\motor_gemini_vision.py
- Não tocar em SIGNLAB - ele já treina os modelos

CONTEXTO:
- Arquivo base: C:\KONECTA\KONECTA_V3\app_central\motors\motor_gemini_vision.py
- Objetivo: Validar qualidade de landmarks
- Latência: < 300ms

TAREFA:
1. Completar motor_gemini_vision.py:
   - Integração com Claude Vision API
   - Análise de qualidade do frame
   - Validação de landmarks visíveis
   - Detecção de iluminação

2. Implementar validações:
   - Frame quality score (0-100)
   - Hands visibility check
   - Lighting adequacy
   - Background noise detection

3. Testes visuais:
   - Testar com múltiplos cenários:
     * Luz boa, mãos claras
     * Luz ruim, ângulo ruim
     * Partes da mão fora do frame
   - Coletar métricas

4. Integração com pipeline:
   - Compatibilidade com recognizer_pipeline.py
   - Timeout handling
   - Error graceful degradation

5. Entregar:
   - motor_gemini_vision.py completo
   - test_gemini_vision.py
   - validation_metrics.json

RESTRIÇÕES:
- Não bloquear pipeline (timeout < 300ms)
- Falhar gracefully se Gemini indisponível
- Responder em formato JSON consistente

DEADLINE: Hoje
```

---

## 🔴 GROK (Context & Real-time Data)

**Melhor habilidade:** Contexto histórico, análise de padrões, dados em tempo real

**Nome:** `grok-context-engine`  
**Branch:** `feature/grok-context`

```
Seu trabalho: Implementar Motor Grok para análise de contexto

⚠️ IMPORTANTE:
- NÃO MEXER em C:\KONECTA\SIGNLAB
- APENAS em: C:\KONECTA\KONECTA_V3\app_central\motors\motor_grok_context.py
- SIGNLAB está funcionando, não precisa mudanças

CONTEXTO:
- Arquivo base: C:\KONECTA\KONECTA_V3\app_central\motors\motor_grok_context.py
- Objetivo: Enriquecer predições com contexto histórico
- Latência: < 1000ms

TAREFA:
1. Implementar cache de histórico:
   - Armazenar últimos 100 sinais por usuário
   - Índice rápido de acesso
   - TTL (expiração) configurável

2. Análise de padrões:
   - Identificar sequências comuns
   - Detectar mudanças de padrão
   - Calcular similaridade de sinais

3. Contexto temporal:
   - Hora do dia influencia sinais?
   - Padrões por sessão?
   - Histórico de erros

4. Função de votação:
   - Quando confiança < 0.7:
     * Buscar sinais similares no histórico
     * Votação ponderada
     * Retornar top-3 candidatos

5. Entregar:
   - motor_grok_context.py completo
   - test_grok_context.py
   - pattern_analysis_demo.py

RESTRIÇÕES:
- Cache em memória (RAM < 500MB)
- Acesso O(1) ao histórico
- Fallback se histórico vazio

DEADLINE: Hoje
```

---

## 💎 OPENCODE (Quick Fixes & Refactoring)

**Melhor habilidade:** Refatoração rápida, fixes, code review

**Nome:** `opencode-code-cleanup`  
**Branch:** `chore/code-quality`

```
Seu trabalho: Limpeza e refatoração de código

⚠️ IMPORTANTE:
- NÃO MEXER em C:\KONECTA\SIGNLAB
- APENAS em: C:\KONECTA\KONECTA_V3\app_central\
- SIGNLAB está pronto, deixar intocado

CONTEXTO:
- Diretório: C:\KONECTA\KONECTA_V3\app_central\
- Objetivo: Code quality, consistência, best practices
- Métrica: Pylint score > 8.0

TAREFA:
1. Code review em:
   - motors/*.py
   - pipeline/*.py
   - utils/*.py

2. Fixes prioritários:
   - Type hints missing
   - Docstrings incompletas
   - Import não usados
   - Variáveis mal nomeadas
   - Code duplication

3. Refatorações:
   - Extrair funções muito longas
   - Simplificar lógica condicional
   - Consolidar imports
   - Organizar estrutura

4. Testes:
   - Executar pylint em cada arquivo
   - mypy type checking
   - Verificar imports cíclicos

5. Entregar:
   - Código refatorado em todos os .py
   - code_quality_report.md
   - pylint_results.json

RESTRIÇÕES:
- Não mudar comportamento (refactoring only)
- Manter compatibilidade
- Todos testes devem passar

DEADLINE: Hoje
```

---

## 🟡 OPENCODE (Testing & QA)

**Melhor habilidade:** Testes, quality assurance, cobertura

**Nome:** `opencode-testing-suite`  
**Branch:** `feature/test-coverage`

```
Seu trabalho: Criar suite de testes completa

⚠️ IMPORTANTE:
- NÃO MEXER em C:\KONECTA\SIGNLAB
- APENAS testar: C:\KONECTA\KONECTA_V3\
- Testes para KONECTA V3 apenas

CONTEXTO:
- Projeto: KONECTA Intelligence Hub
- Framework: pytest
- Objetivo: 80%+ cobertura de código

TAREFA:
1. Testes para cada motor:
   - test_motor_konecta_v3.py
     * Mock de frames
     * Validar landmarks extraction
     * Testar classificação
   
   - test_motor_claude_logic.py
     * Mock de respostas Claude
     * Validar parsing JSON
     * Testar fallbacks
   
   - test_motor_gemini_vision.py
     * Mock de análises Gemini
     * Validar quality scores
     * Testar timeouts
   
   - test_motor_grok_context.py
     * Testar cache
     * Validar pattern matching
     * Testar votação

2. Testes de integração:
   - test_recognizer_pipeline.py
     * Fluxo HIGH confidence
     * Fluxo MEDIUM confidence
     * Fluxo LOW confidence
     * Timeout handling
     * Error recovery

3. Testes de performance:
   - Latência média < 1s
   - P95 latência < 1.5s
   - CPU < 40%
   - RAM < 2GB

4. Teste end-to-end:
   - Simular captura de câmera
   - Processar frames em sequência
   - Verificar histórico
   - Validar N8N webhooks

5. Entregar:
   - tests/ diretório completo
   - conftest.py com fixtures
   - test_coverage_report.html
   - CI/CD pipeline ready

RESTRIÇÕES:
- Todos testes devem rodar < 5min
- Mock all external APIs
- Fixtures reutilizáveis

DEADLINE: Hoje
```

---

## 🎨 CURSOR (IDE Integration & Quick Fixes)

**Melhor habilidade:** Edits locais rápidos, fixes pontuais, context-aware

**Nome:** `cursor-ui-polish`  
**Branch:** `feature/ui-improvements`

```
Seu trabalho: Polir interface PyQt5 e UX

⚠️ IMPORTANTE:
- NÃO MEXER em C:\KONECTA\SIGNLAB
- APENAS em: C:\KONECTA\KONECTA_V3\app_central\main.py
- Interface de KONECTA V3 apenas

CONTEXTO:
- Arquivo: C:\KONECTA\KONECTA_V3\app_central\main.py
- Objetivo: Interface profissional e intuitiva
- Target: Usuários pesquisadores

TAREFA:
1. Melhorias visuais:
   - Dark mode tema
   - Cores consistentes (gradient)
   - Ícones melhores
   - Responsividade

2. UX improvements:
   - Tooltips úteis
   - Mensagens de status claras
   - Loading indicators
   - Error messages friendly

3. Funcionalidades:
   - Settings dialog (editar config)
   - Export de métricas
   - Histórico exportável (CSV/JSON)
   - Atalhos de teclado

4. Temas:
   - Light mode
   - Dark mode
   - System preference

5. Testes manuais:
   - Testar em 1920x1080
   - Testar em 1366x768
   - Testar em 800x600 (janela pequena)
   - Testar em touch screen

6. Entregar:
   - main.py com melhorias
   - styles.qss (arquivo de estilos)
   - screenshot_demo.png
   - UX_IMPROVEMENTS.md

RESTRIÇÕES:
- Não alterar lógica de reconhecimento
- Manter performance (< 100ms render)
- Compatibilidade Windows/Linux/Mac

DEADLINE: Hoje
```

---

## 📊 OpenClaude (Backend & Infrastructure)

**Melhor habilidade:** Estrutura backend, banco de dados, APIs

**Nome:** `opencode-backend-setup`  
**Branch:** `feature/backend-infrastructure`

```
Seu trabalho: Setup de backend e infraestrutura

⚠️ IMPORTANTE:
- NÃO MEXER em C:\KONECTA\SIGNLAB
- APENAS em: C:\KONECTA\KONECTA_V3\app_backend\
- Backend de KONECTA V3 apenas

CONTEXTO:
- Projeto: KONECTA Intelligence Hub
- Objetivo: Backend robusto para produção
- Stack: FastAPI, SQLite/PostgreSQL

TAREFA:
1. Implementar banco de dados:
   - Schema SQL (signals, users, models)
   - Migrations (Alembic)
   - Índices para performance
   - Backup strategy

2. Criar APIs REST:
   - GET /api/health
   - POST /api/metrics
   - GET /api/signals?user_id=...
   - GET /api/models/available
   - POST /api/webhook/signal-recognized

3. Autenticação:
   - API key para N8N
   - Rate limiting
   - CORS configuration

4. Logging & Monitoring:
   - Structured logging (JSON)
   - Error tracking
   - Performance metrics
   - Health checks

5. Deployment:
   - Docker configuration
   - docker-compose.yml
   - Environment variables
   - Production checklist

6. Entregar:
   - app_backend/routes/*.py
   - migrations/
   - docker/
   - docker-compose.yml
   - README_BACKEND.md

RESTRIÇÕES:
- Zero downtime deployment support
- Backward compatible
- Scalable para múltiplos usuários

DEADLINE: Hoje
```

---

## 🚀 Como Usar

### Passo 1: Abra o Orca
```
File → Create worktree (ou Ctrl+Shift+W)
```

### Passo 2: Selecione o Agent
```
Agent: [Selecione o agent da lista]
```

### Passo 3: Cole o Script
```
Copie o script correspondente acima
Cole em "Name or 'Create From'"
```

### Passo 4: Configure
```
Project: KONECTA_V3
Run on: Local Windows
Branch: (conforme script)
```

### Passo 5: Envie
```
Clique em "Create worktree"
Agent começa a trabalhar!
```

---

## 📋 Ordem de Prioridade

Se quiser enviar em paralelo, use esta ordem:

**Imediato (hoje):**
1. ✅ CLAUDE - Architecture Review
2. ✅ CODEX - Motor Optimization
3. ✅ OPENCODE - Code Quality
4. ✅ OPENCODE - Testing Suite

**Próximo (amanhã):**
5. ✅ GEMINI - Vision Motor
6. ✅ GROK - Context Engine
7. ✅ CURSOR - UI Polish
8. ✅ OPENCODE - Backend Setup

---

## 🎯 Tracking de Progresso

Use este checklist para acompanhar:

```
CLAUDE (Architecture):
  [ ] Review de arquitetura
  [ ] Documento ARCHITECTURE_REVIEW.md
  [ ] Recomendações

CODEX (Optimization):
  [ ] Otimizações implementadas
  [ ] Benchmarks rodados
  [ ] Performance report

GEMINI (Vision):
  [ ] Motor Gemini completo
  [ ] Testes de validação
  [ ] Métricas

GROK (Context):
  [ ] Motor Grok completo
  [ ] Cache implementado
  [ ] Pattern analysis

OPENCODE-1 (Code):
  [ ] Refatoração completa
  [ ] Pylint score 8.0+
  [ ] Code review

OPENCODE-2 (Testing):
  [ ] 80%+ coverage
  [ ] Todos testes verdes
  [ ] Performance tests

CURSOR (UI):
  [ ] UI polida
  [ ] Temas funcionando
  [ ] Atalhos teclado

OPENCODE-3 (Backend):
  [ ] DB schema
  [ ] APIs REST
  [ ] Docker ready
```

---

**Próximo Passo:** Copie um script acima, abra o Orca, e mande! 🚀
