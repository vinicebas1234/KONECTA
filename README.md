# KONECTA
## Plataforma de Pesquisa em Reconhecimento de Libras

---

## 🚀 Quick Start

```bash
# Menu interativo (melhor experiência)
start.bat

# Ou direto para SIGNLAB
cd SIGNLAB
scripts/signlab.bat
```

**Acesse:** `http://localhost:8100`

---

## 📦 Projetos Ativos

### ⭐ **SIGNLAB** - Teachable Machine Interativa
- Interface web para treinar modelos de sinais
- Upload de imagens e vídeos
- Treino com RF/MLP ou BiLSTM/LSTM
- Data augmentation (LSAE)
- Reconhecimento em tempo real

```bash
cd SIGNLAB
scripts/signlab.bat  # Escolha "1 - Iniciar"
```

### 🔧 **KONECTA_V2** - Framework Backend
- Backend Python/FastAPI
- Knowledge Engine
- Pipeline de processamento
- Integração com SIGNLAB (em desenvolvimento)

---

## 📁 Estrutura

```
KONECTA/
│
├── 🎯 SIGNLAB/           ← Teachable Machine (ATIVO)
│   ├── app/
│   ├── scripts/
│   ├── docs/
│   └── data/signlab.db
│
├── 🔧 KONECTA_V2/        ← Framework (EM DESENVOLVIMENTO)
│   ├── backend/
│   ├── frontend/
│   └── ...
│
├── 📊 Datasets/          ← V-LIBRASIL + dados
│
├── 📚 docs/              ← Documentação
│
├── 📦 archive/           ← Projetos antigos (preservados)
│
├── start.bat             ← Menu principal
├── README_PROJETOS.md    ← Guia detalhado
└── .gitignore
```

---

## 📚 Documentação

- **SIGNLAB:** `SIGNLAB/docs/README.md`
- **Dataset:** `SIGNLAB/docs/IMPORT_DATASET.md`
- **Geral:** `docs/` (artigos, relatórios técnicos)
- **Detalhes:** `README_PROJETOS.md`

---

## 🎓 Para Pesquisadores

### Começar novo experimento:
1. Abrir `start.bat` → escolher SIGNLAB
2. Criar novo projeto
3. Fazer upload de vídeos/imagens
4. Treinar modelo
5. Testar e analisar resultados

### Usar V-LIBRASIL:
```bash
cd SIGNLAB
python scripts/import_vlibrasil.py  # Importa dataset completo
```

### Acessar dados antigos:
- Projetos experimentais: `archive/`
- Documentação técnica: `docs/`

---

## ⚙️ Stack

- **Frontend:** HTML + CSS + JavaScript (vanilla)
- **Backend:** FastAPI + SQLite
- **ML:** Keras, Scikit-Learn, MediaPipe
- **Data:** V-LIBRASIL (UFPE), vídeos locais

---

## 🗂️ Archive

Projetos antigos preservados (não em uso):
- KONECTA_V3 (experimental)
- vision_lab, vlibra, lsae_demo
- Backups e builds antigos

Para restaurar: `archive/<pasta>`

---

**Status:** 2026-08-11  
**Pesquisador:** Vinicius  
**Última atualização:** Reorganização e limpeza
