"""Testes de performance do app_central.

Metas (do projeto):
- latência média < 1s por processamento
- P95 < 1.5s

Nenhuma rede é usada: caminhos quentes são exercitados com mocks em memória.
"""

# pylint: disable=missing-function-docstring,protected-access,unused-argument,C1803,too-few-public-methods

import asyncio
import statistics
import time

import numpy as np

from app_central.motors.motor_konecta_v3 import FEATURE_COUNT, MotorKonectaV3

AVG_TARGET_MS = 1000.0
P95_TARGET_MS = 1500.0
RUNS = 30


def _fast_motor() -> MotorKonectaV3:
    """Motor com classifier e hands 100% em memória (sem MediaPipe/cv2 pesado)."""
    motor = MotorKonectaV3()

    class _Classifier:
        classes_ = np.array(["OLA", "NAO"])

        def predict_proba(self, features):
            return np.array([[0.95, 0.05]])

    class _Hands:
        def process(self, frame):
            class _Point:
                def __init__(self, i):
                    self.x = i / 21.0
                    self.y = 0.5
                    self.z = 0.0

            class _Hand:
                landmark = [_Point(i) for i in range(21)]

            class _Results:
                multi_hand_landmarks = [_Hand()]

            return _Results()

        def close(self):
            pass

    motor.classifier = _Classifier()
    motor._hands = _Hands()
    return motor


def test_konecta_process_latency_within_budget():
    motor = _fast_motor()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    async def _run():
        latencies = []
        for _ in range(RUNS):
            started = time.perf_counter()
            await motor.process(frame)
            latencies.append((time.perf_counter() - started) * 1000)
        return latencies

    latencies = asyncio.run(_run())
    avg = statistics.mean(latencies)
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    assert avg < AVG_TARGET_MS
    assert p95 < P95_TARGET_MS


def test_konecta_landmark_extraction_fast():
    motor = _fast_motor()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    latencies = []
    for _ in range(20):
        started = time.perf_counter()
        landmarks = motor._extract_landmarks(frame)
        latencies.append((time.perf_counter() - started) * 1000)

    assert landmarks.shape == (FEATURE_COUNT,)
    assert statistics.mean(latencies) < 10.0


def test_frame_to_base64_fast(small_frame):
    from app_central.pipeline.recognizer_pipeline import RecognizerPipeline

    latencies = []
    for _ in range(20):
        started = time.perf_counter()
        RecognizerPipeline._frame_to_base64(small_frame)
        latencies.append((time.perf_counter() - started) * 1000)
    assert statistics.mean(latencies) < 50.0


def test_grok_enrich_latency_within_budget():
    from app_central.motors.motor_grok_context import MotorGrokContext

    motor = MotorGrokContext()
    for sig in ("OLA", "BOM", "SIM", "NAO", "OLA"):
        motor.record_signal("perf_user", sig)

    async def _run():
        latencies = []
        for _ in range(RUNS):
            started = time.perf_counter()
            await motor.enrich_with_context("OLA", 0.5, "perf_user")
            latencies.append((time.perf_counter() - started) * 1000)
        return latencies

    latencies = asyncio.run(_run())
    assert statistics.mean(latencies) < AVG_TARGET_MS
