"""Testes do Motor KONECTA V3 (reconhecimento primário)."""

# pylint: disable=missing-function-docstring,protected-access,unused-argument,C1803,too-few-public-methods,import-outside-toplevel,no-member,no-name-in-module

import asyncio

import numpy as np
import pytest

from app_central.motors.motor_konecta_v3 import (
    FEATURE_COUNT,
    PROFILE_STAGES,
    MotorBase,
    MotorKonectaV3,
    RecognitionResult,
)


# ── MotorBase / contrato ─────────────────────────────────────────

def test_motor_base_process_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        asyncio.run(MotorBase().process(np.zeros((1, 1, 3), dtype=np.uint8)))


def test_feature_count_contract():
    assert FEATURE_COUNT == 63


# ── Carregamento de modelos ─────────────────────────────────────

def test_load_models_missing_path(tmp_path, caplog):
    motor = MotorKonectaV3(model_path=str(tmp_path))
    motor._load_models()
    assert motor.classifier is None
    assert motor.metadata == {}
    assert motor._models_loaded is True
    assert motor._label_map == {}


def test_load_models_with_files(tmp_path):
    import json
    import joblib

    (tmp_path / "classifier.joblib").write_bytes(b"x")
    (tmp_path / "metadata.json").write_text(
        json.dumps({"labels": {"0": "OLA", "1": "NAO"}}), encoding="utf-8"
    )

    class _StubClassifier:
        pass

    motor = MotorKonectaV3(model_path=str(tmp_path))
    original_load = joblib.load
    import app_central.motors.motor_konecta_v3 as module

    try:
        module.joblib.load = lambda path: _StubClassifier()
        motor._load_models()
    finally:
        module.joblib.load = original_load

    assert isinstance(motor.classifier, _StubClassifier)
    assert motor.metadata["labels"] == {"0": "OLA", "1": "NAO"}
    assert motor._label_map == {"0": "OLA", "1": "NAO"}


def test_load_models_retries_after_failure(tmp_path, monkeypatch):
    # Arquivo presente, mas leitura falha -> joblib.load lança exceção
    (tmp_path / "classifier.joblib").write_bytes(b"corrupted")
    motor = MotorKonectaV3(model_path=str(tmp_path))
    import app_central.motors.motor_konecta_v3 as module

    def boom(path):
        raise OSError("disco falhou")

    monkeypatch.setattr(module.joblib, "load", boom)
    motor._load_models()
    assert motor._models_loaded is False
    assert motor.classifier is None


def test_load_sequence_model_missing_returns_none(tmp_path):
    motor = MotorKonectaV3(model_path=str(tmp_path))
    assert motor._load_sequence_model() is None
    assert motor.sequence_model is None


def test_load_sequence_model_already_loaded(tmp_path):
    motor = MotorKonectaV3(model_path=str(tmp_path))
    motor.sequence_model = "fake-model"
    assert motor._load_sequence_model() == "fake-model"


def test_load_sequence_model_import_error(tmp_path):
    (tmp_path / "sequence_model.keras").write_bytes(b"not-a-keras-model")
    motor = MotorKonectaV3(model_path=str(tmp_path))
    # tensorflow não instalado (ou arquivo inválido) -> falha tratada sem lançar
    assert motor._load_sequence_model() is None


# ── Cache de landmarks ──────────────────────────────────────────

def test_cache_key_contiguous(sample_frame):
    key = MotorKonectaV3._cache_key(sample_frame)
    assert key is not None
    shape, dtype, digest = key
    assert shape == (480, 640, 3)
    assert dtype == sample_frame.dtype.str
    assert len(digest) == 16


def test_cache_key_non_contiguous(sample_frame):
    non_contig = sample_frame[:, ::-1]
    assert not non_contig.flags.c_contiguous
    assert MotorKonectaV3._cache_key(non_contig) is None


def test_cache_put_get_roundtrip(sample_frame):
    motor = MotorKonectaV3(landmark_cache_size=8)
    key = MotorKonectaV3._cache_key(sample_frame)
    landmarks = np.zeros(FEATURE_COUNT, dtype=np.float32)
    motor._cache_put(key, landmarks)
    hit, cached = motor._cache_get(key)
    assert hit is True
    np.testing.assert_array_equal(cached, landmarks)


def test_cache_get_returns_copy(sample_frame):
    motor = MotorKonectaV3(landmark_cache_size=8)
    key = MotorKonectaV3._cache_key(sample_frame)
    motor._cache_put(key, np.arange(FEATURE_COUNT, dtype=np.float32))
    _, cached = motor._cache_get(key)
    cached[0] = 999.0
    _, cached2 = motor._cache_get(key)
    assert cached2[0] == 0.0


def test_cache_put_none_key_is_noop():
    motor = MotorKonectaV3(landmark_cache_size=8)
    motor._cache_put(None, np.zeros(1))
    assert len(motor._landmark_cache) == 0
    hit, cached = motor._cache_get(None)
    assert hit is False and cached is None


def test_cache_lru_eviction(sample_frame):
    motor = MotorKonectaV3(landmark_cache_size=2)
    frame_a = np.zeros((1, 1, 3), dtype=np.uint8)
    frame_b = np.ones((1, 1, 3), dtype=np.uint8)
    frame_c = np.full((1, 1, 3), 2, dtype=np.uint8)
    for frame in (frame_a, frame_b, frame_c):
        motor._cache_put(MotorKonectaV3._cache_key(frame), np.zeros(1, dtype=np.float32))
    assert len(motor._landmark_cache) == 2
    hit, _ = motor._cache_get(MotorKonectaV3._cache_key(frame_a))
    assert hit is False  # frame_a foi expulso


def test_cache_disabled():
    motor = MotorKonectaV3(landmark_cache_size=0)
    assert motor._landmark_cache_size == 0
    motor._cache_put(("k",), np.zeros(1, dtype=np.float32))
    assert len(motor._landmark_cache) == 0


# ── Extração de landmarks ───────────────────────────────────────

def test_extract_landmarks_invalid_frame(sample_frame):
    motor = MotorKonectaV3()
    with pytest.raises(ValueError):
        motor._extract_landmarks(sample_frame[:, :, :2])  # 2 canais
    with pytest.raises(ValueError):
        motor._extract_landmarks(np.zeros((2, 2), dtype=np.uint8))  # 2D


def test_extract_landmarks_shape_and_value(fake_hands):
    motor = MotorKonectaV3()
    motor._hands = fake_hands
    landmarks = motor._extract_landmarks(np.zeros((1, 1, 3), dtype=np.uint8))
    assert landmarks is not None
    assert landmarks.dtype == np.float32
    assert landmarks.shape == (FEATURE_COUNT,)


def test_extract_landmarks_no_hands(fake_hands):
    motor = MotorKonectaV3()
    fake_hands._present = False
    motor._hands = fake_hands
    assert motor._extract_landmarks(np.zeros((1, 1, 3), dtype=np.uint8)) is None


def test_extract_landmarks_mediapipe_unavailable(monkeypatch):
    motor = MotorKonectaV3()
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "mediapipe":
            raise ImportError("sem mediapipe")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    hands = motor._get_hands()
    assert hands is None
    assert motor._mediapipe_unavailable is True


# ── Processamento de frames ─────────────────────────────────────

def test_process_without_model_returns_error(sample_frame):
    motor = MotorKonectaV3()
    result = asyncio.run(motor.process(sample_frame))
    assert result.status == "error"
    assert result.error == "Modelo não carregado"
    assert result.signal == "ERROR"
    assert result.confidence == 0.0


def test_process_success_with_proba(fake_classifier_proba, fake_hands, tmp_path):
    import json

    # _load_models sobrescreve _label_map a partir de metadata.json
    # (mapeia o nome da classe para o nome de exibição)
    (tmp_path / "metadata.json").write_text(
        json.dumps({"labels": {"OLA": "OLA"}}), encoding="utf-8"
    )
    motor = MotorKonectaV3(model_path=str(tmp_path))
    motor.classifier = fake_classifier_proba
    motor._hands = fake_hands

    result = asyncio.run(motor.process(np.zeros((1, 1, 3), dtype=np.uint8)))

    assert result.status == "success"
    assert result.signal == "OLA"
    assert result.confidence == pytest.approx(0.8)
    assert len(result.landmarks) == FEATURE_COUNT


def test_process_success_with_plain_predict(fake_classifier_predict, fake_hands):
    motor = MotorKonectaV3()
    motor.classifier = fake_classifier_predict
    motor._hands = fake_hands

    result = asyncio.run(motor.process(np.zeros((1, 1, 3), dtype=np.uint8)))

    assert result.status == "success"
    assert result.signal == "UNKNOWN_OLA"  # sem label_map → prefixo UNKNOWN_
    assert result.confidence == 1.0


def test_process_no_hands(fake_classifier_proba):
    motor = MotorKonectaV3()
    motor.classifier = fake_classifier_proba
    motor._mediapipe_unavailable = True  # evita instanciar MediaPipe real
    result = asyncio.run(motor.process(np.zeros((1, 1, 3), dtype=np.uint8)))
    assert result.status == "no_input"
    assert result.signal == "NO_HANDS"
    assert result.error == "Mãos não detectadas"


def test_process_exception_is_caught(fake_classifier_proba, sample_frame):
    motor = MotorKonectaV3()
    motor.classifier = fake_classifier_proba

    class _BrokenHands:
        def process(self, frame):
            raise RuntimeError("mediapipe crash")

    motor._hands = _BrokenHands()
    result = asyncio.run(motor.process(sample_frame))
    assert result.status == "error"
    assert motor.performance_stats["errors"] == 1


def test_process_cache_hit(fake_classifier_proba, fake_hands):
    motor = MotorKonectaV3(landmark_cache_size=8)
    motor.classifier = fake_classifier_proba
    motor._hands = fake_hands
    frame = np.zeros((1, 1, 3), dtype=np.uint8)

    asyncio.run(motor.process(frame))
    assert motor.performance_stats["cache_misses"] == 1

    asyncio.run(motor.process(frame))
    assert motor.performance_stats["cache_hits"] == 1
    assert motor.performance_stats["total_processed"] == 2


def test_process_batch_order(fake_classifier_proba, fake_hands):
    motor = MotorKonectaV3()
    motor.classifier = fake_classifier_proba
    motor._hands = fake_hands
    frames = [np.full((1, 1, 3), i, dtype=np.uint8) for i in range(3)]
    results = asyncio.run(motor.process_batch(frames))
    assert len(results) == 3
    assert all(r.status == "success" for r in results)


# ── Benchmark ───────────────────────────────────────────────────

def test_benchmark_empty_raises():
    motor = MotorKonectaV3()
    with pytest.raises(ValueError):
        asyncio.run(motor.benchmark_performance([]))


def test_benchmark_report_structure(fake_classifier_proba, fake_hands):
    motor = MotorKonectaV3()
    motor.classifier = fake_classifier_proba
    motor._hands = fake_hands
    frames = [np.zeros((1, 1, 3), dtype=np.uint8) for _ in range(10)]
    report = asyncio.run(motor.benchmark_performance(frames, warmup_frames=2))
    assert report["frames"] == 10
    assert report["avg_latency_ms"] >= 0
    assert "p50_latency_ms" in report
    assert "p95_latency_ms" in report
    assert "p99_latency_ms" in report
    assert "fps" in report
    assert "status_counts" in report
    assert set(report["avg_stage_ms"].keys()) == set(PROFILE_STAGES)
    assert "cache" in report


def test_benchmark_report_empty_profile_edge(fake_classifier_proba, fake_hands):
    motor = MotorKonectaV3()
    motor.classifier = fake_classifier_proba
    motor._hands = fake_hands
    frames = [np.zeros((1, 1, 3), dtype=np.uint8)]
    report = asyncio.run(motor.benchmark_performance(frames, warmup_frames=0))
    assert report["frames"] == 1
    assert report["status_counts"]["success"] == 1


# ── Estatísticas ────────────────────────────────────────────────

def test_stats_avg_and_error_rate(sample_frame):
    motor = MotorKonectaV3()
    asyncio.run(motor.process(sample_frame))  # erro: sem modelo
    stats = motor.get_stats()
    assert stats["total_processed"] == 1
    assert stats["errors"] == 1
    assert stats["error_rate"] == 1.0
    assert stats["avg_latency_ms"] >= 0
    assert set(stats["avg_stage_ms"].keys()) == set(PROFILE_STAGES)


def test_clear_stats_resets():
    motor = MotorKonectaV3()
    motor.performance_stats["total_processed"] = 50
    motor.performance_stats["stage_time_ms"]["inference"] = 12.5
    motor.clear_stats()
    stats = motor.get_stats()
    assert stats["total_processed"] == 0
    assert all(v == 0.0 for v in stats["stage_time_ms"].values())


def test_close_releases_hands_and_cache(fake_hands):
    motor = MotorKonectaV3()
    motor._hands = fake_hands
    motor._cache_put(("k",), np.zeros(1, dtype=np.float32))
    motor.close()
    assert fake_hands.closed is True
    assert motor._hands is None
    assert len(motor._landmark_cache) == 0


def test_recognition_result_defaults():
    result = RecognitionResult("OLA", 0.9, 10.0)
    assert result.landmarks is None
    assert result.model_version == "v1"
    assert result.status == "success"
    assert result.error is None
