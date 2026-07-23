"""Treinamento e avaliação de modelos para reconhecimento de sinais."""

from __future__ import annotations

import time
from typing import Optional

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from ai_engine.types import (
    AnaliseErros,
    MatrizConfusao,
    MetricasDesempenho,
    ResultadoTreinamento,
    TipoModelo,
)
from core.types import Amostra


class TreinadorModelo:
    """Treina e avalia modelos de reconhecimento."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.modelo = None
        self.scaler = StandardScaler()
        self.labels = None
        self.classes = None

    def preparar_dados(
        self, amostras: list[Amostra]
    ) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """Extrai features das amostras e retorna X, y, labels."""
        X = []
        y = []
        labels = []

        for amostra in amostras:
            if amostra.landmarks is None or amostra.landmarks.shape[0] == 0:
                continue

            # Extrair features do tensor de landmarks
            features = self._extrair_features(amostra.landmarks)
            X.append(features)
            y.append(amostra.sinal)
            labels.append(amostra.id)

        if not X:
            raise ValueError("Nenhuma amostra com landmarks disponível")

        X = np.array(X)
        y = np.array(y)

        # Mapear labels de sinais para índices
        self.classes = np.unique(y)
        y_encoded = np.array([np.where(self.classes == label)[0][0] for label in y])

        return X, y_encoded, labels

    def treinar(
        self,
        amostras: list[Amostra],
        tipo_modelo: TipoModelo = TipoModelo.RANDOM_FOREST,
        test_size: float = 0.2,
        val_size: float = 0.1,
    ) -> ResultadoTreinamento:
        """Treina um modelo e retorna resultados."""
        tempo_inicio = time.time()

        # Preparar dados
        X, y, labels = self.preparar_dados(amostras)

        # Split: treino/temp -> treino/validação/teste
        X_treino, X_temp, y_treino, y_temp = train_test_split(
            X, y, test_size=(test_size + val_size), random_state=self.seed
        )

        val_ratio = val_size / (test_size + val_size)
        X_val, X_teste, y_val, y_teste = train_test_split(
            X_temp, y_temp, test_size=(1 - val_ratio), random_state=self.seed
        )

        # Normalizar
        X_treino_norm = self.scaler.fit_transform(X_treino)
        X_val_norm = self.scaler.transform(X_val)
        X_teste_norm = self.scaler.transform(X_teste)

        # Treinar modelo
        if tipo_modelo == TipoModelo.RANDOM_FOREST:
            self.modelo = RandomForestClassifier(
                n_estimators=100, random_state=self.seed, n_jobs=-1
            )
        else:
            raise NotImplementedError(f"Tipo de modelo não implementado: {tipo_modelo}")

        self.modelo.fit(X_treino_norm, y_treino)

        # Avaliar
        metricas_treino = self._calcular_metricas(
            self.modelo, X_treino_norm, y_treino
        )
        metricas_validacao = self._calcular_metricas(
            self.modelo, X_val_norm, y_val
        )
        metricas_teste = self._calcular_metricas(
            self.modelo, X_teste_norm, y_teste
        )

        tempo_treinamento = time.time() - tempo_inicio

        return ResultadoTreinamento(
            tipo_modelo=tipo_modelo,
            metricas_treino=metricas_treino,
            metricas_validacao=metricas_validacao,
            metricas_teste=metricas_teste,
            tempo_treinamento_s=tempo_treinamento,
            n_amostras_treino=len(X_treino),
            n_amostras_validacao=len(X_val),
            n_amostras_teste=len(X_teste),
            melhor_parametro="n_estimators=100",
        )

    def analisar_erros(
        self, amostras: list[Amostra]
    ) -> tuple[MatrizConfusao, AnaliseErros]:
        """Analisa erros de previsão."""
        if self.modelo is None:
            raise RuntimeError("Modelo não foi treinado")

        X, y, _ = self.preparar_dados(amostras)
        X_norm = self.scaler.transform(X)

        y_pred = self.modelo.predict(X_norm)

        # Matriz de confusão
        cm = confusion_matrix(y, y_pred, labels=np.arange(len(self.classes)))
        sinais = list(self.classes)

        matriz_confusao = MatrizConfusao(
            sinais=sinais,
            matriz=cm.tolist(),
            acertos_diagonais=np.trace(cm),
            erros_totais=len(y) - np.trace(cm),
        )

        # Análise de erros
        erros = AnaliseErros()

        for i, sinal_real in enumerate(self.classes):
            for j, sinal_pred in enumerate(self.classes):
                if i != j and cm[i, j] > 0:
                    erros.confusoes_principais.append(
                        (sinal_real, sinal_pred, int(cm[i, j]))
                    )

        # Sinais problemáticos
        for i, sinal in enumerate(self.classes):
            total_amostras_sinal = cm[i].sum()
            if total_amostras_sinal > 0:
                taxa_erro = 1.0 - (cm[i, i] / total_amostras_sinal)
                if taxa_erro > 0.2:  # 20% de erro
                    erros.sinais_problematicos[sinal] = taxa_erro

        # Recomendações
        if erros.sinais_problematicos:
            sinais_problema = ", ".join(
                f"{s} ({e*100:.1f}%)"
                for s, e in sorted(
                    erros.sinais_problematicos.items(), key=lambda x: -x[1]
                )[:3]
            )
            erros.recomendacoes.append(f"Coletar mais amostras: {sinais_problema}")

        if erros.confusoes_principais:
            confusoes_top = sorted(
                erros.confusoes_principais, key=lambda x: -x[2]
            )[:3]
            for real, pred, count in confusoes_top:
                erros.recomendacoes.append(
                    f"Revisar diferenças entre {real} e {pred} ({count} erros)"
                )

        return matriz_confusao, erros

    @staticmethod
    def _extrair_features(landmarks: np.ndarray) -> np.ndarray:
        """Extrai features de um tensor de landmarks."""
        # Flatten simples + estatísticas
        features = []

        # Flatten dos landmarks
        features.extend(landmarks.flatten())

        # Estatísticas por ponto
        velocidades = np.sqrt(np.sum(np.diff(landmarks, axis=0) ** 2, axis=-1))
        features.extend([
            np.mean(velocidades),
            np.std(velocidades),
            np.max(velocidades),
            np.min(velocidades),
        ])

        # Amplitude geral
        amplitude = np.max(landmarks) - np.min(landmarks)
        features.append(amplitude)

        return np.array(features)

    def _calcular_metricas(
        self, modelo, X: np.ndarray, y: np.ndarray
    ) -> MetricasDesempenho:
        """Calcula métricas de desempenho."""
        y_pred = modelo.predict(X)

        acuracia = accuracy_score(y, y_pred)
        precisao = precision_score(y, y_pred, average="weighted", zero_division=0)
        recall = recall_score(y, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y, y_pred, average="weighted", zero_division=0)

        # AUC-ROC (one-vs-rest)
        try:
            auc = roc_auc_score(
                y, modelo.predict_proba(X), multi_class="ovr", average="weighted"
            )
        except Exception:
            auc = 0.0

        return MetricasDesempenho(
            acuracia=acuracia,
            precisao=precisao,
            recall=recall,
            f1_score=f1,
            auc_roc=auc,
        )
