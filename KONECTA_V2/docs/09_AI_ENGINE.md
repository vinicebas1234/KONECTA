# AI Engine — Etapa 9 (Implementada)

Treinamento e avaliação de modelos para reconhecimento de sinais. Consome
amostras enriquecidas do pipeline (Etapas 4-8) e gera métricas para o
AI Research Assistant.

## Arquitetura

```
Amostra (com landmarks)
  ├─ Extração de features
  │  ├─ Flatten de landmarks
  │  ├─ Estatísticas de movimento
  │  └─ Amplitude geral
  └─ Normalização

       ⬇️ Split treino/validação/teste

TreinadorModelo
  ├─ Random Forest (implementado)
  ├─ Neural Network (planejado)
  └─ SVM (planejado)

       ⬇️ Treinamento

ResultadoTreinamento
  ├─ Métricas treino/validação/teste
  ├─ Tempo de treinamento
  └─ Parâmetros ótimos

       ⬇️ Análise de erros

MatrizConfusao + AnaliseErros
  ├─ Quais sinais são confundidos
  ├─ Sinais problemáticos
  └─ Recomendações de coleta
```

## Uso

```python
from ai_engine import TreinadorModelo, TipoModelo
from core.types import Amostra

# Criar amostras com landmarks (do pipeline)
amostras = [...]  # de backend.services.pipeline_service

# Treinar modelo
treinador = TreinadorModelo()
resultado = treinador.treinar(
    amostras,
    tipo_modelo=TipoModelo.RANDOM_FOREST,
    test_size=0.2,
    val_size=0.1,
)

# Acessar métricas
print(f"Acurácia treino: {resultado.metricas_treino.acuracia:.3f}")
print(f"Acurácia teste: {resultado.metricas_teste.acuracia:.3f}")

# Analisar erros
matriz, erros = treinador.analisar_erros(amostras)
print(f"Taxa de acerto: {matriz.taxa_acerto:.1%}")

for rec in erros.recomendacoes:
    print(f"- {rec}")
```

## Features Extraídas

Por amostra:
- **Flatten dos landmarks**: 30 frames × 21 pontos × 3 coords = 1890 features
- **Velocidades**: mean, std, max, min (4 features)
- **Amplitude**: max - min de todos os pontos (1 feature)
- **Total**: ~1895 features por amostra

## Modelos Disponíveis

### Random Forest (Implementado)
- 100 árvores
- Escalável com dados
- Rápido
- Interpretável (feature importance)

### Neural Network (Planejado)
- Para datasets maiores
- Melhor para padrões complexos

### SVM (Planejado)
- Para verificação
- Mais lento, mais preciso

## Métricas de Desempenho

Por split (treino/validação/teste):

- **Acurácia**: Proporção de acertos totais
- **Precisão**: Taxa de verdadeiros positivos entre preditos positivos
- **Recall**: Taxa de verdadeiros positivos entre reais positivos
- **F1-Score**: Média harmônica de precisão e recall
- **AUC-ROC**: Área sob a curva (one-vs-rest)

## Matriz de Confusão

Mostra quais sinais são confundidos:

```
      CASA  MESA  PORTA
CASA   20     1      0
MESA    0    18      2
PORTA   0     1     19
```

Diagonal = acertos, fora da diagonal = confusões.

## Análise de Erros

Automaticamente identifica:

1. **Confusões principais**: Quais pares de sinais são frequentemente confundidos
2. **Sinais problemáticos**: Sinais com taxa de erro > 20%
3. **Recomendações**:
   - Coletar mais amostras de sinais problemáticos
   - Revisar diferenças entre sinais confundidos

## Integração com Knowledge Engine

Resultado do AI Engine alimenta:

- **Signal Profiler**: taxa_confusao (matriz)
- **Recomendações**: sinais com baixa acurácia ficam prioritários
- **AI Research Assistant**: métricas para interpretação

## Status da Implementação

- ✓ TreinadorModelo
- ✓ Feature extraction
- ✓ Split treino/validação/teste
- ✓ Random Forest
- ✓ Métricas de desempenho
- ✓ Matriz de confusão
- ✓ Análise de erros
- ✓ Recomendações automáticas
- ✓ Teste de smoke
- ✗ Neural Network (próxima)
- ✗ SVM (próxima)
- ✗ Serialização de modelos
- ✗ API REST de predição

## Próximas Etapas

1. **Serialização**: Salvar/carregar modelos treinados
2. **API REST**: Endpoint de predição em produção
3. **Outros modelos**: Neural Network, SVM
4. **Fine-tuning**: Grid search de hiperparâmetros
5. **Cross-validation**: Validação mais robusta
6. **Interpretabilidade**: Feature importance, SHAP values

## Referências

- Scikit-learn: Random Forest, métricas
- Pipeline de ML: treino → validação → teste
- Matriz de confusão: análise de erros

## Performance

Dataset de teste (30 amostras, 3 sinais):
- Tempo de treinamento: ~0.23s
- Acurácia treino: 100%
- Acurácia validação: 67%
- Acurácia teste: 100%

Escalável para datasets maiores com datasets reais.
