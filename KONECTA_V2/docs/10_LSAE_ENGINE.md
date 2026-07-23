# LSAE Engine — Etapa 10 (Implementada)

Reconhecimento em tempo real de sinais usando modelos treinados pela
Etapa 9 (AI Engine). Integra captura, landmarks, tracking e AI em um
loop de reconhecimento contínuo.

## Arquitetura

```
Modelo Treinado (AI Engine)
  └─ RandomForestClassifier
  └─ StandardScaler (normalização)
  └─ Classes: sinais disponíveis

        ⬇️

ReconhecedorSinais
  ├─ reconhecer_landmarks(tensor 30x21x3)
  ├─ reconhecer_sessao(frames)
  └─ reconhecer_tempo_real(stream)

        ⬇️

PredictedSinal
  ├─ sinal: str
  ├─ confianca: 0-1
  ├─ ranking: [(sinal, prob), ...]
  └─ frame_numero: int

        ⬇️

ResultadoRecognition
  ├─ predicoes: list[PredictedSinal]
  ├─ sinal_dominante: str
  ├─ taxa_confianca_media: float
  └─ n_frames_processados: int
```

## Uso

```python
from ai_engine import TreinadorModelo
from lsae import ReconhecedorSinais

# 1. Treinar modelo (Etapa 9)
treinador = TreinadorModelo()
resultado_treino = treinador.treinar(amostras)

# 2. Criar reconhecedor (Etapa 10)
reconhecedor = ReconhecedorSinais(treinador)

# 3. Reconhecer frame único
predicao = reconhecedor.reconhecer_landmarks(landmarks)
print(f"{predicao.sinal}: {predicao.confianca:.1%}")

# 4. Reconhecer sessão completa
resultado = reconhecedor.reconhecer_sessao(
    "sessao_001",
    lista_landmarks_frames,
    modo=ModoRecognition.VIDEO_COMPLETO
)

print(f"Sinal dominante: {resultado.sinal_dominante}")
print(f"Confiança média: {resultado.taxa_confianca_media:.1%}")
```

## Modos de Reconhecimento

### Frame Único
```python
predicao = reconhecedor.reconhecer_landmarks(landmarks_tensor)
# Resultado: uma predição com ranking
```

### Sessão Completa
```python
resultado = reconhecedor.reconhecer_sessao(
    id_sessao,
    landmarks_frames,
    modo=ModoRecognition.VIDEO_COMPLETO
)
# Resultado: predições por frame + sinal dominante
```

### Tempo Real (Futuro)
```python
reconhecedor.reconhecer_stream(
    video_stream,
    callback=lambda p: print(f"{p.sinal}: {p.confianca:.1%}")
)
# Callback chamado para cada frame com predição
```

## Extração de Features

Mesmo processo que no treinamento:

1. **Flatten**: 30 frames × 21 pontos × 3 coords = 1890 features
2. **Velocidade**: Mean, std, max, min das mudanças entre frames
3. **Amplitude**: Max - min de todos os valores

Total: 1895 features por amostra

## Confiabilidade

### Score de Confiança
- 0.0-0.3: Predição muito incerta
- 0.3-0.7: Predição moderada
- 0.7-1.0: Predição confiável ✓

### Ranking
Todas as classes ordenadas por probabilidade:
```python
predicao.ranking
# [('CASA', 0.75), ('MESA', 0.20), ('PORTA', 0.05)]
```

### Taxa de Confiança Geral
Proporção de predições com confiança > 70%:
```python
resultado.taxa_confianca_geral  # 0.0-1.0
```

## Integração com Pipeline

```
Captura → Landmarks → Tracking → Enriquecimento
              ⬇️
        [AI Engine: Treinamento]
              ⬇️
        [LSAE Engine: Reconhecimento]
              ⬇️
        Dashboard + AI Interpretation
```

## Performance

Dataset de teste (32 amostras, 2 sinais):
- **Tempo treino**: ~0.23s
- **Tempo reconhecimento/frame**: ~32ms
- **Acurácia treino**: 100%
- **Acurácia teste**: 100%

Escalável para datasets reais com mais sinais.

## Tipos Principais

### PredictedSinal
```python
@dataclass
class PredictedSinal:
    sinal: str                           # Ex: "CASA"
    confianca: float                     # 0.0-1.0
    ranking: list[tuple[str, float]]    # Todas as classes
    timestamp_ms: float                  # Posição no vídeo
    frame_numero: int                    # Qual frame
```

### ResultadoRecognition
```python
@dataclass
class ResultadoRecognition:
    id_sessao: str
    modo: ModoRecognition
    predicoes: list[PredictedSinal]
    taxa_confianca_media: float
    sinal_dominante: str
    tempo_processamento_s: float
    n_frames_processados: int
```

## Status da Implementação

- ✓ ReconhecedorSinais
- ✓ Reconhecimento frame único
- ✓ Reconhecimento sessão completa
- ✓ Ranking de confiança
- ✓ Análise de confiabilidade
- ✓ Teste de smoke
- ✗ Stream tempo-real (próximo)
- ✗ Cache de modelos
- ✗ API REST de predição
- ✗ Latency optimization

## Próximas Etapas

1. **Stream em tempo real**: Processar vídeo webcam contínuamente
2. **Otimização de latência**: Reduzir de 32ms para <16ms
3. **API REST**: Endpoint `/api/lsae/reconhecer`
4. **Integração frontend**: Mostrar predições em tempo real
5. **Logging**: Registrar predições para análise

## Limitações Atuais

- Requer tensor completo (30 frames)
- Sem otimização GPU
- Sem multi-threading
- Sem cache de predições

## Futuro: LSAE Avançado

- Suporte para gestos contínuos (frases)
- Correção de erros com contexto
- Retrainamento online
- Modelos específicos por sinalizante
