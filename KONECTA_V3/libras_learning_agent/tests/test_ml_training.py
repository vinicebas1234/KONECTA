"""Testes reais do Ciclo 7 (dataset + "treino" DTW/protótipos) do Libras Learning Agent.

Nada aqui é simulado: landmarks reais de vídeos reais do V-LIBRASIL (UFPE),
DTW real, SQLite temporário real. Mesmo padrão do Ciclo 1
(`test_vision_hand_landmarks.py`) — sem mocks.

Dataset lido de `ml.dataset.DEFAULT_VLIBRASIL_ROOT`
(`C:\\KONECTA\\Datasets\\videos UFPE (V-LIBRASIL)\\`), fora de `KONECTA_V3` —
só leitura, nunca escrita (ver `ml/dataset.py`).

Para manter o arquivo rápido, um único vocabulário pequeno (5 sinais × 3
sinalizantes = 15 vídeos, os 5 primeiros em ordem alfabética com os 3
articuladores presentes) é extraído uma vez (fixture `module`-scoped) e
reaproveitado pelos testes de DTW, vazamento de dado e pipeline completo. O
teste de determinismo (o mais importante do ciclo, mesmo padrão do Ciclo 1)
faz sua própria extração dupla, porque precisa de duas chamadas
independentes de verdade — reaproveitar uma amostra já carregada não provaria
nada.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from libras_learning_agent.core.config import Settings
from libras_learning_agent.database.db import Base
from libras_learning_agent.database.models import ModelVersion, TrainingRun
from libras_learning_agent.ml.dataset import (
    DEFAULT_VLIBRASIL_ROOT,
    discover_vocabulary,
    load_dataset,
    load_references,
)
from libras_learning_agent.ml.dtw import dtw_distance
from libras_learning_agent.ml.features import normalize_hand_landmarks
from libras_learning_agent.ml.predict import predict
from libras_learning_agent.ml.training import (
    build_model_version,
    evaluate_leave_one_signer_out,
    leave_one_signer_out_splits,
)
from libras_learning_agent.vision.hand_landmarks import ensure_hand_landmarker_model, extract_hand_landmarks

SMALL_VOCAB_SIZE = 5  # 5 sinais x 3 sinalizantes = 15 vídeos, cabe no orçamento do teste


def _sqlite_url(path: Path) -> str:
    return "sqlite:///" + str(path).replace("\\", "/")


@pytest.fixture(scope="module")
def model_path() -> Path:
    return ensure_hand_landmarker_model()


@pytest.fixture(scope="module")
def small_vocabulary():
    return discover_vocabulary(DEFAULT_VLIBRASIL_ROOT, min_signs=SMALL_VOCAB_SIZE, max_signs=SMALL_VOCAB_SIZE)


@pytest.fixture(scope="module")
def small_samples(small_vocabulary, model_path):
    """15 amostras reais (5 sinais x 3 sinalizantes), extraídas uma única vez."""
    samples = load_dataset(small_vocabulary, model_path=model_path)
    assert len(samples) == SMALL_VOCAB_SIZE * 3
    return samples


def _find(samples, sign: str, signer: str):
    for s in samples:
        if s.sign == sign and s.signer == signer:
            return s
    raise AssertionError(f"amostra não encontrada: sign={sign} signer={signer}")


def _pairs(sign, samples):
    """Todos os pares (sinalizantes diferentes) de amostras do mesmo `sign`."""
    same_sign = [s for s in samples if s.sign == sign]
    return combinations(same_sign, 2)


def _diff_sign_pairs(samples):
    """Pares de amostras de sinais diferentes, mesmo sinalizante (controla o efeito do sinalizante)."""
    for signer in {s.signer for s in samples}:
        same_signer = [s for s in samples if s.signer == signer]
        yield from combinations(same_signer, 2)


# --------------------------------------------------------------------- 1 ---


def test_normalize_hand_landmarks_deterministic_real_video(model_path: Path) -> None:
    """Duas extrações+normalizações independentes do mesmo vídeo real batem.

    Mesmo padrão de determinismo do Ciclo 1: um pipeline real e determinístico
    dá o mesmo resultado nas duas rodadas. Também prova o shape (T, 128).
    """
    video = DEFAULT_VLIBRASIL_ROOT / "data" / "Abacaxi" / "Abacaxi_Articulador1.mp4"
    assert video.is_file(), f"vídeo real ausente: {video}"

    seq1 = normalize_hand_landmarks(extract_hand_landmarks(video, model_path=model_path))
    seq2 = normalize_hand_landmarks(extract_hand_landmarks(video, model_path=model_path))

    assert seq1.shape == seq2.shape
    assert seq1.ndim == 2
    assert seq1.shape[1] == 128
    assert seq1.shape[0] > 0
    assert np.array_equal(seq1, seq2), "normalização não é determinística entre rodadas"


# --------------------------------------------------------------------- 2 ---


def test_dtw_distance_sanity(small_samples) -> None:
    """Auto-distância ~0; sinal diferente > mesmo sinal com sinalizante diferente.

    Prova que a métrica captura o gesto, não é ruído: se a distância DTW não
    fosse, em média, menor para o mesmo sinal (sinalizantes diferentes) do que
    para sinais diferentes, ela não estaria medindo o gesto de verdade.

    Comparação por UM par só (ex. só "Abacaxi" vs "Abanar") é frágil demais
    para julgar isso: o próprio `RECONHECIMENTO_RECOMENDACAO.md` (seção 5.1)
    mede só 47,4% de acurácia top-1 mesmo no melhor caso medido (kNN, 20
    sinais) — ou seja, o vizinho mais próximo erra a maioria das vezes mesmo
    lá. Um par isolado falhar não prova que a métrica é ruído; a média sobre
    vários pares é o teste honesto. Reaproveita as 15 amostras já extraídas
    (nenhum vídeo novo processado aqui).
    """
    self_distance = dtw_distance(small_samples[0].sequence, small_samples[0].sequence)
    assert self_distance < 1e-5, f"auto-distância deveria ser ~0, veio {self_distance}"

    same_sign_distances = [
        dtw_distance(a.sequence, b.sequence)
        for sign in {s.sign for s in small_samples}
        for a, b in _pairs(sign, small_samples)
    ]
    diff_sign_distances = [
        dtw_distance(a.sequence, b.sequence)
        for a, b in _diff_sign_pairs(small_samples)
    ]

    mean_same = sum(same_sign_distances) / len(same_sign_distances)
    mean_diff = sum(diff_sign_distances) / len(diff_sign_distances)

    assert mean_same < mean_diff, (
        f"DTW não separou sinais em média: mesmo sinal (sinalizantes diferentes) = "
        f"{mean_same:.4f} (n={len(same_sign_distances)}), sinal diferente (mesmo "
        f"sinalizante) = {mean_diff:.4f} (n={len(diff_sign_distances)}) — esperado o "
        f"primeiro menor. Se isto falhar de verdade, é para documentar no relatório "
        f"com os números reais, não forçar."
    )


# --------------------------------------------------------------------- 3 ---


def test_leave_one_signer_out_no_leakage(small_samples) -> None:
    """O teste de vazamento de dado mais importante do ciclo.

    Para cada fold (um por sinalizante), nenhuma amostra de referência pode
    pertencer ao sinalizante sendo avaliado — senão a acurácia cross-signer
    sai artificialmente inflada. Verificação na estrutura intermediária
    (`leave_one_signer_out_splits`), amostra a amostra, não só no agregado.
    """
    splits = leave_one_signer_out_splits(small_samples)
    assert len(splits) == 3  # 3 sinalizantes no V-LIBRASIL

    signers_seen = set()
    for tested_signer, test_samples, reference_samples in splits:
        signers_seen.add(tested_signer)
        assert test_samples, f"fold do sinalizante {tested_signer} sem amostras de teste"
        assert reference_samples, f"fold do sinalizante {tested_signer} sem referências"

        assert all(s.signer == tested_signer for s in test_samples)
        leaked = [s for s in reference_samples if s.signer == tested_signer]
        assert not leaked, (
            f"VAZAMENTO: {len(leaked)} amostra(s) do sinalizante {tested_signer} "
            f"apareceram nas referências do próprio fold"
        )
        # tamanho: teste = 1/3 do total, referência = 2/3
        assert len(test_samples) + len(reference_samples) == len(small_samples)

    assert signers_seen == {"1", "2", "3"}


def test_evaluate_leave_one_signer_out_metrics_shape(small_samples) -> None:
    """`evaluate_leave_one_signer_out` agrega por sinalizante e no geral, sem vazamento.

    Acurácia real, seja qual for — não há verdade "esperada" aqui (vocabulário
    pequeno, sem garantia de bater o 47% do documento com 20 sinais); só a
    estrutura e a faixa [0, 1] são verificadas. O número real vai no relatório.
    """
    metrics = evaluate_leave_one_signer_out(small_samples)

    assert metrics["n_signs"] == SMALL_VOCAB_SIZE
    assert metrics["n_evaluated"] == len(small_samples)
    assert 0.0 <= metrics["top1_accuracy"] <= 1.0
    assert 0.0 <= metrics["top5_accuracy"] <= 1.0
    assert metrics["top5_accuracy"] >= metrics["top1_accuracy"], "top-5 nunca pode ser pior que top-1"
    assert set(metrics["per_signer"].keys()) == {"1", "2", "3"}
    for signer_metrics in metrics["per_signer"].values():
        assert signer_metrics["n_samples"] == SMALL_VOCAB_SIZE
        assert signer_metrics["n_references"] == SMALL_VOCAB_SIZE * 2


# --------------------------------------------------------------------- 4 ---


def test_full_pipeline_small_vocabulary_real(tmp_path: Path, small_vocabulary, small_samples) -> None:
    """Ponta a ponta: avalia, constrói `ModelVersion`, e `predict()` numa amostra de fora do treino.

    Uma amostra é retirada de `small_samples` ANTES de treinar/avaliar — vira
    a consulta "de fora do treino" para `predict()` no fim.
    """
    held_out = small_samples[-1]
    training_samples = small_samples[:-1]
    # (sign, signer) em vez de `held_out not in training_samples`: `Sample` é um
    # dataclass congelado com um campo `np.ndarray` — comparar o objeto inteiro
    # arriscaria `ValueError` de array ambíguo se algum dia os campos anteriores
    # (sign, signer) empatassem antes da comparação de array.
    assert (held_out.sign, held_out.signer) not in {(s.sign, s.signer) for s in training_samples}

    eval_metrics = evaluate_leave_one_signer_out(training_samples)
    assert eval_metrics["n_evaluated"] == len(training_samples)

    settings = Settings(
        _env_file=None,
        data_dir=str(tmp_path / "data"),
        models_dir=str(tmp_path / "models"),
        database_url=_sqlite_url(tmp_path / "ciclo7_test.db"),
    )
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    try:
        with Session(engine) as session:
            model_version = build_model_version(
                session, training_samples, eval_metrics, version="ciclo7_test_v001", settings=settings
            )
            model_version_id = model_version.id
            file_path = Path(model_version.file_path)

            assert model_version.status == "evaluated", 'nunca "production" — promoção é decisão humana futura'
            assert model_version.dataset_version == "vlibrasil_subset_v1"
            assert model_version.signals_count == SMALL_VOCAB_SIZE
            assert model_version.metrics["n_evaluated"] == eval_metrics["n_evaluated"]
            assert file_path.is_file(), f"artefato de referências não foi criado: {file_path}"
            assert (tmp_path / "models") in file_path.parents, "artefato fora de settings.models_dir (tmp isolado)"
            assert "KONECTA_V3" not in str(file_path.parents), "nunca deve cair sob KONECTA_V3/models/"

        # sessão nova: TrainingRun e ModelVersion sobrevivem fora da sessão que criou
        with Session(engine) as session2:
            runs = session2.query(TrainingRun).all()
            assert len(runs) == 1
            assert runs[0].status == "completed"
            assert runs[0].dataset_version == "vlibrasil_subset_v1"
            assert runs[0].metrics["n_evaluated"] == eval_metrics["n_evaluated"]

            row = session2.get(ModelVersion, model_version_id)
            assert row is not None
            assert row.file_path == str(file_path)

        references = load_references(file_path)
        assert len(references) == len(training_samples)

        ranking = predict(references, held_out.sequence, k=5)
        assert 1 <= len(ranking) <= 5
        vocabulary_signs = set(small_vocabulary.keys())
        for sign, distance in ranking:
            assert sign in vocabulary_signs
            assert distance >= 0.0
        distances = [d for _, d in ranking]
        assert distances == sorted(distances), "ranking deveria vir ordenado por distância"
    finally:
        engine.dispose()
