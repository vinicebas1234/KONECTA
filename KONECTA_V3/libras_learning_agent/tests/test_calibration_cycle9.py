"""Testes reais do Ciclo 9 (calibração cross-signer) do Libras Learning Agent.

Não reprocessa o vocabulário completo de 25 sinais usado no experimento
principal (`ml/experiments/calibration_cycle9.py::run_all`) — isso é feito uma
vez, manualmente, e reportado à parte (rodar de novo aqui só para testar
tornaria a suíte lenta sem ganhar cobertura nova). Este arquivo testa as
funções novas e reaproveitáveis do experimento (`normalize_center_of_mass`,
`resample_sequence`, `dtw_distance_banded`, `evaluate_single_split`,
`split_train_test`) sobre um vocabulário pequeno e real (2 sinais x 3
sinalizantes = 6 vídeos) — mesmo padrão sem mocks do resto do LLA.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from libras_learning_agent.ml.dataset import DEFAULT_VLIBRASIL_ROOT
from libras_learning_agent.ml.experiments.calibration_cycle9 import (
    RESAMPLE_LENGTH,
    dtw_distance_banded,
    evaluate_single_split,
    load_raw_dataset,
    normalize_center_of_mass,
    resample_sequence,
    split_train_test,
)
from libras_learning_agent.ml.dataset import Sample
from libras_learning_agent.ml.features import VECTOR_SIZE, normalize_hand_landmarks
from libras_learning_agent.vision.hand_landmarks import ensure_hand_landmarker_model, extract_hand_landmarks

TINY_VOCAB_SIZE = 2  # 2 sinais x 3 sinalizantes = 6 vídeos, orçamento mínimo pro teste


@pytest.fixture(scope="module")
def model_path() -> Path:
    return ensure_hand_landmarker_model()


@pytest.fixture(scope="module")
def tiny_raw(model_path):
    """6 amostras cruas reais (2 sinais x 3 sinalizantes), extraídas uma única vez."""
    raw = load_raw_dataset(vocab_size=TINY_VOCAB_SIZE, model_path=model_path)
    assert len(raw) == TINY_VOCAB_SIZE * 3
    return raw


# --------------------------------------------------------------------- 1 ---


def test_normalize_center_of_mass_deterministic_and_shape(model_path: Path) -> None:
    """Determinismo (2 extrações reais independentes do mesmo vídeo) + shape (T, 128).

    Mesmo padrão de determinismo do Ciclo 1/7: um pipeline real e
    determinístico dá o mesmo resultado nas duas rodadas.
    """
    video = DEFAULT_VLIBRASIL_ROOT / "data" / "Abacaxi" / "Abacaxi_Articulador1.mp4"
    assert video.is_file(), f"vídeo real ausente: {video}"

    seq1 = normalize_center_of_mass(extract_hand_landmarks(video, model_path=model_path))
    seq2 = normalize_center_of_mass(extract_hand_landmarks(video, model_path=model_path))

    assert seq1.shape == seq2.shape
    assert seq1.ndim == 2
    assert seq1.shape[1] == VECTOR_SIZE
    assert seq1.shape[0] > 0
    assert np.array_equal(seq1, seq2), "normalização center-of-mass não é determinística entre rodadas"

    # É uma normalização DIFERENTE da de produção de propósito -- não deveriam
    # coincidir byte a byte (senão a variante V2 não estaria testando nada).
    seq_producao = normalize_hand_landmarks(extract_hand_landmarks(video, model_path=model_path))
    assert seq1.shape == seq_producao.shape
    assert not np.array_equal(seq1, seq_producao), (
        "center-of-mass produziu exatamente o mesmo vetor da normalização por-mão de produção"
    )


# --------------------------------------------------------------------- 2 ---


def test_resample_and_banded_dtw_sanity(tiny_raw) -> None:
    """Reamostragem preserva shape (RESAMPLE_LENGTH, D); DTW com banda tem auto-distância ~0."""
    sequence = normalize_center_of_mass(tiny_raw[0].extraction)
    resampled = resample_sequence(sequence)

    assert resampled.shape == (RESAMPLE_LENGTH, VECTOR_SIZE)

    self_distance = dtw_distance_banded(resampled, resampled)
    assert self_distance < 1e-5, f"auto-distância com banda deveria ser ~0, veio {self_distance}"

    # sequência vazia -> inf, mesmo contrato de `ml/dtw.py::dtw_distance` de produção
    empty = np.zeros((0, VECTOR_SIZE), dtype=np.float32)
    assert dtw_distance_banded(empty, resampled) == float("inf")


# --------------------------------------------------------------------- 3 ---


def test_evaluate_single_split_structure(tiny_raw) -> None:
    """`split_train_test` + `evaluate_single_split`: sinalizantes corretos, estrutura, faixa [0,1].

    Vocabulário mínimo (2 sinais) -- não há acurácia "esperada" aqui, só a
    estrutura é verificada (mesmo espírito de
    `test_evaluate_leave_one_signer_out_metrics_shape` do Ciclo 7).
    """
    samples = [
        Sample(sign=r.sign, signer=r.signer, sequence=normalize_center_of_mass(r.extraction), video_path=r.video_path)
        for r in tiny_raw
    ]
    train, test = split_train_test(samples)

    assert {s.signer for s in train} == {"1", "3"}
    assert {s.signer for s in test} == {"2"}
    assert len(train) + len(test) == len(samples)

    metrics = evaluate_single_split(train, test)
    assert metrics["n_evaluated"] == len(test)
    assert metrics["n_references"] == len(train)
    assert 0.0 <= metrics["top1_accuracy"] <= 1.0
    assert 0.0 <= metrics["top5_accuracy"] <= 1.0
    assert metrics["top5_accuracy"] >= metrics["top1_accuracy"], "top-5 nunca pode ser pior que top-1"
