"""Controle inteligente de qualidade das amostras.

Somente amostras aprovadas aqui devem ser adicionadas ao dataset principal.
Os limiares vem de `configs/knowledge.yaml`.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.types import (
    Amostra,
    Prioridade,
    ProblemaQualidade,
    ResultadoQualidade,
    TipoProblema,
)


@dataclass
class ConfigQualidade:
    duracao_minima_s: float = 0.3
    duracao_maxima_s: float = 10.0
    confianca_minima: float = 0.5
    taxa_maxima_landmarks_perdidos: float = 0.3
    n_frames_minimo: int = 5


class QualityAnalyzer:
    """Avalia cada amostra individualmente contra os limiares configurados."""

    def __init__(self, config: ConfigQualidade | None = None):
        self.config = config or ConfigQualidade()

    def avaliar(self, amostra: Amostra) -> ResultadoQualidade:
        problemas: list[ProblemaQualidade] = []
        cfg = self.config

        if amostra.duracao_s is not None:
            if amostra.duracao_s < cfg.duracao_minima_s:
                problemas.append(ProblemaQualidade(
                    TipoProblema.MUITO_CURTA,
                    f"Duracao {amostra.duracao_s:.2f}s abaixo do minimo de {cfg.duracao_minima_s}s",
                    Prioridade.ALTA,
                ))
            elif amostra.duracao_s > cfg.duracao_maxima_s:
                problemas.append(ProblemaQualidade(
                    TipoProblema.MUITO_LONGA,
                    f"Duracao {amostra.duracao_s:.2f}s acima do maximo de {cfg.duracao_maxima_s}s",
                ))

        if amostra.confianca_media is not None and amostra.confianca_media < cfg.confianca_minima:
            problemas.append(ProblemaQualidade(
                TipoProblema.BAIXA_CONFIANCA,
                f"Confianca media do MediaPipe {amostra.confianca_media:.2f} abaixo de {cfg.confianca_minima}",
                Prioridade.ALTA,
            ))

        if (
            amostra.taxa_landmarks_perdidos is not None
            and amostra.taxa_landmarks_perdidos > cfg.taxa_maxima_landmarks_perdidos
        ):
            problemas.append(ProblemaQualidade(
                TipoProblema.LANDMARKS_AUSENTES,
                f"{amostra.taxa_landmarks_perdidos:.0%} dos landmarks perdidos "
                f"(maximo permitido: {cfg.taxa_maxima_landmarks_perdidos:.0%})",
                Prioridade.ALTA,
            ))

        if amostra.n_frames is not None and amostra.n_frames < cfg.n_frames_minimo:
            problemas.append(ProblemaQualidade(
                TipoProblema.MOVIMENTO_INCOMPLETO,
                f"Apenas {amostra.n_frames} frames capturados",
                Prioridade.ALTA,
            ))

        # TODO(fase Capture Engine): checagens visuais que dependem do video
        # bruto — baixa iluminacao, oclusoes, maos invertidas e deteccao de
        # duplicatas (hash perceptual ou distancia entre sequencias).

        aprovada = not any(p.severidade == Prioridade.ALTA for p in problemas)
        return ResultadoQualidade(amostra_id=amostra.id, aprovada=aprovada, problemas=problemas)
