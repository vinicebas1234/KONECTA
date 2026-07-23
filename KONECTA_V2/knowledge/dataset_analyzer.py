"""Orquestrador do Knowledge Engine.

Ponto de entrada unico: recebe as amostras (fornecidas pelo Dataset Engine)
e produz a `AnaliseDataset` completa — estatisticas, perfis, qualidade,
relacoes entre sinais, recomendacoes e versao logica.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

from core.types import Amostra, AnaliseDataset
from knowledge.dataset_statistics import DatasetStatistics
from knowledge.dataset_versioning import DatasetVersioning
from knowledge.enricher import enriquecer_lote
from knowledge.quality_analyzer import ConfigQualidade, QualityAnalyzer
from knowledge.recommendations import ConfigRecomendacoes, RecommendationEngine
from knowledge.signal_profiler import SignalProfiler
from knowledge.signer_profiler import SignerProfiler
from knowledge.similarity_engine import SimilarityEngine


class DatasetAnalyzer:
    """Executa a analise completa de um conjunto de amostras."""

    def __init__(
        self,
        config_qualidade: ConfigQualidade | None = None,
        config_recomendacoes: ConfigRecomendacoes | None = None,
        caminho_versoes: str | Path | None = None,
    ):
        self.estatisticas = DatasetStatistics()
        self.qualidade = QualityAnalyzer(config_qualidade)
        self.perfil_sinalizante = SignerProfiler()
        self.perfil_sinal = SignalProfiler()
        self.similaridade = SimilarityEngine()
        self.recomendacoes = RecommendationEngine(config_recomendacoes)
        self.versionamento = (
            DatasetVersioning(caminho_versoes) if caminho_versoes else None
        )

    def analisar(
        self,
        amostras: list[Amostra],
        resumo_versao: str = "",
        on_progresso: Optional[Callable[[str], None]] = None,
    ) -> AnaliseDataset:
        def progresso(mensagem: str) -> None:
            if on_progresso is not None:
                on_progresso(mensagem)

        # Enriquecer amostras com dados de tracking (Etapa 6)
        progresso("Enriquecendo amostras com análise de trajetória")
        try:
            amostras = enriquecer_lote(amostras)
        except Exception:
            # Se enriquecimento falhar (sem landmarks, etc), continuar
            pass

        progresso("Calculando estatisticas gerais")
        estatisticas = self.estatisticas.calcular(amostras)
        progresso("Avaliando qualidade das amostras")
        qualidade = [self.qualidade.avaliar(a) for a in amostras]

        por_sinalizante: dict[str, list[Amostra]] = defaultdict(list)
        por_sinal: dict[str, list[Amostra]] = defaultdict(list)
        for a in amostras:
            por_sinalizante[a.sinalizante].append(a)
            por_sinal[a.sinal].append(a)

        progresso("Construindo perfis dos sinalizantes")
        perfis_sinalizantes = {
            s: self.perfil_sinalizante.perfilar(s, lista)
            for s, lista in por_sinalizante.items()
        }
        progresso("Construindo perfis dos sinais")
        perfis_sinais = {
            s: self.perfil_sinal.perfilar(s, lista) for s, lista in por_sinal.items()
        }

        progresso("Calculando relacoes de similaridade entre sinais")
        relacoes = self.similaridade.relacoes(amostras)
        progresso("Gerando recomendacoes")
        recomendacoes = self.recomendacoes.gerar(estatisticas, perfis_sinais, relacoes)

        versao = None
        if self.versionamento is not None:
            versao = self.versionamento.registrar(estatisticas, resumo_versao)

        return AnaliseDataset(
            estatisticas=estatisticas,
            perfis_sinalizantes=perfis_sinalizantes,
            perfis_sinais=perfis_sinais,
            qualidade=qualidade,
            relacoes=relacoes,
            recomendacoes=recomendacoes,
            versao=versao,
        )

    # TODO(fase Dataset Engine): carregar amostras diretamente do formato de
    # armazenamento da V2 (e um adaptador de leitura para o dataset da V1 em
    # OCR/dados_libras, usado apenas durante a migracao).
