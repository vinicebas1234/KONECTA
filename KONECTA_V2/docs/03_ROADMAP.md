# Roadmap de Migracao — KONECTA V2

A reconstrucao ocorre por etapas. Cada modulo da V2 e desenvolvido de forma
independente da V1; somente apos validacao ocorre a migracao de
funcionalidades. A V1 serve apenas como referencia de regras de negocio.

| # | Etapa | Status | Observacoes |
|---|---|---|---|
| 1 | Arquitetura do projeto | **Concluida** | Estrutura de pastas, tipos em `core/`, contratos e implementacao inicial do Knowledge Engine |
| 2 | Interface Web | **Concluida** | React + Tailwind + Framer Motion em `frontend/`: dashboard, qualidade, perfis, recomendacoes e relatorio |
| 3 | Backend | **Concluida** | FastAPI + WebSocket em `backend/`: REST (`/api/*`) + progresso em tempo real (`/ws/analise`); adaptador somente leitura do dataset V1 |
| 4 | Capture Engine | **Iniciada** | Captura de vídeo (webcam/arquivo) + validação de iluminação e movimento |
| 5 | MediaPipe Engine | **Iniciada** | Extração de landmarks (mãos + corpo) com fallback gracioso |
| 6 | Tracking Engine | Pendente | Define o layout de pontos (destrava dominancia e "principal diferenca") |
| 7 | Dataset Engine | **Concluida** | Abstração de fontes (V1 dinâmicos, V1 estáticos, sintético) com cache thread-safe; todo dataset loading centralizado |
| 8 | Knowledge Engine | **Iniciada** | Nucleo implementado na etapa 1; evoluir junto com as etapas 4-7 |
| 9 | AI Engine | Pendente | Treinamento/avaliacao; exporta metricas para o AI Research Assistant |
| 10 | LSAE Engine | Pendente | Consome perfis do Knowledge Engine |
| 11 | Avaliacao | Pendente | Cross-signer, matriz de confusao realimentando `taxa_confusao` |
| 12 | Testes | Iniciada | Smoke test do Knowledge Engine em `tests/` |
| 13 | Migracao dos modelos existentes | Pendente | Modelos da V1 (`OCR/modelos`) |

## Proximos passos imediatos

1. Etapa 4 — Capture Engine (captura de video; destrava os checks visuais
   de qualidade).
2. Etapa 7 — Dataset Engine: definir o formato de armazenamento da V2 e
   absorver o adaptador de leitura da V1 que hoje vive em
   `backend/services/dataset_provider.py`.
3. Integrar o AI Research Assistant a interface (botao "interpretar com IA"
   sobre a analise corrente).
