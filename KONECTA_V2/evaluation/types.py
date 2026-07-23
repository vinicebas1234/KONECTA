"""Tipos do módulo de Avaliação — Etapa 11."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MetricasCrossSigners:
    """Métricas de desempenho cross-signer."""

    sinal: str
    n_sinalizantes: int
    acurácia_media: float
    acurácia_minima: float
    acurácia_maxima: float
    variancia_cross_signer: float  # Quão consistente é entre signatários
    sinalizantes_problematicos: list[str] = field(default_factory=list)


@dataclass
class MatrizConfusaoDetalhada:
    """Matriz de confusão com análise detalhada."""

    sinais: list[str]
    matriz: list[list[int]]
    precisao_por_sinal: dict[str, float]
    recall_por_sinal: dict[str, float]
    f1_por_sinal: dict[str, float]


@dataclass
class RelatorioAvaliacao:
    """Relatório completo de avaliação."""

    acurácia_geral: float
    macro_f1: float
    weighted_f1: float

    cross_signer_metrics: dict[str, MetricasCrossSigners]
    matriz_confusao: MatrizConfusaoDetalhada

    sinais_problematicos: list[str]
    sinalizantes_problematicos: dict[str, float]  # sinalizante -> taxa_erro

    recomendacoes: list[str] = field(default_factory=list)
    tempo_avaliacao_s: float = 0.0
