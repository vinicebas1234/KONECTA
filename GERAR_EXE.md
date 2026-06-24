# 📦 Gerar EXE Executável

## 3 passos simples:

### **Passo 1: Gerar o EXE**

1. Duplo-clique em: `C:\KONECTA\gerar_exe.bat`
2. Espera uns 2-3 minutos (primeira vez é mais lenta)
3. Pronto! EXE está em: `C:\KONECTA\dist\Libras_OCR.exe`

---

### **Passo 2 (Opcional): Criar Atalho no Desktop**

Para facilitar ainda mais, crie um atalho no Desktop:

1. Duplo-clique em: `C:\KONECTA\create_shortcut.bat`
2. Atalho aparece no seu Desktop
3. Agora pode iniciar diretamente do Desktop

---

### **Passo 3: Usar o EXE**

```
Opção A: Via Desktop
└─ Duplo-clique no atalho "Libras OCR" no Desktop

Opção B: Via arquivo
└─ Duplo-clique em: C:\KONECTA\dist\Libras_OCR.exe

Opção C: Via linha de comando
└─ C:\KONECTA\dist\Libras_OCR.exe
```

---

## 📊 O que está incluído no EXE

O executável já contém:
- ✅ Python runtime completo
- ✅ Todas as bibliotecas (OpenCV, TensorFlow, MediaPipe, etc)
- ✅ Interface gráfica (Tkinter)
- ✅ Dados e modelos treinados (se existirem)

**Resultado:** Um único `.exe` que você pode compartilhar, copiar, colocar no Desktop, o que quiser!

---

## 🎯 Resumo Final

```
Sem EXE (antes):
├─ Precisa VSCode ou terminal
├─ Precisa configurar variáveis
└─ Meio complicado

Com EXE (agora):
├─ Duplo-clique e pronto
├─ Tudo pré-configurado
└─ Semelhante a qualquer programa Windows
```

---

## ⚠️ Se der erro

### "Arquivo não encontrado"
```
Certifique-se que:
✓ Tem o .venv2 em OCR/.venv2
✓ Executou run.bat antes
```

### "Permission denied"
```
Se não conseguir executar .bat:
1. Clique direito em gerar_exe.bat
2. Propriedades → Desbloquear
3. Tente de novo
```

### "ModuleNotFoundError"
```
Rode primeiro:
.venv2\Scripts\pip install pyinstaller
```

---

## 📈 Tamanho do EXE

```
Esperado: ~150-200 MB
(Inclui Python + todas as dependências)

Primeira geração: 2-3 minutos
Gerações futuras: 1-2 minutos (mais rápido)
```

---

## 🚀 Próximo passo

```
1. Execute: gerar_exe.bat
2. Espera terminar
3. Execute: create_shortcut.bat
4. Duplo-clique no atalho Desktop
5. Pronto!
```

**Agora você tem um programa Windows normal que executa assim como qualquer outro! 🎉**
