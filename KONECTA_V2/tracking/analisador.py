"""Análise de trajetórias e detecção de movimento em sinais."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from mediapipe_engine.types import LandmarksFrame
from tracking.types import (
    AnaliseMao,
    AnaliseTrajetoria,
    Dominancia,
    LocalTrajetoria,
    TrajetoData,
)


class AnalisadorTrajetoria:
    """Analisa trajetórias de landmarks para caracterizar sinais."""

    def __init__(self):
        # Índices do MediaPipe Pose para referência (corpo)
        self.idx_ombro_esq = 11
        self.idx_ombro_dir = 12
        self.idx_quadril_esq = 23
        self.idx_quadril_dir = 24

    def analisar_landmarks(
        self,
        id_sessao: str,
        landmarks_maos: list[LandmarksFrame],
        landmarks_corpo: Optional[list[LandmarksFrame]] = None,
    ) -> AnaliseTrajetoria:
        """Analisa trajetórias completas de mãos em uma sessão."""
        # Extrair trajetórias
        trajetorias_dir = self._extrair_trajetorias(landmarks_maos, "direita")
        trajetorias_esq = self._extrair_trajetorias(landmarks_maos, "esquerda")

        # Analisar movimento
        analise_dir = self._analisar_mao(trajetorias_dir, "direita", landmarks_maos)
        analise_esq = self._analisar_mao(trajetorias_esq, "esquerda", landmarks_maos)

        # Determinar dominância
        dominancia = self._determinar_dominancia(analise_dir, analise_esq)

        # Localização principal
        local = self._determinar_local_principal(trajetorias_dir, trajetorias_esq)

        # Complexidade
        complexidade = self._estimar_complexidade(trajetorias_dir, trajetorias_esq)

        # Montar resultado
        maos = {}
        if analise_dir:
            maos["direita"] = analise_dir
        if analise_esq:
            maos["esquerda"] = analise_esq

        velocidade_media = np.mean(
            [m.velocidade_media for m in maos.values() if m]
        ) if maos else 0.0

        duracao = len(landmarks_maos)

        return AnaliseTrajetoria(
            id_sessao=id_sessao,
            dominancia=dominancia,
            local_principal=local,
            maos=maos,
            duracao_movimento_frames=duracao,
            velocidade_media_geral=float(velocidade_media),
            complexidade_estimada=complexidade,
        )

    def _extrair_trajetorias(
        self,
        landmarks_lista: list[LandmarksFrame],
        lado: str,
    ) -> dict[str, TrajetoData]:
        """Extrai trajetórias de todos os 21 pontos de uma mão."""
        trajetorias = {}

        if not landmarks_lista or not landmarks_lista[0].mao_direita:
            return trajetorias

        # 21 pontos na mão (0-20)
        for idx in range(21):
            xs, ys, zs, confiancas = [], [], [], []

            for frame in landmarks_lista:
                mao = (
                    frame.mao_direita if lado == "direita"
                    else frame.mao_esquerda
                )
                if idx < len(mao):
                    ponto = mao[idx]
                    xs.append(ponto.x)
                    ys.append(ponto.y)
                    zs.append(ponto.z)
                    confiancas.append(ponto.confianca)

            if xs:  # Se temos dados
                nome_ponto = self._nomear_ponto(idx)
                trajetorias[nome_ponto] = TrajetoData(
                    nome_ponto=nome_ponto,
                    xs=xs,
                    ys=ys,
                    zs=zs,
                    confiancas=confiancas,
                )

        return trajetorias

    def _analisar_mao(
        self,
        trajetorias: dict[str, TrajetoData],
        lado: str,
        landmarks_lista: list[LandmarksFrame],
    ) -> Optional[AnaliseMao]:
        """Analisa estatísticas de uma mão."""
        if not trajetorias:
            return None

        # Velocidades
        velocidades = []
        for traj in trajetorias.values():
            vel = traj.comprimento_pixel / traj.n_frames if traj.n_frames > 1 else 0
            velocidades.append(vel)

        velocidade_media = np.mean(velocidades) if velocidades else 0.0

        # Amplitude (distância máxima percorrida)
        amplitudes = [t.comprimento_pixel for t in trajetorias.values()]
        amplitude_total = sum(amplitudes)

        # Detectar frames com movimento
        frames_ativos = self._contar_frames_ativos(landmarks_lista, lado)

        # Estabilidade (inversamente proporcional à variação de velocidade)
        var_velocidade = np.std(velocidades) if len(velocidades) > 1 else 0.0
        estabilidade = 1.0 / (1.0 + var_velocidade) if var_velocidade > 0 else 1.0

        return AnaliseMao(
            lado=lado,
            dominancia_estimada=Dominancia.INDEFINIDA,
            ativa_em_frames=frames_ativos,
            velocidade_media=float(velocidade_media),
            amplitude_total=float(amplitude_total),
            estabilidade=float(estabilidade),
            trajetorias=trajetorias,
        )

    def _determinar_dominancia(
        self,
        analise_dir: Optional[AnaliseMao],
        analise_esq: Optional[AnaliseMao],
    ) -> Dominancia:
        """Determina qual mão é dominante no sinal."""
        if not analise_dir and not analise_esq:
            return Dominancia.INDEFINIDA
        if not analise_dir:
            return Dominancia.ESQUERDA
        if not analise_esq:
            return Dominancia.DIREITA

        # Ambas presentes: comparar atividade
        if analise_dir.ativa_em_frames > analise_esq.ativa_em_frames * 1.5:
            return Dominancia.DIREITA
        elif analise_esq.ativa_em_frames > analise_dir.ativa_em_frames * 1.5:
            return Dominancia.ESQUERDA
        else:
            return Dominancia.AMBAS

    def _determinar_local_principal(
        self,
        trajetorias_dir: dict[str, TrajetoData],
        trajetorias_esq: dict[str, TrajetoData],
    ) -> LocalTrajetoria:
        """Determina onde no espaço a trajetória principal ocorre."""
        todas_trajetorias = list(trajetorias_dir.values()) + list(
            trajetorias_esq.values()
        )
        if not todas_trajetorias:
            return LocalTrajetoria.NEUTRO

        ys = [y for t in todas_trajetorias for y in t.ys]
        y_media = np.mean(ys) if ys else 0.5

        if y_media < 0.3:
            return LocalTrajetoria.ALTO
        elif y_media > 0.7:
            return LocalTrajetoria.BAIXO
        else:
            return LocalTrajetoria.NEUTRO

    def _estimar_complexidade(
        self,
        trajetorias_dir: dict[str, TrajetoData],
        trajetorias_esq: dict[str, TrajetoData],
    ) -> float:
        """Estima complexidade do sinal baseado em variedade de movimentos."""
        todas_trajetorias = list(trajetorias_dir.values()) + list(
            trajetorias_esq.values()
        )
        if not todas_trajetorias:
            return 0.0

        # Complexidade = número de trajetórias com movimento significativo
        trajetorias_ativas = sum(
            1 for t in todas_trajetorias if t.comprimento_pixel > 0.05
        )

        complexidade = trajetorias_ativas / max(len(todas_trajetorias), 1)
        return float(complexidade)

    def _contar_frames_ativos(
        self,
        landmarks_lista: list[LandmarksFrame],
        lado: str,
    ) -> int:
        """Conta frames onde a mão foi detectada com confiança."""
        mao_attr = "mao_direita" if lado == "direita" else "mao_esquerda"
        contador = 0

        for frame in landmarks_lista:
            mao = getattr(frame, mao_attr)
            if mao and len(mao) > 0:
                confianca_media = np.mean([p.confianca for p in mao])
                if confianca_media > 0.3:
                    contador += 1

        return contador

    @staticmethod
    def _nomear_ponto(idx: int) -> str:
        """Nomeia um ponto da mão (0-20) de acordo com MediaPipe Hand."""
        nomes = [
            "polegar_base",
            "polegar_p1",
            "polegar_p2",
            "polegar_ponta",
            "indice_base",
            "indice_p1",
            "indice_p2",
            "indice_ponta",
            "medio_base",
            "medio_p1",
            "medio_p2",
            "medio_ponta",
            "anelar_base",
            "anelar_p1",
            "anelar_p2",
            "anelar_ponta",
            "mindinho_base",
            "mindinho_p1",
            "mindinho_p2",
            "mindinho_ponta",
            "palma_centro",
        ]
        return nomes[idx] if idx < len(nomes) else f"ponto_{idx}"
