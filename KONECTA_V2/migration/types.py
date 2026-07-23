"""Tipos do módulo de Migração V1 — Etapa 13."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModeloV1Info:
    """Informações sobre modelo V1."""

    nome: str
    caminho: str
    tipo: str  # "dinamico", "estatico", "rf"
    acurácia_v1: float
    data_treinamento: str
    n_amostras_treino: int


@dataclass
class ComparacaoV1V2:
    """Comparação entre V1 e V2."""

    modelo_v1: ModeloV1Info
    acurácia_v1: float
    acurácia_v2: float
    melhoria: float  # (V2 - V1) / V1 * 100
    tempo_v1_ms: float
    tempo_v2_ms: float
    compatibilidade_dados: float  # Quanto dos dados V1 roda em V2


@dataclass
class RelatorioMigracao:
    """Relatório completo de migração."""

    versao_v1: str
    versao_v2: str
    modelos_encontrados: list[ModeloV1Info]
    comparacoes: list[ComparacaoV1V2]
    status_migracao: str  # "completo", "parcial", "compatibilidade_baixa"
    recomendacoes: list[str]
    pontuacao_migracao: float  # 0-1
