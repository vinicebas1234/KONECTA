# Pipeline Integrado — Captura até Análise

Documentação do pipeline end-to-end que conecta Etapas 4-6 com o Knowledge Engine (Etapa 8).

## Fluxo Completo

```
┌─────────────────────────────────────────────────────────────────┐
│                    PIPELINE KONECTA V2                          │
└─────────────────────────────────────────────────────────────────┘

1. CAPTURA DE VÍDEO (Etapa 4)
   ├─ POST /api/captura/sessao
   ├─ CaptorVideo: webcam ou arquivo
   ├─ Validação de iluminação e movimento
   └─ SessaoCaptura com 60+ frames

2. EXTRAÇÃO DE LANDMARKS (Etapa 5)
   ├─ POST /api/captura/sessao/{id}/landmarks
   ├─ ExtratormediaPipeHands: 21 pontos/mão
   ├─ ExtratormediaPipePose: 33 pontos corpo
   └─ Coordenadas normalizadas [0, 1]

3. ANÁLISE DE TRAJETÓRIAS (Etapa 6)
   ├─ AnalisadorTrajetoria processa landmarks
   ├─ Calcula trajetórias de cada ponto
   ├─ Detecta dominância (direita/esquerda/ambas)
   ├─ Localiza no espaço (alto/baixo/neutro)
   └─ Estima complexidade do gesto

4. CONVERSÃO PARA CORE TYPE (Knowledge Engine)
   ├─ Amostra com landmarks tensor (frames, 21, 3)
   ├─ Metadados: sinal, sinalizante, FPS
   └─ Qualidades: iluminação, confiança

5. ANÁLISE DO KNOWLEDGE ENGINE (Etapa 8)
   ├─ Signal Profiler: características do sinal
   ├─ Quality Analyzer: validação de qualidade
   ├─ Signer Profiler: perfil biomecânico
   └─ Recommendations: prioridade de coleta
```

## Endpoints REST

### POST /api/captura/sessao
Inicia uma nova sessão de captura.

```bash
curl -X POST "http://localhost:8000/api/captura/sessao?id_sessao=sess_001&sinal=CASA&sinalizante=Art1"
```

Resposta:
```json
{
  "id": "sess_001",
  "sinal": "CASA",
  "sinalizante": "Art1"
}
```

### POST /api/captura/sessao/{id}/landmarks
Extrai landmarks de uma sessão.

```bash
curl -X POST "http://localhost:8000/api/captura/sessao/sess_001/landmarks?incluir_maos=true&incluir_corpo=true"
```

Resposta:
```json
{
  "id_sessao": "sess_001",
  "n_frames": 60,
  "landmarks_maos": [
    {
      "numero_frame": 0,
      "timestamp_ms": 0.0,
      "confianca_media": 0.85,
      "mao_direita": [
        {"x": 0.45, "y": 0.35, "z": 0.1, "confianca": 0.9},
        ...
      ],
      "mao_esquerda": [],
      "corpo": []
    },
    ...
  ]
}
```

### POST /api/pipeline/processar
Processa pipeline completo.

```bash
curl -X POST "http://localhost:8000/api/pipeline/processar?id_sessao=sess_001&sinal=CASA&sinalizante=Art1"
```

Resposta:
```json
{
  "id": "sess_001",
  "sinal": "CASA",
  "sinalizante": "Art1",
  "n_frames": 60,
  "duracao_s": 2.0,
  "landmarks_shape": [60, 21, 3],
  "trajetoria": {
    "dominancia": "direita",
    "local_principal": "neutro",
    "complexidade": 0.72,
    "velocidade_media": 1.23
  }
}
```

### GET /api/pipeline/sessao/{id}/trajetoria
Recupera análise de trajetória.

```bash
curl "http://localhost:8000/api/pipeline/sessao/sess_001/trajetoria"
```

## Python API

```python
from backend.services.pipeline_service import processar_sessao_completa

# Processar sessão completa
resultado = processar_sessao_completa(
    id_sessao="minha_sessao",
    sinal="CASA",
    sinalizante="Articulador1"
)

# Resultado contém:
# - id, sinal, sinalizante, n_frames, duracao_s
# - landmarks_shape (tensor de landmarks)
# - trajetoria (dominância, complexidade, velocidade)
```

## Integração com Knowledge Engine

```python
from backend.services.pipeline_service import processar_sessao_completa
from knowledge.dataset_analyzer import DatasetAnalyzer

# 1. Processar via pipeline
resultado = processar_sessao_completa("sess_001", "CASA", "Art1")

# 2. Converter para Amostra (já feito no pipeline)
amostra = Amostra(
    id=resultado["id"],
    sinal=resultado["sinal"],
    sinalizante=resultado["sinalizante"],
    n_frames=resultado["n_frames"],
    duracao_s=resultado["duracao_s"],
    landmarks=resultado["landmarks_tensor"]
)

# 3. Analisar com Knowledge Engine
analyzer = DatasetAnalyzer()
amostras = [amostra]  # + mais amostras
analise = analyzer.analisar([amostra])

# Resultado contém:
# - Balanceamento entre sinais
# - Qualidade de cada amostra
# - Perfis dos sinalizantes
# - Recomendações de coleta
```

## Tipos Principais

### Amostra (core/types.py)
```python
@dataclass
class Amostra:
    id: str
    sinal: str
    sinalizante: str
    n_frames: int
    duracao_s: float
    fps: float
    landmarks: np.ndarray  # (frames, 21, 3)
    qualidade_luz_media: float
    confianca_media: float
```

### AnaliseTrajetoria (tracking/types.py)
```python
@dataclass
class AnaliseTrajetoria:
    id_sessao: str
    dominancia: Dominancia  # enum
    local_principal: LocalTrajetoria  # enum
    maos: dict[str, AnaliseMao]
    duracao_movimento_frames: int
    velocidade_media_geral: float
    complexidade_estimada: float  # 0-1
```

## Status da Implementação

- ✓ Etapa 4 — Captura de vídeo
- ✓ Etapa 5 — Extração de landmarks
- ✓ Etapa 6 — Análise de trajetórias
- ✓ Pipeline integrado com REST API
- ✓ Conversão para Core types
- ⏳ Integração com Knowledge Engine (em progresso)
- ⏳ Etapa 9 — AI Engine (treinamento)

## Próximas Etapas

1. **Completar integração com Knowledge Engine**:
   - Signal Profiler consome AnaliseTrajetoria
   - Quality Analyzer valida landmarks
   - Recommendations usa trajetórias

2. **Etapa 9 — AI Engine**:
   - Treinamento de modelos com amostras do pipeline
   - Avaliação e métricas

3. **Etapas 10-13**:
   - LSAE Engine (reconhecimento)
   - Testes completos
   - Migração de modelos V1
