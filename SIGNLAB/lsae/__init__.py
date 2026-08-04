"""LSAE — Libras Semantic Augmentation Engine.

Aumenta a diversidade dos dados de treinamento gerando variações
plausíveis das representações estruturadas dos sinais (landmarks):
variação espacial, temporal, jitter, ruído controlado, escala, rotação.

Regra obrigatória (anti data-leakage): o LSAE só é aplicado ao conjunto
de TREINO, após o split. Validação e teste permanecem originais.

Implementação prevista na Fase 4 do roadmap.
"""
