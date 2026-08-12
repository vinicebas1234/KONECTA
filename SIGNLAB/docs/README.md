# SIGNLAB

Laboratório Visual de Treinamento e Reconhecimento de Libras.

Inspirado na simplicidade do Google Teachable Machine, especializado em Libras:
imagens, vídeos, webcam, landmarks, sequências temporais e LSAE.

## Como executar

```bash
python -m uvicorn app.backend.main:app --port 8100
```

Abra http://localhost:8100 no navegador.

## Estrutura

```
SIGNLAB/
├── app/
│   ├── frontend/     # Interface (HTML/CSS/JS)
│   └── backend/      # API FastAPI + SQLite
├── projects/         # Dados dos projetos (filesystem)
├── lsae/             # Libras Semantic Augmentation Engine
├── vision/           # MediaPipe, extração e normalização de landmarks
├── training/         # Treinamento (imagem e temporal)
├── evaluation/       # Métricas, matriz de confusão, cross-signer
├── config/           # Configurações
└── README.md
```

## Roadmap

- **Fase 1 — Interface** ✅ projeto, classes, upload, preview, organização
- **Fase 2 — Imagens** ⏳ processamento, landmarks, treinamento, classificação
- **Fase 3 — Vídeos** ⏳ frames, landmarks, sequências, treinamento temporal
- **Fase 4 — LSAE** ⏳ augmentation temporal/espacial, landmarks sintéticos
- **Fase 5 — Avaliação** ⏳ métricas, matriz de confusão, cross-signer
- **Fase 6 — Real-Time** ⏳ webcam, buffer, reconhecimento contínuo
- **Fase 7 — Research** ⏳ BiLSTM, Transformer, benchmark
