# Tracking Engine — Etapa 6 (em desenvolvimento)

Análise de trajetórias de landmark para caracterizar movimento de sinais de Libras.
Detecta dominância de mão, localização no espaço de sinalização, e complexidade do gesto.

## Arquitetura

```
TrajetoData — trajetória de um ponto (x, y, z, confiança ao longo de frames)
  ├─ comprimento_pixel — distância total percorrida
  ├─ confianca_media — confiança média de detecção
  └─ n_frames — número de frames

AnaliseMao — análise de uma mão
  ├─ dominancia_estimada
  ├─ ativa_em_frames
  ├─ velocidade_media
  ├─ amplitude_total
  ├─ estabilidade (0-1)
  └─ trajetorias (dict de 21 pontos)

AnaliseTrajetoria — resultado final
  ├─ dominancia (direita/esquerda/ambas/indefinida)
  ├─ local_principal (alto/baixo/neutro/lateral/frontal)
  ├─ maos (análise de cada mão)
  ├─ velocidade_media_geral
  └─ complexidade_estimada (0-1)

AnalisadorTrajetoria — engine de análise
```

## Uso

```python
from capture import CaptorVideo
from mediapipe_engine import ExtratormediaPipeHands
from tracking import AnalisadorTrajetoria

# Capturar e extrair landmarks
captor = CaptorVideo()
sessao = captor.iniciar_sessao("CASA", "Articulador1")
sessao = captor.capturar_da_webcam(duracao_segundos=5.0)

extrator_maos = ExtratormediaPipeHands()
landmarks_maos = extrator_maos.extrair_da_sessao(sessao)

# Analisar trajetórias
analisador = AnalisadorTrajetoria()
analise = analisador.analisar_landmarks(
    id_sessao="sessao_001",
    landmarks_maos=landmarks_maos,
)

print(f"Dominância: {analise.dominancia}")
print(f"Local: {analise.local_principal}")
print(f"Complexidade: {analise.complexidade_estimada:.2f}")

# Acessar detalhe das mãos
if "direita" in analise.maos:
    mao_direita = analise.maos["direita"]
    print(f"Mão direita ativa em {mao_direita.ativa_em_frames} frames")
    print(f"Velocidade: {mao_direita.velocidade_media:.3f} px/frame")
```

## Conceitos

### Dominância
- **Direita**: mão direita com movimento 50%+ maior
- **Esquerda**: mão esquerda dominante
- **Ambas**: movimento simétrico/alternado
- **Indefinida**: pouco movimento detectado

### Local Principal
- **Alto**: acima dos ombros (cabeça)
- **Baixo**: abaixo da cintura
- **Neutro**: frente ao corpo (padrão)
- **Lateral**: fora do corpo
- **Frontal**: perto do rosto

### Métricas

**Velocidade**:PixelsFrame movimento médio
- Simples: 0.2-0.5 px/frame
- Moderado: 0.5-1.5 px/frame
- Rápido: > 1.5 px/frame

**Amplitude**: Distância total percorrida (pixels)

**Estabilidade**: Inverso da variância de velocidade
- 1.0 = movimento muito consistente
- 0.0 = movimento muito errático

**Complexidade**: Proporção de trajetórias com movimento significativo
- 0.0-0.3: gesto simples (1-6 dedos movendo)
- 0.3-0.7: gesto moderado (7-14 dedos)
- 0.7-1.0: gesto complexo (15+ dedos)

## Integração com Knowledge Engine

Resultados alimentam:

1. **Signal Profiler**: Trajetórias normalizadas dos pontos críticos
2. **Quality Analyzer**: Detecta lacunas e inconsistências
3. **Similarity Engine**: Comparação de trajetórias entre amostras
4. **Recommendations**: Prioriza coletas de sinais com trajetórias instáveis

## Pontos da Mão (MediaPipe)

```
Thumb:      0 (base) → 1 → 2 → 3 (ponta)
Index:      4 (base) → 5 → 6 → 7 (ponta)
Middle:     8 (base) → 9 → 10 → 11 (ponta)
Ring:      12 (base) → 13 → 14 → 15 (ponta)
Pinky:     16 (base) → 17 → 18 → 19 (ponta)
Wrist:     20 (centro da palma)
```

## Status da implementação

- ✓ AnalisadorTrajetoria
- ✓ Extração de trajetórias (21 pontos)
- ✓ Determinação de dominância
- ✓ Localização no espaço
- ✓ Estimativa de complexidade
- ✓ Cálculos de velocidade e estabilidade
- ✓ Teste de smoke
- ✗ Layout customizável (próximo)
- ✗ Integração com Knowledge Engine (Etapa 8)
- ✗ Detecção de movimento (início/fim)

## Próximas etapas

1. **Layouts de sinais específicos**: Definir quais pontos são críticos para cada sinal
2. **Integração com Knowledge Engine**: Usar análise no Signal Profiler
3. **Detecção de repouso**: Identificar frames onde o sinal não está ocorrendo
