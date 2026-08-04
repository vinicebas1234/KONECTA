"""Treinamento de classificadores temporais (LSTM/BiLSTM) sobre sequências.

Recebe X (N, T, F) e y (ids de classe), devolve modelo Keras treinado,
ordem de labels do softmax e métricas no conjunto de teste — mesma
estrutura de métricas do classificador de imagem, para a UI reutilizar.
"""
import time

import numpy as np
from sklearn.metrics import (accuracy_score, confusion_matrix,
                             precision_recall_fscore_support)
from sklearn.model_selection import train_test_split

MODEL_TYPES = ("bilstm", "lstm")

# vídeos são mais caros de gravar que fotos; o mínimo aqui é menor,
# mas a análise do dataset recomenda bem mais
MIN_VALID_PER_CLASS = 3


def build_model(model_type: str, seq_len: int, n_features: int, n_classes: int):
    import keras
    from keras import layers

    inputs = keras.Input(shape=(seq_len, n_features))
    if model_type == "bilstm":
        x = layers.Bidirectional(layers.LSTM(64))(inputs)
    elif model_type == "lstm":
        x = layers.LSTM(64)(inputs)
    else:
        raise ValueError(f"Modelo desconhecido: {model_type}")
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(32, activation="relu")(x)
    outputs = layers.Dense(n_classes, activation="softmax")(x)

    model = keras.Model(inputs, outputs)
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy",
                  metrics=["accuracy"])
    return model


def train(X: np.ndarray, y: np.ndarray, class_names: dict[int, str],
          model_type: str = "bilstm") -> tuple[object, list[int], dict]:
    """Treina e avalia. Retorna (modelo, labels na ordem do softmax, métricas)."""
    import keras

    labels = sorted(class_names)
    if len(labels) < 2:
        raise ValueError("São necessárias pelo menos 2 classes com vídeos válidos.")

    counts = {label: int(np.sum(y == label)) for label in labels}
    weak = [class_names[l] for l, n in counts.items() if n < MIN_VALID_PER_CLASS]
    if weak:
        raise ValueError(
            f"Classes com menos de {MIN_VALID_PER_CLASS} vídeos válidos "
            "(com mãos detectadas): " + ", ".join(weak))

    label_to_idx = {label: i for i, label in enumerate(labels)}
    y_idx = np.array([label_to_idx[c] for c in y])

    test_size = max(0.25, (len(labels) + 0.5) / len(y))
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_idx, test_size=test_size, random_state=42, stratify=y_idx)

    started = time.time()
    keras.utils.set_random_seed(42)
    model = build_model(model_type, X.shape[1], X.shape[2], len(labels))
    stop = keras.callbacks.EarlyStopping(monitor="loss", patience=15,
                                         restore_best_weights=True)
    model.fit(X_train, y_train, epochs=150, batch_size=8,
              verbose=0, callbacks=[stop])
    train_seconds = time.time() - started

    y_pred = model.predict(X_test, verbose=0).argmax(axis=1)
    idx_all = list(range(len(labels)))
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, y_pred, labels=idx_all, zero_division=0)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_test, y_pred, labels=idx_all, average="macro", zero_division=0)

    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(macro_p), 4),
        "recall": round(float(macro_r), 4),
        "f1": round(float(macro_f1), 4),
        "per_class": [
            {
                "name": class_names[labels[i]],
                "precision": round(float(precision[i]), 4),
                "recall": round(float(recall[i]), 4),
                "f1": round(float(f1[i]), 4),
                "support": int(support[i]),
            }
            for i in idx_all
        ],
        "confusion": {
            "labels": [class_names[label] for label in labels],
            "matrix": confusion_matrix(y_test, y_pred, labels=idx_all).tolist(),
        },
        "train_size": int(len(y_train)),
        "test_size": int(len(y_test)),
        "train_seconds": round(train_seconds, 2),
    }
    return model, labels, metrics
