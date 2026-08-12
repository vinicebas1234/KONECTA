# 🚀 Setup Simplificado - Libras OCR

## 3 Formas de Executar (escolha a sua!)

### **Opção 1: VSCode (Recomendado) ⭐**

Agora que temos `.vscode/launch.json`, é super fácil:

1. Abra `C:\KONECTA` no VSCode
2. Abra `OCR/libras_recognizer.py`
3. Pressione `F5` (ou `Ctrl+F5`)
   - Automaticamente puxa `LIBRAS_BASE_DIR` 
   - Seta `PYTHONPATH` correto
   - Executa no terminal integrado

**Pronto!** Nenhuma variável de ambiente manual necessária.

---

### **Opção 2: Duplo-clique (Windows) 🖱️**

1. Vá até `C:\KONECTA\`
2. Duplo-clique em `run.bat`
3. Espera (pode levar alguns segundos na primeira vez)
4. Aplicação inicia com tudo configurado

---

### **Opção 3: PowerShell (Avançado)**

```powershell
# Abre PowerShell em C:\KONECTA
cd C:\KONECTA

# Executa
.\run.ps1
```

---

## Se der erro:

### "Ambiente virtual não encontrado"

```bash
# Na pasta C:\KONECTA\OCR\
python -m venv .venv2
.venv2\Scripts\pip install -r requirements.txt
```

### "ModuleNotFoundError: No module named 'cv2'"

```bash
.venv2\Scripts\pip install opencv-python mediapipe tensorflow scikit-learn numpy
```

### VSCode não encontra Python

1. `Ctrl+Shift+P` → "Python: Select Interpreter"
2. Escolha: `.../OCR/.venv2/Scripts/python.exe`

---

## ✨ O que foi configurado

### `.vscode/settings.json`
- Define Python interpreter automaticamente
- Ignora cache (`__pycache__`, `*.pyc`)

### `.vscode/launch.json`
- Configura `F5` para rodar com variáveis corretas
- Fornece 2 configurações de launch:
  - `Python: Libras OCR` → executa libras_recognizer.py
  - `Python: Importar Dataset` → executa importar_dataset_libras.py

### `run.bat` e `run.ps1`
- Scripts que configuram e executam automaticamente
- Perfeito para duplo-clique ou terminal

---

## 🎯 Fluxo recomendado

```
1. Abre VSCode (C:\KONECTA como pasta workspace)
2. Abre OCR/libras_recognizer.py
3. Pressiona F5
4. Desenvolvimento/testes
5. Commit + push quando pronto
```

**Sem precisar pensar em variáveis de ambiente!**

---

## Variáveis Configuradas

```
LIBRAS_BASE_DIR = C:\KONECTA\OCR
PYTHONPATH = C:\KONECTA\OCR
```

Se precisar mudar o caminho base, edite `.vscode/launch.json` ou `run.bat`.
