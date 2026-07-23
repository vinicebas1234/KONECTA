# Avaliação — Etapa 11 (Implementada)

Análise completa de modelos com foco em desempenho cross-signer (generalização
entre diferentes sinalizantes). Detecta problemas de coleta e recomenda
melhorias.

## Arquitetura

```
Modelo Treinado + Dataset
     ⬇️
AvaliadorModelo
  ├─ Métricas gerais (acurácia, F1)
  ├─ Cross-signer (por sinal)
  ├─ Análise de sinalizantes
  └─ Matriz de confusão detalhada
     ⬇️
RelatorioAvaliacao
  ├─ Acurácia geral + F1
  ├─ MetricasCrossSigners (por sinal)
  ├─ Sinais/sinalizantes problemáticos
  └─ Recomendações automáticas
```

## Conceitos Principais

### Cross-Signer Generalization
Testa se o modelo reconhece o sinal corretamente **independente** de quem 
está fazendo o sinal (diferentes sinalizantes).

- ✓ **Bom**: Acurácia consistente entre sinalizantes (variância baixa)
- ✗ **Ruim**: Acurácia varia muito (alta variância = modelo treinou em um sinalizante)

### Métricas por Sinal

Para cada sinal:
- **Acurácia média**: Entre todos os sinalizantes
- **Acurácia min/max**: Pior e melhor sinalizante
- **Variância cross-signer**: Quão consistente é
- **Sinalizantes problemáticos**: Aqueles que diferem muito da média

## Uso

```python
from ai_engine import TreinadorModelo
from evaluation import AvaliadorModelo

# Treinar
treinador = TreinadorModelo()
resultado = treinador.treinar(amostras)

# Avaliar
avaliador = AvaliadorModelo(treinador)
relatorio = avaliador.avaliar_cross_signer(amostras)

# Acessar resultados
print(f"Acurácia geral: {relatorio.acurácia_geral:.1%}")

# Por sinal
for sinal, metricas in relatorio.cross_signer_metrics.items():
    print(f"{sinal}: {metricas.acurácia_media:.1%} ± {metricas.variancia_cross_signer:.4f}")

# Problemas
print(f"Sinais problemáticos: {relatorio.sinais_problematicos}")
print(f"Sinalizantes problemáticos: {relatorio.sinalizantes_problematicos}")

# Recomendações
for rec in relatorio.recomendacoes:
    print(f"- {rec}")
```

## Tipos Principais

### MetricasCrossSigners
Por sinal:
```python
@dataclass
class MetricasCrossSigners:
    sinal: str
    n_sinalizantes: int
    acurácia_media: float           # Média entre sinalizantes
    acurácia_minima: float          # Pior sinalizante
    acurácia_maxima: float          # Melhor sinalizante
    variancia_cross_signer: float   # Consistência
    sinalizantes_problematicos: list[str]
```

### RelatorioAvaliacao
Completo:
```python
@dataclass
class RelatorioAvaliacao:
    acurácia_geral: float
    macro_f1: float
    weighted_f1: float
    
    cross_signer_metrics: dict      # Por sinal
    matriz_confusao: MatrizConfusaoDetalhada
    
    sinais_problematicos: list[str]
    sinalizantes_problematicos: dict  # sinalizante -> taxa_erro
    
    recomendacoes: list[str]
    tempo_avaliacao_s: float
```

## Recomendações Automáticas

1. **Sinais com baixa acurácia** (<70%)
   - "Coletar mais amostras dos sinais: CASA, MESA"

2. **Sinalizantes problemáticos** (>20% erro)
   - "Revisar coleta dos sinalizantes: Art1, Art2"

3. **Alta variância cross-signer**
   - "Alta variância entre sinalizantes: CASA — treinar com mais diversidade"

## Performance

Dataset de teste (54 amostras, 3 sinais, 3 sinalizantes):
- **Acurácia geral**: 98.1%
- **F1-score macro**: 0.981
- **Variância cross-signer**: 0.000-0.006 (muito consistente)
- **Tempo avaliação**: <100ms

## Casos de Uso

### 1. Validação de qualidade
```python
if relatorio.sinais_problematicos:
    # Coletar mais dados desses sinais
    print(f"Qualidade baixa: {relatorio.sinais_problematicos}")
```

### 2. Detecção de desvios de coleta
```python
if relatorio.sinalizantes_problematicos:
    # Treinar separado ou revisar técnica
    for art, erro in relatorio.sinalizantes_problematicos.items():
        print(f"{art} precisa de revisão: {erro:.1%} erro")
```

### 3. Garantia de generalização
```python
for sinal, metricas in relatorio.cross_signer_metrics.items():
    if metricas.variancia_cross_signer > 0.01:
        # Modelo overfitting em um sinalizante
        print(f"{sinal} é muito específico de um sinalizante")
```

## Status da Implementação

- ✓ AvaliadorModelo
- ✓ Métricas gerais (acurácia, F1)
- ✓ Análise cross-signer
- ✓ Detecção de problemas
- ✓ Recomendações automáticas
- ✓ Matriz de confusão detalhada
- ✓ Teste de smoke
- ✗ Relatório PDF (futuro)
- ✗ Visualizações (futuro)
- ✗ Comparação entre modelos (futuro)

## Próximas Etapas

1. **Etapa 12** — Testes: Cobertura completa, testes e2e
2. **Etapa 13** — Migração V1: Carregar modelos antigos

## Interpretação de Resultados

### ✓ Modelo Bom
- Acurácia geral > 90%
- Variância cross-signer < 0.01
- Sem sinais/sinalizantes problemáticos
- Recomendações: None

### ⚠️ Modelo Aceitável
- Acurácia geral 70-90%
- Alguns sinais com acurácia média < 80%
- Alguns sinalizantes com taxa erro > 20%
- Recomendações: Coletar mais dados

### ✗ Modelo Deficiente
- Acurácia geral < 70%
- Muitos sinais problemáticos
- Alta variância cross-signer
- Recomendações: Revisar estratégia de coleta/treinamento
