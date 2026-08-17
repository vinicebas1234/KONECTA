# KONECTA V3 — Vision Lab

Um laboratório experimental de visão computacional para validar a pipeline de captura, extração de landmarks, processamento e reconhecimento de Libras.

**Objetivo**: Responder empiricamente: A nova representação de landmarks consegue transformar os vídeos existentes em dados suficientemente bons para treinar um modelo capaz de reconhecer Libras em tempo real?

## Setup Rápido

```bash
# 1. Criar ambiente virtual
python -m venv .venv
.venv\Scripts\activate

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Rodas testes básicos
pytest tests/ -v

# 4. Executar servidor
uvicorn vision_lab.app:app --reload --port 8000
```

Acesse: http://localhost:8000

## Arquitetura

```
Dataset Loader
    ↓
Video Viewer (Frame Navigation)
    ↓
Landmark Extraction (MediaPipe)
    ↓
Quality Analysis
    ↓
Visualization
    ↓
Landmark Cleaner
    ↓
Normalizer
    ↓
Feature Engineering
    ↓
Dataset Builder
    ↓
Training Lab
    ↓
Live Recognition
```

## Fases de Implementação

- [x] **FASE 1**: Dataset Loader + Video Viewer + Landmark Extraction
- [ ] **FASE 2**: Landmark Visualization + Quality Analysis
- [ ] **FASE 3**: Cleaning, Interpolation, Smoothing, Normalization
- [ ] **FASE 4**: Feature Engineering + Dataset Builder
- [ ] **FASE 5**: Baseline Training + Metrics
- [ ] **FASE 6**: Cross-Signer + Error Analysis
- [ ] **FASE 7**: Real-time Recognition
- [ ] **FASE 8**: Experiment Manager + V1/V2 Comparison

## Dataset

Detecta automaticamente estrutura de vídeos em:

```
datasets/
├── train/
│   ├── CLASS_A/
│   │   ├── signer_01/video_1.mp4
│   │   └── signer_02/video_1.mp4
│   └── CLASS_B/
│       └── ...
└── videos UFPE (V-LIBRASIL)/
    └── data/
        ├── Abacaxi/
        ├── Abanar/
        └── ...
```

## Documentação

- [Pipelines](docs/01_pipeline.md)
- [Landmarks](docs/02_landmarks.md)
- [Dataset Format](docs/03_dataset.md)
- [Training](docs/04_training.md)
