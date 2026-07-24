"""Perfil estatistico de cada sinal.

Permite compreender automaticamente quais sinais sao mais dificeis de
reconhecer (alta variabilidade, curta duracao, alta similaridade com outros)
e alimenta o LSAE com limites naturais de variacao por sinal.
"""

from __future__ import annotations

import numpy as np

from core.types import Amostra, PerfilSinal
from knowledge.signer_profiler import _amplitude, _velocidades


class SignalProfiler:
    """Constroi o perfil de um sinal a partir de todas as suas execucoes."""

    def perfilar(self, sinal: str, amostras: list[Amostra]) -> PerfilSinal:
        vels = [v for a in amostras if (v := _velocidades(a)) is not None]
        amps = [amp for a in amostras if (amp := _amplitude(a)) is not None]
        duracoes = [a.duracao_s for a in amostras if a.duracao_s is not None]

        velocidades_medias = [v.mean() for v in vels]
        return PerfilSinal(
            sinal=sinal,
            n_amostras=len(amostras),
            n_sinalizantes=len({a.sinalizante for a in amostras}),
            velocidade_media=float(np.mean(velocidades_medias)) if vels else None,
            aceleracao_media=(
                float(np.mean([np.abs(np.diff(v)).mean() for v in vels if len(v) > 1]))
                if any(len(v) > 1 for v in vels)
                else None
            ),
            amplitude_media=float(np.mean(amps)) if amps else None,
            duracao_media_s=float(np.mean(duracoes)) if duracoes else None,
            # Complexidade: proxy inicial = variacao de velocidade dentro da
            # execucao (sinais com muitas mudancas de ritmo sao mais complexos).
            complexidade=(
                float(np.mean([np.std(v) for v in vels])) if vels else None
            ),
            variabilidade=(
                float(np.std(velocidades_medias)) if len(vels) > 1 else None
            ),
            estabilidade=(
                float(1.0 / (1.0 + np.std(velocidades_medias)))
                if len(vels) > 1
                else None
            ),
            # taxa_confusao e preenchida pos-treino, a partir da matriz de
            # confusao produzida pelo AI Engine.
            taxa_confusao=None,
            trajetoria_media=self._trajetoria_media(amostras),
        )

    @staticmethod
    def _trajetoria_media(amostras: list[Amostra], n_frames: int = 30) -> np.ndarray | None:
        """Trajetoria media do sinal, com cada execucao reamostrada para `n_frames`."""
        sequencias = []
        for a in amostras:
            if a.landmarks is None or a.landmarks.shape[0] < 2:
                continue
            origem = np.linspace(0.0, 1.0, a.landmarks.shape[0])
            destino = np.linspace(0.0, 1.0, n_frames)
            pontos, coords = a.landmarks.shape[1], a.landmarks.shape[2]
            reamostrada = np.empty((n_frames, pontos, coords))
            for p in range(pontos):
                for c in range(coords):
                    reamostrada[:, p, c] = np.interp(destino, origem, a.landmarks[:, p, c])
            sequencias.append(reamostrada)
        if not sequencias:
            return None
        return np.mean(np.stack(sequencias), axis=0)
