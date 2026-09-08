"""Dataset, treino (protótipos + DTW), avaliação e inferência do Libras Learning Agent.

Ciclo 7. "Treino" aqui não é rede neural: é a abordagem que o próprio projeto já
mediu como superior nesta escala de dados — ver
`KONECTA_V3/RECONHECIMENTO_RECOMENDACAO.md`, seção 5.1. Com 1.364 sinais e ~6
amostras de 3 sinalizantes, uma LSTM treinada deu 0,44% de acurácia cross-signer
(quase acaso); DTW com kNN sobre as amostras cruas, sem treinar nada, deu 1,54%,
subindo para 47,4% top-1 num vocabulário de 20 sinais. Este pacote reproduz essa
abordagem já validada, num vocabulário pequeno (ver `ml/dataset.py`).

Isolamento: nada aqui é importado de `app_central` (a normalização em
`ml/features.py` é reimplementada a partir do mesmo contrato documentado, não
importada) nem escreve fora de `libras_learning_agent/` — ver `core/config.py`.
"""
