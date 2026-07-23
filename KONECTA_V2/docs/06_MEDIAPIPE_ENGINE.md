# MediaPipe Engine — Etapa 5 (em desenvolvimento)

Extração de landmarks (pontos de articulação) de frames capturados. Utiliza o
MediaPipe do Google para detectar posição de mãos e corpo em tempo real.

## Arquitetura

```
Ponto3D — estrutura básica com (x, y, z, confiança)

LandmarksFrame — landmarks extraídos de um frame
  ├─ mao_direita: list[Ponto3D] (21 pontos)
  ├─ mao_esquerda: list[Ponto3D] (21 pontos)
  └─ corpo: list[Ponto3D] (33 pontos de pose)

ExtratormediaPipeHands — detector de mãos
  └─ extrair_da_sessao(sessao) → list[LandmarksFrame]

ExtratormediaPipePose — detector de corpo
  └─ extrair_da_sessao(sessao) → list[LandmarksFrame]
```

## Modelos do MediaPipe

### Mãos (Hand Landmarker)
- 21 pontos por mão
- Detecta: dedos, palma, pulso
- Confiança normalizada 0-1
- Suporta 2 mãos simultâneas

### Corpo (Pose Landmarker)
- 33 pontos
- Detecta: cabeça, tronco, braços, pernas
- Confiança = visibilidade (0-1)
- Única pessoa por frame

## Uso

```python
from capture import CaptorVideo
from mediapipe_engine import ExtratormediaPipeHands, ExtratormediaPipePose

# Capturar vídeo
captor = CaptorVideo()
sessao = captor.iniciar_sessao("CASA", "Articulador1")
sessao = captor.capturar_da_webcam(duracao_segundos=5.0)

# Extrair landmarks de mãos
extrator_maos = ExtratormediaPipeHands()
landmarks_maos = extrator_maos.extrair_da_sessao(sessao)

# Extrair landmarks do corpo
extrator_corpo = ExtratormediaPipePose()
landmarks_corpo = extrator_corpo.extrair_da_sessao(sessao)

# Acessar landmarks de um frame
primeiro_frame = landmarks_maos[0]
print(f"Mão direita: {len(primeiro_frame.mao_direita)} pontos")
print(f"Mão esquerda: {len(primeiro_frame.mao_esquerda)} pontos")

# Normalizar coordenadas (já fazemos automaticamente)
# Coordenadas estão em [0, 1] (esquerda→direita, topo→base)
for ponto in primeiro_frame.mao_direita:
    print(f"  Ponto: ({ponto.x:.3f}, {ponto.y:.3f}), confiança: {ponto.confianca:.3f}")
```

## Confiabilidade

### Detecção robusta
- Fallback gracioso: se MediaPipe não estiver disponível, frameworks continuam funcionando
- Detecções vazias quando não há mãos/corpo visível
- Confiança sempre presente (0.0 = não detectado)

### Limitações conhecidas
- **Mãos ocluídas**: Pode não detectar quando cruzadas ou tapadas
- **Corpo parcial**: Necessita torso visível para boa detecção
- **Iluminação baixa**: Afeta confiança, validada pela Etapa 4
- **Velocidade alta**: Movimento muito rápido pode gerar lacunas

## Integração com Knowledge Engine

Após extração, os landmarks alimentam:

1. **Signal Profiler**: Trajectória normalizada dos dedos
2. **Quality Analyzer**: Taxa de landmarks perdidos
3. **Similarity Engine**: Distância euclidiana entre posições
4. **Recommendations**: Coletas faltando landmarks críticos

## Status da implementação

- ✓ ExtratormediaPipeHands
- ✓ ExtratormediaPipePose
- ✓ Normalização de coordenadas
- ✓ Fallback gracioso
- ✓ Teste de smoke
- ✗ Integração com Knowledge Engine (Etapa 8)
- ✗ Caching de detecções
- ✗ Configuração de confiança dinâmica

## Próximas etapas

1. **Etapa 6** — Tracking Engine: definir layout de pontos (dominância, "principal diferença")
2. **Integração Etapa 4-8**: Pipeline completo captura → landmarks → análise
