# SIGNLAB - Teachable Machine para Libras

Plataforma web interativa para treinar modelos de reconhecimento de sinais em Libras, inspirada no Teachable Machine do Google.

## 🚀 Quick Start

**Opção 1: Menu interativo (recomendado)**
```bash
scripts/signlab.bat
```

**Opção 2: Iniciar direto**
```bash
scripts/start-signlab.bat
```

Acesse: `http://localhost:8100`

## 📁 Estrutura do Projeto

```
SIGNLAB/
├── app/                      # Aplicação principal
│   ├── backend/             # API FastAPI + lógica
│   ├── frontend/            # HTML + CSS + JavaScript
│   └── __pycache__/
│
├── scripts/                 # Utilitários e ferramentas
│   ├── signlab.bat         # Menu interativo (start/stop)
│   ├── start-signlab.bat   # Inicia servidor
│   ├── stop-signlab.bat    # Para servidor
│   └── import_vlibrasil.py # Importa dataset V-LIBRASIL
│
├── docs/                    # Documentação
│   ├── README.md
│   └── IMPORT_DATASET.md   # Guia de importação
│
├── data/                    # Banco de dados
│   └── signlab.db
│
├── projects/               # Dados dos projetos (git ignored)
│   ├── {projeto-id}/
│   ├── images/
│   ├── videos/
│   ├── sequences/
│   ├── models/
│   └── ...
│
├── training/              # Treinamento de modelos
│   ├── image_classifier.py
│   ├── sequence_classifier.py
│   └── ...
│
├── vision/                # Processamento de visão
│   ├── hands.py          # MediaPipe HandLandmarker
│   ├── video.py          # Extração de sequências
│   ├── models/           # Arquivos de modelo
│   └── ...
│
├── lsae/                  # Libras Semantic Augmentation Engine
│   ├── spatial.py
│   ├── temporal.py
│   └── pipeline.py
│
├── config/               # Configurações gerais
├── evaluation/           # Ferramentas de avaliação
├── requirements.txt      # Dependências Python
└── .gitignore
```

## 🛠️ Importar Dataset V-LIBRASIL

**Opção 1: Script automático (rápido)**
```bash
python scripts/import_vlibrasil.py
```

**Opção 2: UI manual (mais controle)**
1. Clique em "+ Novo projeto"
2. Crie classes manualmente
3. Faça upload dos vídeos

Veja: `docs/IMPORT_DATASET.md`

## 📦 Instalação

```bash
pip install -r requirements.txt
python -m uvicorn app.backend.main:app --port 8100 --reload
```

## 🔧 Fases Implementadas

- ✅ **Fase 1-2**: Interface + upload de imagens/vídeos
- ✅ **Fase 3**: Treino com BiLSTM/LSTM para vídeos
- ✅ **Fase 4**: LSAE (data augmentation)
- ✅ **Fase 5.1**: Análise comparativa de experimentos
- ✅ **Fase 6**: Reconhecimento contínuo com webcam
- ✅ **Fase 5.2**: Cross-signer backend (UI pendente)

## 📝 Documentação

- [Importar Dataset](docs/IMPORT_DATASET.md)
- [Arquitetura Técnica](docs/ARCHITECTURE.md) *(em breve)*

---

**Desenvolvido para:** Projeto KONECTA - Libras Sign Language Recognition
