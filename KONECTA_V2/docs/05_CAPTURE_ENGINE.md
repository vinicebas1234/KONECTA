# Capture Engine — Etapa 4 (em desenvolvimento)

Módulo responsável por capturar vídeos de webcam ou arquivo, extrair frames e
validar qualidade de captura. Habilita os checks visuais de qualidade do Knowledge Engine.

## Arquitetura

```
CaptorVideo (capturer.py)
  ├─ capturar_da_webcam() — captura em tempo real
  ├─ capturar_do_arquivo() — importa vídeo existente
  └─ frames extraídos com qualidade de iluminação

SessaoCaptura (types.py)
  ├─ Metadados (sinal, sinalizante, FPS realizado)
  ├─ Lista de FrameCapturado
  └─ Estatísticas agregadas (duração, FPS, iluminação média)

ValidadorCaptura (validador.py)
  ├─ Validar iluminação (mínima/máxima)
  ├─ Validar movimento (mudança entre frames)
  ├─ Validar FPS e número de frames
  └─ Retorna ResultadoValidacao com pontuação 0-1
```

## Uso

```python
from capture import CaptorVideo, ConfigCaptura, ValidadorCaptura

# Configurar captura
config = ConfigCaptura(
    fps=30,
    resolucao=(640, 480),
    duracao_max_segundos=30,
    luz_minima_pct=0.1,
)

# Capturar vídeo
captor = CaptorVideo(config=config)
sessao = captor.iniciar_sessao("CASA", "Articulador1")

# Da webcam
sessao = captor.capturar_da_webcam(duracao_segundos=5.0)

# Ou de arquivo
from pathlib import Path
sessao = captor.capturar_do_arquivo(Path("video.mp4"))

# Validar qualidade
validador = ValidadorCaptura()
resultado = validador.validar_sessao(sessao)

print(f"Válida: {resultado.valida}")
print(f"Pontuação: {resultado.pontuacao_geral:.2f}")
for problema in resultado.problemas:
    print(f"  Problema: {problema}")
```

## Tipos

- **ConfigCaptura**: Parâmetros de captura (FPS, resolução, codec, durações)
- **FrameCapturado**: Um frame com timestamp, dados PNG, e qualidade de luz
- **SessaoCaptura**: Metadados e frames de uma sessão (sinal, sinalizante, duração)
- **ResultadoValidacao**: Resultado de validação com problemas, avisos e pontuação

## Validação de Qualidade

### Iluminação
- **Mínima**: 0.15 (muito escuro é rejeitado)
- **Máxima**: 0.95 (possível reflexo ou saturação)
- **Score**: Distância do ponto ideal (0.5)

### Movimento
- Detecta diferença de pixels entre frames consecutivos
- Alerta se movimento < 5.0 (sinalizante parado)
- Score baseado na variação do movimento

### Técnicos
- **FPS mínimo**: 20 fps (real pode ser diferente de esperado)
- **Frames mínimos**: 20 (deve ter duração mínima)

## Próximas etapas

1. **Integração com MediaPipe**: Extrair landmarks (29 pontos da mão) de cada frame
2. **Tracking automático de movimento**: Detectar início/fim do sinal
3. **API REST**: POST /api/capture/sessao — frontend envia vídeo para análise
4. **WebSocket de progresso**: Mostrar validação em tempo real durante captura

## Status da implementação

- ✓ CaptorVideo (webcam + arquivo)
- ✓ Validação de iluminação
- ✓ Validação de movimento
- ✓ Teste de smoke
- ✗ Integração com MediaPipe (próxima: Etapa 5)
- ✗ WebSocket de progresso
- ✗ API de captura
