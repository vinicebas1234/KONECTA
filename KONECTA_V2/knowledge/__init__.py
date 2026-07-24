"""Knowledge Engine — compreensao profunda de datasets de Libras.

Este motor nao reconhece sinais. Ele aprende continuamente sobre os dados:
estatisticas do dataset, perfis de sinalizantes e de sinais, qualidade das
amostras, relacoes entre sinais, recomendacoes de coleta e versionamento.
E a principal fonte de conhecimento do LSAE e do AI Research Assistant.
"""

from knowledge.dataset_analyzer import DatasetAnalyzer

__all__ = ["DatasetAnalyzer"]
