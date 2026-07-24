# Arquitetura Geral — KONECTA V2

## Visao

A V2 transforma o KONECTA de um sistema de treinamento de modelos em uma
plataforma modular de pesquisa em IA aplicada ao reconhecimento de Libras.
Cada motor tem responsabilidade unica e se comunica pelos tipos definidos em
`core/types.py`.

## Pipeline de motores

```
Capture Engine      captura de video/frames
      |
Tracking Engine     extracao de landmarks (MediaPipe)
      |
Dataset Engine      armazenamento, importacao e organizacao das amostras
      |
Knowledge Engine    analise, perfis, qualidade, relacoes, recomendacoes
      |
AI Research         LLMs interpretando as analises para o pesquisador
Assistant           (Claude, GPT, Gemini, modelos locais)
      |
AI Engine           treinamento e avaliacao dos modelos de reconhecimento
      |
LSAE Engine         geracao sintetica biomecanica alimentada pelo Knowledge Engine
      |
Interface / API     frontend web + backend FastAPI (WebSocket)
```

Mudanca central em relacao a V1: **nenhum treinamento acontece sem que o
Knowledge Engine tenha analisado, validado e documentado o dataset antes.**

## Stack

- **Frontend**: React + HTML + Tailwind + Framer Motion
- **Backend**: Python + FastAPI, comunicacao em tempo real via WebSocket
- **Processamento**: MediaPipe, OpenCV, PyTorch, Scikit-Learn
- **IA generativa**: SDK oficial `anthropic` (referencia); suporte multi-provedor planejado

## Regras de desenvolvimento

1. A V1 (raiz do repositorio) permanece intacta — e somente referencia.
2. Todo codigo novo vive em `KONECTA_V2/`.
3. Antes de implementar algo, verificar se existe equivalente na V1:
   analisar, reaproveitar a logica necessaria e **reescrever** dentro da
   arquitetura da V2 — nunca copiar arquivos inteiros.
4. Qualidade da arquitetura acima de velocidade de implementacao.
5. Migracao por etapas; cada modulo da V2 e validado de forma independente
   antes de qualquer migracao de funcionalidade da V1.

## Preparado para crescer

Decisoes arquiteturais devem considerar: novos modelos de IA, datasets
publicos, multiplos idiomas de sinais, diferentes motores de captura e
tracking, novos algoritmos de augmentation, APIs publicas, versoes Desktop
e Web, colaboracao entre pesquisadores e plugins de terceiros.
