# Importar Dataset V-LIBRASIL Completo

## Opção 1: Importação Automática (Script Python)

Executa um script que automaticamente:
- ✅ Cria um novo projeto "V-LIBRASIL Completo"
- ✅ Cria todas as classes (um sinal por classe)
- ✅ Importa todos os vídeos do dataset
- ✅ Armazena no SQLite e storage do SIGNLAB

### Passo a passo:

1. **Certifique-se que o servidor está parado:**
   ```bash
   # Interrompa o servidor no navegador ou terminal
   ```

2. **Execute o script:**
   ```bash
   cd C:\KONECTA\SIGNLAB
   python import_vlibrasil.py
   ```

3. **Monitore o progresso:**
   - O script exibirá o progresso de importação
   - Após concluir, você verá um link para acessar o projeto

4. **Reinicie o servidor:**
   - Clique no botão "signlab" no Preview, ou execute:
   ```bash
   python -m uvicorn app.backend.main:app --port 8100
   ```

5. **Acesse o projeto:**
   - Vá para http://localhost:8100
   - Clique no projeto "V-LIBRASIL Completo"

## Opção 2: Importação Manual via UI

Se preferir fazer manualmente:

1. Crie um novo projeto
2. Para cada sinal:
   - Crie uma classe
   - Clique em "📁 Imagens" ou "📷 Webcam"
   - Selecione os vídeos do sinal
   - Aguarde o upload

⚠️ **Mais lento**, mas oferece controle total sobre quais sinais importar.

## Solução de Problemas

### "Caminho não encontrado"
- Verifique se o dataset está em: `C:\KONECTA\Datasets\videos UFPE (V-LIBRASIL)\data`
- Se estiver em outro local, edite `VLIBRASIL_PATH` no script

### "Erro ao conectar ao banco"
- Certifique-se que o servidor está parado
- Não execute o script enquanto o servidor está usando o banco

### "Importação lenta"
- É normal! O dataset tem centenas de vídeos
- O progresso é exibido a cada 50 vídeos importados

## Após Importação

Você pode:
- ✅ Treinar modelos com o dataset completo
- ✅ Fazer testes de reconhecimento
- ✅ Executar análise comparativa de experimentos
- ✅ Testar reconhecimento contínuo com câmera

---

**Script criado em:** 2026-08-04
**Versão:** 1.0
