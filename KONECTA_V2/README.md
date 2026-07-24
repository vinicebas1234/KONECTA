# KONECTA V2

Plataforma de pesquisa em Inteligencia Artificial aplicada ao reconhecimento de Libras.

A V2 nao substitui a versao atual: a V1 permanece intacta na raiz do repositorio
(`OCR/`, `LSAE-repo/`, etc.) e serve apenas como referencia de regras de negocio.
Todo o desenvolvimento novo acontece exclusivamente dentro desta pasta.

## Arquitetura

```
Capture Engine -> Tracking Engine -> Dataset Engine -> Knowledge Engine
    -> AI Research Assistant -> AI Engine -> LSAE Engine -> Interface / API
```

O fluxo central da V2: antes de qualquer treinamento, o **Knowledge Engine**
analisa, valida e documenta o dataset. O **AI Research Assistant** (LLMs como
Claude, GPT, Gemini ou modelos locais) interpreta essas analises para o
pesquisador — a IA generativa **nunca** reconhece sinais; o reconhecimento e
responsabilidade dos modelos treinados no proprio KONECTA.

## Estrutura

| Pasta | Responsabilidade |
|---|---|
| `backend/` | API FastAPI + WebSocket (etapa 3 do roadmap) |
| `frontend/` | Interface web React + Tailwind + Framer Motion (etapa 2) |
| `core/` | Tipos e contratos compartilhados entre os motores |
| `knowledge/` | Knowledge Engine — analise de datasets, perfis, qualidade, recomendacoes |
| `training/` | Pipelines de treinamento (AI Engine) |
| `lsae/` | LSAE Engine — geracao sintetica biomecanica |
| `models/` | Modelos treinados e artefatos |
| `datasets/` | Datasets e versionamento logico |
| `tests/` | Testes automatizados |
| `docs/` | Documentacao de arquitetura e decisoes |
| `configs/` | Configuracoes (limiares de qualidade, regras, provedores de IA) |
| `scripts/` | Scripts utilitarios e CLIs |

## Status

- [x] Etapa 1 — Arquitetura do projeto (estrutura, tipos, contratos do Knowledge Engine)
- [x] Etapa 2 — Interface Web (React + Tailwind + Framer Motion)
- [x] Etapa 3 — Backend (FastAPI + WebSocket)
- [ ] Etapas 4+ — ver [docs/03_ROADMAP.md](docs/03_ROADMAP.md)

## Executando

Dependências (uma só vez):

```
pip install -r requirements.txt
```

**Configuração do AI Research Assistant** (opcional, necessário para os botões de IA):

Se quiser usar Claude para interpretar as análises, configure a variável de ambiente com sua API key:

```powershell
$env:ANTHROPIC_API_KEY = "sua-chave-de-api-aqui"
```

Ou crie um arquivo `.env` e carregue-o manualmente (em desenvolvimento).

Backend (da pasta `KONECTA_V2`):

```
.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000
```

Frontend (dev server na porta 5173, com proxy para a API):

```
cd frontend && npm run dev
```

A interface permite:
- Analisar o dataset real da V1 (somente leitura de `OCR/dados_libras`) ou um dataset sintético de demonstração
- Progresso do Knowledge Engine transmitido via WebSocket
- **Três botões de AI Research Assistant (Claude)**: "Interpretar com IA", "Priorizar coletas", "Próximos passos"

Testes:

```
.venv\Scripts\python tests\test_knowledge_smoke.py
.venv\Scripts\python tests\test_api_smoke.py
```
