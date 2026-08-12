# KONECTA - Libras Sign Language Recognition

Repositório consolidado com projetos de pesquisa em reconhecimento de sinais em Libras.

## 🚀 Projetos Ativos

### 1. **SIGNLAB** ⭐ (Recomendado)
**Teachable Machine interativa para Libras**

```bash
cd SIGNLAB
scripts/signlab.bat  # Menu (iniciar/parar servidor)
```

- ✅ Interface web type Teachable Machine
- ✅ Upload/webcam de imagens e vídeos
- ✅ Treino com RF/MLP (imagem) ou BiLSTM/LSTM (vídeo)
- ✅ LSAE (data augmentation)
- ✅ Análise comparativa de experimentos
- ✅ Reconhecimento contínuo com webcam

📍 Acesse: `http://localhost:8100`

**Documentação:** `SIGNLAB/docs/`

---

### 2. **KONECTA_V2** (Em desenvolvimento)
**Framework backend para Libras com Knowledge Engine**

```bash
cd KONECTA_V2
# Configurar conforme documentação no diretório
```

- 🔧 Backend Python/FastAPI
- 📚 Knowledge Engine antes do treino
- 📊 Pipeline de processamento de dados
- 🧠 Modelos de reconhecimento

**Documentação:** `KONECTA_V2/README.md`

---

## 📁 Estrutura

```
KONECTA/
├── SIGNLAB/                ← Teachable Machine (ATIVO ⭐)
│   ├── app/               # Backend + Frontend
│   ├── scripts/           # Ferramentas
│   └── docs/              # Documentação
│
├── KONECTA_V2/             ← Framework (ATIVO 🔧)
│   ├── backend/
│   ├── frontend/
│   └── ...
│
├── Datasets/               ← Dados compartilhados
│   └── videos UFPE (V-LIBRASIL)/
│
├── docs/                   ← Documentação geral
│   └── *.md
│
└── archive/                ← Projetos antigos (2025-08-11)
    ├── KONECTA_V3/
    ├── vision_lab/
    ├── vlibra/
    ├── lsae_demo/
    └── ...
```

---

## 🎯 Quick Start

**Para testar SIGNLAB:**
```bash
cd SIGNLAB
scripts/signlab.bat
# Escolha opção 1 (iniciar servidor)
# Acesse http://localhost:8100
```

**Para desenvolver em KONECTA_V2:**
```bash
cd KONECTA_V2
# Consulte README.md ou documentation
```

---

## 📚 Documentação

- **SIGNLAB:** `SIGNLAB/docs/README.md` + `SIGNLAB/docs/IMPORT_DATASET.md`
- **KONECTA_V2:** `KONECTA_V2/README.md`
- **Geral:** `docs/` (guias técnicos, setup, etc.)

---

## 🗂️ O que foi movido para archive/

Projetos e código antigo (preservado, não deletado):
- KONECTA_V3 (experimental)
- vision_lab, vlibra, Libras_OCR
- LSAE-repo, lsae_demo, mediapipe_engine
- Backups e pastas de build antigos
- Arquivos de teste/debug soltos

**Para recuperar:** `archive/<pasta>`

---

## 💡 Próximos Passos

1. **Usar SIGNLAB** para fazer experimentos interativos
2. **Integrar KONECTA_V2** como backend robusto (quando pronto)
3. **Consolidar resultados** em relatórios de pesquisa

---

**Último update:** 2026-08-11
**Pesquisador:** Vinicius (KONECTA/Libras)
