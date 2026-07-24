"""Relacoes estatisticas entre sinais: quais sao semelhantes e por que.

Essas relacoes auxiliam treinamento, augmentation, explicabilidade e a
analise de erros (ex.: CASA e muito semelhante a PREDIO; principal
diferenca: orientacao da palma).
"""

from __future__ import annotations

import numpy as np

from core.types import Amostra, RelacaoSinais
from knowledge.embeddings import EmbeddingEngine


class SimilarityEngine:
    """Constroi a matriz de similaridade e as relacoes entre sinais."""

    def __init__(self, embeddings: EmbeddingEngine | None = None, limiar: float = 0.9):
        self.embeddings = embeddings or EmbeddingEngine()
        self.limiar = limiar

    def matriz(self, amostras: list[Amostra]) -> tuple[list[str], np.ndarray]:
        """Matriz de similaridade de cosseno entre os centroides dos sinais."""
        centroides = self.embeddings.gerar_por_sinal(amostras)
        sinais = sorted(centroides)
        if not sinais:
            return [], np.empty((0, 0))
        base = np.stack([centroides[s] for s in sinais])
        return sinais, base @ base.T  # embeddings ja normalizados

    def relacoes(self, amostras: list[Amostra]) -> list[RelacaoSinais]:
        """Pares de sinais com similaridade acima do limiar configurado."""
        sinais, matriz = self.matriz(amostras)
        resultado = []
        for i in range(len(sinais)):
            for j in range(i + 1, len(sinais)):
                similaridade = float(matriz[i, j])
                if similaridade >= self.limiar:
                    resultado.append(RelacaoSinais(
                        sinal_a=sinais[i],
                        sinal_b=sinais[j],
                        similaridade=similaridade,
                        principal_diferenca=None,
                        # TODO: identificar automaticamente a principal
                        # diferenca (orientacao da palma, trajetoria, maos)
                        # comparando os componentes do descritor por grupo
                        # de landmarks — depende do layout de pontos do
                        # Tracking Engine da V2.
                    ))
        resultado.sort(key=lambda r: r.similaridade, reverse=True)
        return resultado

    def sinais_semelhantes(
        self, amostras: list[Amostra], sinal: str, top_n: int = 5
    ) -> list[RelacaoSinais]:
        """Os `top_n` sinais mais proximos de `sinal` (busca por semelhanca)."""
        sinais, matriz = self.matriz(amostras)
        if sinal not in sinais:
            return []
        i = sinais.index(sinal)
        vizinhos = sorted(
            (j for j in range(len(sinais)) if j != i),
            key=lambda j: matriz[i, j],
            reverse=True,
        )[:top_n]
        return [
            RelacaoSinais(sinal_a=sinal, sinal_b=sinais[j], similaridade=float(matriz[i, j]))
            for j in vizinhos
        ]
