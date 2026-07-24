# Diagnóstico - KONECTA V2 vs V1

## Problemas Identificados

### 1. **Canvas não visível**
- V2: `className="hidden"` no canvas
- **Solução**: Remover hidden, fazer canvas overlay do vídeo

### 2. **MediaPipe não está processando frames**
- `onHandsResults` retorna se `!capturando`
- Mas capturando é true ANTES de MediaPipe estar pronto
- **Solução**: Remover verificação, deixar sempre processar

### 3. **Camera.start() não chama onFrame**
- Camera não está sendo inicializado corretamente
- **Solução**: Verificar se videoRef está pronto ANTES de criar Camera

### 4. **Canvas overlay não está sobre o vídeo**
- Canvas está hidden, não visível
- **Solução**: Posicionar canvas em absolute no topo do vídeo

### 5. **Landmarks não sendo coletados**
- Se não há landmarks, envia zeros ao backend
- Zeros ao backend = sempre "DESCONHECIDO"
- **Solução**: Garantir que landmarks reais estão sendo extraídos

## Ação Imediata

1. Tornar canvas visível
2. Garantir mediaPipe processa TODOS os frames
3. Testar com câmera real (não navegador)
4. Validar que reconhecimento funciona com dados reais
