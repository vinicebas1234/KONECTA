"""Recomendacoes inteligentes de novas coletas.

Depois de analisar o dataset, sugere automaticamente onde investir o esforco
de coleta: sinais com poucas amostras, pouca diversidade de sinalizantes ou
alta similaridade com outros sinais.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.types import (
    EstatisticasDataset,
    PerfilSinal,
    Prioridade,
    Recomendacao,
    RelacaoSinais,
)


@dataclass
class ConfigRecomendacoes:
    min_amostras_por_sinal: int = 10
    min_sinalizantes_por_sinal: int = 2
    min_sinalizantes_dataset: int = 5
    balanceamento_minimo: float = 0.85


class RecommendationEngine:
    """Gera recomendacoes priorizadas a partir da analise do dataset."""

    def __init__(self, config: ConfigRecomendacoes | None = None):
        self.config = config or ConfigRecomendacoes()

    def gerar(
        self,
        estatisticas: EstatisticasDataset,
        perfis_sinais: dict[str, PerfilSinal],
        relacoes: list[RelacaoSinais] | None = None,
    ) -> list[Recomendacao]:
        cfg = self.config
        recomendacoes: list[Recomendacao] = []

        poucas_amostras = sorted(
            (s for s, n in estatisticas.amostras_por_sinal.items()
             if n < cfg.min_amostras_por_sinal),
            key=lambda s: estatisticas.amostras_por_sinal[s],
        )
        if poucas_amostras:
            recomendacoes.append(Recomendacao(
                titulo="Coletar mais amostras para sinais sub-representados",
                motivo=(
                    f"{len(poucas_amostras)} sinais possuem menos de "
                    f"{cfg.min_amostras_por_sinal} amostras"
                ),
                prioridade=Prioridade.ALTA,
                sinais=poucas_amostras,
            ))

        poucos_sinalizantes = sorted(
            s for s, p in perfis_sinais.items()
            if p.n_sinalizantes < cfg.min_sinalizantes_por_sinal
        )
        if poucos_sinalizantes:
            recomendacoes.append(Recomendacao(
                titulo="Aumentar diversidade de sinalizantes por sinal",
                motivo=(
                    f"{len(poucos_sinalizantes)} sinais foram executados por menos de "
                    f"{cfg.min_sinalizantes_por_sinal} sinalizantes — risco de o modelo "
                    "aprender o estilo do articulador em vez do sinal"
                ),
                prioridade=Prioridade.ALTA,
                sinais=poucos_sinalizantes,
            ))

        if estatisticas.n_sinalizantes < cfg.min_sinalizantes_dataset:
            recomendacoes.append(Recomendacao(
                titulo="Recrutar novos sinalizantes",
                motivo=(
                    f"O dataset possui apenas {estatisticas.n_sinalizantes} sinalizantes; "
                    "baixa diversidade limita a generalizacao cross-signer"
                ),
                prioridade=Prioridade.MEDIA,
            ))

        if estatisticas.balanceamento < cfg.balanceamento_minimo:
            recomendacoes.append(Recomendacao(
                titulo="Rebalancear a distribuicao entre classes",
                motivo=(
                    f"Balanceamento (entropia normalizada) em "
                    f"{estatisticas.balanceamento:.2f}, abaixo do alvo de "
                    f"{cfg.balanceamento_minimo}"
                ),
                prioridade=Prioridade.MEDIA,
            ))

        for relacao in (relacoes or [])[:5]:
            recomendacoes.append(Recomendacao(
                titulo=f"Revisar par confundivel {relacao.sinal_a} x {relacao.sinal_b}",
                motivo=(
                    f"Similaridade de {relacao.similaridade:.2f} entre os sinais — "
                    "priorizar coletas que acentuem a diferenca e monitorar a "
                    "matriz de confusao pos-treino"
                ),
                prioridade=Prioridade.BAIXA,
                sinais=[relacao.sinal_a, relacao.sinal_b],
            ))

        return recomendacoes
