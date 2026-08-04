"""Treinamento de classificadores de imagem sobre features de landmarks.

Independente de interface e de banco: recebe X, y e nomes de classes,
devolve modelo treinado + métricas completas. Split estratificado;
métricas sempre calculadas no conjunto de teste (nunca no de treino).
"""
import time

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, confusion_matrix,
                             precision_recall_fscore_support)
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

MODEL_TYPES = ("rf", "mlp")

MIN_VALID_PER_CLASS = 4


def build_model(model_type: str):
    if model_type == "rf":
        return RandomForestClassifier(
            n_estimators=300, random_state=42, n_jobs=-1)
    if model_type == "mlp":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("mlp", MLPClassifier(hidden_layer_sizes=(128, 64),
                                  max_iter=600, random_state=42)),
        ])
    raise ValueError(f"Modelo desconhecido: {model_type}")


def train(X: np.ndarray, y: np.ndarray, class_names: dict[int, str],
          model_type: str = "rf", lsae_config=None) -> tuple[object, dict]:
    """Treina e avalia. y contém ids de classe; class_names mapeia id -> nome.

    Retorna (modelo, métricas). Lança ValueError com mensagem amigável
    quando o dataset é insuficiente. O LSAE (se habilitado) é aplicado
    SOMENTE ao conjunto de treino, depois do split — teste permanece
    original (regra anti data-leakage).
    """
    labels = sorted(class_names)
    if len(labels) < 2:
        raise ValueError("São necessárias pelo menos 2 classes com exemplos válidos.")

    counts = {label: int(np.sum(y == label)) for label in labels}
    weak = [class_names[l] for l, n in counts.items() if n < MIN_VALID_PER_CLASS]
    if weak:
        raise ValueError(
            "Classes com menos de "
            f"{MIN_VALID_PER_CLASS} exemplos válidos (com mão detectada): "
            + ", ".join(weak))

    # garante pelo menos 1 exemplo de teste por classe
    test_size = max(0.2, (len(labels) + 0.5) / len(y))
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y)

    train_size_original = int(len(y_train))
    lsae_applied = None
    if lsae_config is not None and lsae_config.enabled:
        from lsae.pipeline import augment_train_set
        X_train, y_train, lsae_applied = augment_train_set(
            X_train, y_train, lsae_config)

    started = time.time()
    model = build_model(model_type)
    model.fit(X_train, y_train)
    train_seconds = time.time() - started

    y_pred = model.predict(X_test)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, y_pred, labels=labels, zero_division=0)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_test, y_pred, labels=labels, average="macro", zero_division=0)

    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(macro_p), 4),
        "recall": round(float(macro_r), 4),
        "f1": round(float(macro_f1), 4),
        "per_class": [
            {
                "name": class_names[label],
                "precision": round(float(precision[i]), 4),
                "recall": round(float(recall[i]), 4),
                "f1": round(float(f1[i]), 4),
                "support": int(support[i]),
            }
            for i, label in enumerate(labels)
        ],
        "confusion": {
            "labels": [class_names[label] for label in labels],
            "matrix": confusion_matrix(y_test, y_pred, labels=labels).tolist(),
        },
        "train_size": int(len(y_train)),
        "train_size_original": train_size_original,
        "test_size": int(len(y_test)),
        "train_seconds": round(train_seconds, 2),
        "lsae": lsae_applied.to_dict() if lsae_applied else {"enabled": False},
    }
    return model, metrics
