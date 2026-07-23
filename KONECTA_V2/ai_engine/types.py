"""Tipos do AI Engine — Treinamento e avaliação de modelos."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TipoModelo(str, Enum):
    """Tipos de modelos disponíveis."""

    RANDOM_FOREST = "random_forest"
    NEURAL_NETWORK = "neural_network"
    SVM = "svm"
    KNN = "knn"


@dataclass
class MetricasDesempenho:
    """Métricas de desempenho de um modelo."""

    acuracia: float
    precisao: float
    recall: float
    f1_score: float
    auc_roc: float


@dataclass
class ResultadoTreinamento:
    """Resultado do treinamento de um modelo."""

    tipo_modelo: TipoModelo
    metricas_treino: MetricasDesempenho
    metricas_validacao: MetricasDesempenho
    metricas_teste: MetricasDesempenho
    tempo_treinamento_s: float
    n_amostras_treino: int
    n_amostras_validacao: int
    n_amostras_teste: int
    melhor_parametro: str = ""


@dataclass
class MatrizConfusao:
    """Matriz de confusão de um modelo."""

    sinais: list[str]
    matriz: list[list[int]]  # sinais x sinais
    acertos_diagonais: int = 0
    erros_totais: int = 0

    @property
    def taxa_acerto(self) -> float:
        """Taxa de acertos (diagonal / total)."""
        total = sum(sum(linha) for linha in self.matriz)
        if total == 0:
            return 0.0
        return self.acertos_diagonais / total


@dataclass
class AnaliseErros:
    """Análise de quais sinais são confundidos."""

    confusoes_principais: list[tuple[str, str, int]] = field(
        default_factory=list
    )  # (sinal_real, sinal_predito, count)
    sinais_problematicos: dict[str, int] = field(
        default_factory=dict
    )  # sinal -> taxa_erro
    recomendacoes: list[str] = field(default_factory=list)
