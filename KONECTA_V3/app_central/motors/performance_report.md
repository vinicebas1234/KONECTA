# Relatório de performance — Motor KONECTA V3

Data: 2026-08-11  
Escopo: somente `app_central/motors/`.

## Gargalos encontrados

- O detector `mp.solutions.hands.Hands` era construído e fechado para cada frame. Isso elimina o tracking temporal do MediaPipe e adiciona inicialização nativa ao caminho crítico.
- O classificador executava `predict()` e `predict_proba()` para o mesmo vetor. Em classificadores scikit-learn com `classes_`, a classe de maior probabilidade é a mesma decisão, logo uma chamada é suficiente.
- TensorFlow e o modelo de sequência eram carregados no construtor, embora o processamento de frame estático não os use.
- A montagem dos 63 valores dos landmarks era feita com `list.extend` em loop Python.
- Não havia telemetria por etapa, cache limitado, nem uma forma de processar uma coleção de frames.

## Implementação

- MediaPipe é criado sob demanda e reutilizado até `close()`. A configuração de detecção/tracking foi mantida.
- `classifier.joblib` e `metadata.json` são carregados somente no primeiro `process`; `sequence_model.keras` possui carregamento tardio separado.
- `np.fromiter(..., dtype=np.float32, count=63)` cria o vetor de landmarks sem a lista intermediária.
- Um LRU de landmarks (32 entradas por padrão) usa BLAKE2b do frame inteiro. O digest completo evita que um cache hit devolva landmarks de outro frame e, portanto, não reduz a acurácia.
- `process_batch()` mantém a ordem e reaproveita os recursos inicializados. `benchmark_performance()` mede média, P50/P95/P99, FPS, cache e cada etapa.

## Comparação estrutural

| Caminho | Antes | Depois |
| --- | ---: | ---: |
| Inicializações MediaPipe / 100 frames | 100 | 1 (sob demanda) |
| Fechamentos MediaPipe / 100 frames | 100 | 0 durante o streaming; 1 em `close()` |
| Inferências do classificador / frame com `predict_proba` | 2 | 1 |
| TensorFlow no caminho de frame estático | carregado no construtor | não carregado |
| Cache de landmarks | não | LRU, 32 entradas |

## Teste executado (100 frames)

O resultado completo está em `benchmark_results.json`.

| Métrica | Resultado |
| --- | ---: |
| Latência média | 1,065 ms |
| P95 | 1,156 ms |
| P99 | 3,375 ms |
| FPS | 939,35 |
| Cache hits / misses | 99 / 1 |
| Validação de classificação | aprovada (`SINAL_7`, confiança 0,8) |

O ensaio é uma validação determinística do pipeline: 100 referências ao mesmo frame BGR de 480×640, detector MediaPipe simulado e classificador compatível com scikit-learn simulado. Ele confirma cache, mapeamento de label, percentis e que a otimização de `predict_proba` preserva a decisão.

## Limitação e próximo passo obrigatório

Não havia `classifier.joblib`, `metadata.json` nem `sequence_model.keras` do SIGNLAB no workspace. Por isso, os números acima **não** representam a latência/accuracy final do modelo real e não devem ser usados para afirmar formalmente a meta de 150 ms. Com os artefatos disponíveis, execute o mesmo `benchmark_performance(frames)` usando 100 frames rotulados; compare o label contra o baseline e aceite a alteração somente se a acurácia for igual ou superior e P95 ficar abaixo de 150 ms.
