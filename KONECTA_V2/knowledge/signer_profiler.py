"""Perfil estatistico de cada sinalizante.

Aprende velocidade, amplitude, estabilidade e habitos de execucao de cada
articulador — insumo para pesquisas de generalizacao entre usuarios e para
o LSAE gerar variacoes realistas.
"""

from __future__ import annotations

import numpy as np

from core.types import Amostra, Dominancia, PerfilSinalizante


def _velocidades(amostra: Amostra) -> np.ndarray | None:
    """Norma da velocidade media dos pontos por frame (unidades normalizadas/s)."""
    if amostra.landmarks is None or amostra.landmarks.shape[0] < 2:
        return None
    fps = amostra.fps or 30.0
    deslocamentos = np.diff(amostra.landmarks, axis=0)  # (frames-1, pontos, 3)
    return np.linalg.norm(deslocamentos, axis=2).mean(axis=1) * fps


def _amplitude(amostra: Amostra) -> float | None:
    """Extensao espacial do movimento: diagonal da caixa que envolve a trajetoria."""
    if amostra.landmarks is None:
        return None
    faixa = amostra.landmarks.max(axis=(0, 1)) - amostra.landmarks.min(axis=(0, 1))
    return float(np.linalg.norm(faixa))


class SignerProfiler:
    """Constroi o perfil biomecanico de um sinalizante a partir de suas amostras."""

    def perfilar(self, sinalizante: str, amostras: list[Amostra]) -> PerfilSinalizante:
        vels = [v for a in amostras if (v := _velocidades(a)) is not None]
        amps = [amp for a in amostras if (amp := _amplitude(a)) is not None]
        duracoes = [a.duracao_s for a in amostras if a.duracao_s is not None]
        perdas = [
            a.taxa_landmarks_perdidos
            for a in amostras
            if a.taxa_landmarks_perdidos is not None
        ]

        velocidade_media = float(np.mean([v.mean() for v in vels])) if vels else None
        aceleracao_media = (
            float(np.mean([np.abs(np.diff(v)).mean() for v in vels if len(v) > 1]))
            if any(len(v) > 1 for v in vels)
            else None
        )
        # Estabilidade: quanto menor a variacao da velocidade entre execucoes,
        # mais estavel o sinalizante. Mapeada para (0, 1].
        estabilidade = (
            float(1.0 / (1.0 + np.std([v.mean() for v in vels])))
            if len(vels) > 1
            else None
        )

        return PerfilSinalizante(
            sinalizante=sinalizante,
            n_amostras=len(amostras),
            velocidade_media=velocidade_media,
            aceleracao_media=aceleracao_media,
            amplitude_media=float(np.mean(amps)) if amps else None,
            estabilidade=estabilidade,
            taxa_landmarks_perdidos=float(np.mean(perdas)) if perdas else None,
            tempo_medio_por_sinal_s=float(np.mean(duracoes)) if duracoes else None,
            # TODO(fase Tracking Engine): dominancia exige distinguir mao
            # esquerda/direita nos landmarks — depende do layout de pontos
            # que o Tracking Engine da V2 definir.
            dominancia=Dominancia.INDEFINIDA,
            variabilidade=(
                float(np.std([v.mean() for v in vels])) if len(vels) > 1 else None
            ),
        )
