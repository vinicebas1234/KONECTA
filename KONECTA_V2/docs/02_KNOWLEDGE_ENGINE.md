# Knowledge Engine

O Knowledge Engine **nao reconhece sinais**. Ele compreende profundamente o
comportamento do dataset, dos sinalizantes e dos modelos treinados, para que
decisoes futuras (coleta, augmentation, treinamento) possam ser tomadas
automaticamente ou com apoio do AI Research Assistant.

## Modulos e responsabilidades

| Modulo | Responsabilidade | Status |
|---|---|---|
| `dataset_analyzer.py` | Orquestrador: recebe amostras, devolve `AnaliseDataset` completa | Funcional |
| `dataset_statistics.py` | Contagens, distribuicao, balanceamento (entropia normalizada), medias | Funcional |
| `quality_analyzer.py` | Aprovacao/reprovacao de amostras por limiares configuraveis | Funcional (checks de metadados); checks visuais dependem do Capture Engine |
| `signer_profiler.py` | Perfil biomecanico por sinalizante (velocidade, amplitude, estabilidade) | Funcional; dominancia depende do layout de landmarks do Tracking Engine |
| `signal_profiler.py` | Perfil por sinal (trajetoria media, complexidade, variabilidade) | Funcional; `taxa_confusao` preenchida pos-treino |
| `embeddings.py` | Vetor descritor por amostra e centroide por sinal | Funcional (descritor estatistico); embeddings aprendidos no futuro |
| `similarity_engine.py` | Matriz de similaridade e pares confundiveis | Funcional; "principal diferenca" automatica pendente |
| `recommendations.py` | Recomendacoes priorizadas de coleta | Funcional |
| `dataset_versioning.py` | Versoes logicas (V1 -> V2 -> ...) com diff automatico | Funcional (JSON) |
| `reports.py` | Relatorio Markdown para pesquisador e para o LLM | Funcional |
| `ai_assistant.py` | AI Research Assistant multi-provedor (Claude implementado) | Funcional com `anthropic`; OpenAI/local pendentes |

## Contratos

Todos os tipos trocados entre modulos estao em `core/types.py`:
`Amostra`, `EstatisticasDataset`, `PerfilSinalizante`, `PerfilSinal`,
`ResultadoQualidade`, `Recomendacao`, `RelacaoSinais`, `VersaoDataset` e
`AnaliseDataset` (o agregado final).

O `landmarks` de uma `Amostra` tem shape `(n_frames, n_pontos, 3)`. O layout
exato dos pontos (quais indices sao mao direita/esquerda, pose, face) sera
fixado pelo Tracking Engine da V2 — os TODOs nos profilers apontam o que
depende dessa definicao.

## Uso

```python
from core.types import Amostra
from knowledge import DatasetAnalyzer
from knowledge.reports import ReportGenerator

analise = DatasetAnalyzer(caminho_versoes="datasets/versions.json").analisar(amostras)
print(ReportGenerator().gerar_markdown(analise))
```

Com o AI Research Assistant (requer `pip install anthropic` e credenciais):

```python
from knowledge.ai_assistant import AIResearchAssistant, ProvedorAnthropic

assistente = AIResearchAssistant(ProvedorAnthropic())
print(assistente.analisar_dataset(analise))
```

## Integracao com o LSAE

O LSAE consultara os perfis (`PerfilSinal`, `PerfilSinalizante`), os limites
naturais de variacao e as relacoes entre sinais para gerar amostras
sinteticas realistas — em vez de depender apenas de parametros manuais.
