"""Avaliação completa de modelos com análise cross-signer."""

from __future__ import annotations

import time
from collections import defaultdict

import numpy as np
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

from ai_engine import TreinadorModelo
from core.types import Amostra
from evaluation.types import (
    MatrizConfusaoDetalhada,
    MetricasCrossSigners,
    RelatorioAvaliacao,
)


class AvaliadorModelo:
    """Avalia desempenho com análise cross-signer."""

    def __init__(self, treinador: TreinadorModelo):
        self.treinador = treinador
        self.modelo = treinador.modelo
        self.scaler = treinador.scaler
        self.classes = treinador.classes

    def avaliar_cross_signer(
        self, amostras: list[Amostra]
    ) -> RelatorioAvaliacao:
        """Avalia desempenho cross-signer (por sinalizante)."""
        tempo_inicio = time.time()

        # Preparar dados
        X, y, _ = self.treinador.preparar_dados(amostras)
        X_norm = self.scaler.transform(X)

        # Predições
        y_pred = self.modelo.predict(X_norm)

        # Métricas gerais
        acuracia_geral = np.mean(y_pred == y)
        f1_macro = f1_score(y, y_pred, average="macro", zero_division=0)
        f1_weighted = f1_score(y, y_pred, average="weighted", zero_division=0)

        # Matriz de confusão
        cm = confusion_matrix(y, y_pred, labels=np.arange(len(self.classes)))
        matriz_detalhada = self._criar_matriz_detalhada(cm, y, y_pred)

        # Cross-signer: agrupar por sinalizante
        cross_signer = self._calcular_cross_signer(amostras, y_pred)

        # Sinais problemáticos
        sinais_problematicos = [
            s for s, m in cross_signer.items()
            if m.acurácia_media < 0.7
        ]

        # Sinalizantes problemáticos
        sinalizantes_problematicos = self._calcular_sinalizantes_problematicos(
            amostras, y_pred
        )

        # Recomendações
        recomendacoes = self._gerar_recomendacoes(
            cross_signer,
            sinais_problematicos,
            sinalizantes_problematicos,
        )

        tempo_avaliacao = time.time() - tempo_inicio

        return RelatorioAvaliacao(
            acurácia_geral=acuracia_geral,
            macro_f1=f1_macro,
            weighted_f1=f1_weighted,
            cross_signer_metrics=cross_signer,
            matriz_confusao=matriz_detalhada,
            sinais_problematicos=sinais_problematicos,
            sinalizantes_problematicos=sinalizantes_problematicos,
            recomendacoes=recomendacoes,
            tempo_avaliacao_s=tempo_avaliacao,
        )

    def _criar_matriz_detalhada(
        self, cm: np.ndarray, y_true: np.ndarray, y_pred: np.ndarray
    ) -> MatrizConfusaoDetalhada:
        """Cria matriz de confusão detalhada com métricas."""
        precisao, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average=None, zero_division=0
        )

        precisao_dict = {self.classes[i]: float(p) for i, p in enumerate(precisao)}
        recall_dict = {self.classes[i]: float(r) for i, r in enumerate(recall)}
        f1_dict = {self.classes[i]: float(f) for i, f in enumerate(f1)}

        return MatrizConfusaoDetalhada(
            sinais=list(self.classes),
            matriz=cm.tolist(),
            precisao_por_sinal=precisao_dict,
            recall_por_sinal=recall_dict,
            f1_por_sinal=f1_dict,
        )

    def _calcular_cross_signer(
        self, amostras: list[Amostra], y_pred: np.ndarray
    ) -> dict[str, MetricasCrossSigners]:
        """Calcula métricas por sinal e sinalizante."""
        # Agrupar por sinal
        por_sinal = defaultdict(list)
        for i, amostra in enumerate(amostras):
            if i < len(y_pred):
                acerto = (y_pred[i] == np.where(self.classes == amostra.sinal)[0][0])
                por_sinal[amostra.sinal].append({
                    "sinalizante": amostra.sinalizante,
                    "acerto": acerto,
                })

        # Calcular métricas por sinal
        resultado = {}
        for sinal, dados in por_sinal.items():
            acertos = [d["acerto"] for d in dados]
            por_sinalizante = defaultdict(list)
            for d in dados:
                por_sinalizante[d["sinalizante"]].append(d["acerto"])

            acuracias_por_sinalizante = {
                s: np.mean(a) for s, a in por_sinalizante.items()
            }

            acurácia_media = np.mean(acertos)
            acurácia_minima = min(acuracias_por_sinalizante.values())
            acurácia_maxima = max(acuracias_por_sinalizante.values())
            variancia = np.var(list(acuracias_por_sinalizante.values()))

            sinalizantes_problematicos = [
                s for s, a in acuracias_por_sinalizante.items()
                if a < acurácia_media - 0.15
            ]

            resultado[sinal] = MetricasCrossSigners(
                sinal=sinal,
                n_sinalizantes=len(por_sinalizante),
                acurácia_media=acurácia_media,
                acurácia_minima=acurácia_minima,
                acurácia_maxima=acurácia_maxima,
                variancia_cross_signer=variancia,
                sinalizantes_problematicos=sinalizantes_problematicos,
            )

        return resultado

    def _calcular_sinalizantes_problematicos(
        self, amostras: list[Amostra], y_pred: np.ndarray
    ) -> dict[str, float]:
        """Calcula taxa de erro por sinalizante."""
        por_sinalizante = defaultdict(list)

        for i, amostra in enumerate(amostras):
            if i < len(y_pred):
                acerto = (y_pred[i] == np.where(self.classes == amostra.sinal)[0][0])
                por_sinalizante[amostra.sinalizante].append(acerto)

        resultado = {}
        for sinalizante, acertos in por_sinalizante.items():
            taxa_erro = 1.0 - np.mean(acertos)
            if taxa_erro > 0.2:  # >20% de erro
                resultado[sinalizante] = taxa_erro

        return resultado

    @staticmethod
    def _gerar_recomendacoes(
        cross_signer: dict[str, MetricasCrossSigners],
        sinais_problematicos: list[str],
        sinalizantes_problematicos: dict[str, float],
    ) -> list[str]:
        """Gera recomendações baseadas na avaliação."""
        recomendacoes = []

        if sinais_problematicos:
            sinais_str = ", ".join(sinais_problematicos[:3])
            recomendacoes.append(
                f"Coletar mais amostras dos sinais: {sinais_str}"
            )

        if sinalizantes_problematicos:
            sinalizantes_str = ", ".join(
                list(sinalizantes_problematicos.keys())[:3]
            )
            recomendacoes.append(
                f"Revisar coleta dos sinalizantes: {sinalizantes_str}"
            )

        # Variância cross-signer
        high_variance = [
            (s, m.variancia_cross_signer)
            for s, m in cross_signer.items()
            if m.variancia_cross_signer > 0.05
        ]
        if high_variance:
            sinais_var = ", ".join([s for s, _ in high_variance[:2]])
            recomendacoes.append(
                f"Alta variância entre sinalizantes: {sinais_var} — treinar com mais diversidade"
            )

        return recomendacoes
