"""Embeddings dos sinais — representacao vetorial de cada execucao.

A implementacao inicial usa um descritor estatistico determinista (media,
dispersao e dinamica dos landmarks), suficiente para busca por similaridade
e deteccao de vizinhos. Futuramente pode ser substituida por embeddings
aprendidos (encoder do proprio modelo de reconhecimento) sem mudar o contrato.
"""

from __future__ import annotations

import numpy as np

from core.types import Amostra


class EmbeddingEngine:
    """Gera um vetor de tamanho fixo para cada amostra."""

    def gerar(self, amostra: Amostra) -> np.ndarray | None:
        if amostra.landmarks is None or amostra.landmarks.shape[0] < 2:
            return None
        seq = amostra.landmarks  # (frames, pontos, 3)
        deslocamentos = np.diff(seq, axis=0)
        velocidade = np.linalg.norm(deslocamentos, axis=2)  # (frames-1, pontos)

        partes = [
            seq.mean(axis=0).ravel(),          # postura media
            seq.std(axis=0).ravel(),           # dispersao espacial por ponto
            velocidade.mean(axis=0),           # dinamica media por ponto
            velocidade.std(axis=0),            # variacao da dinamica por ponto
        ]
        vetor = np.concatenate(partes)
        norma = np.linalg.norm(vetor)
        return vetor / norma if norma > 0 else vetor

    def gerar_por_sinal(self, amostras: list[Amostra]) -> dict[str, np.ndarray]:
        """Embedding medio de cada sinal (centroide das execucoes)."""
        por_sinal: dict[str, list[np.ndarray]] = {}
        for a in amostras:
            emb = self.gerar(a)
            if emb is not None:
                por_sinal.setdefault(a.sinal, []).append(emb)
        return {
            sinal: np.mean(np.stack(embs), axis=0)
            for sinal, embs in por_sinal.items()
        }
