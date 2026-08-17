"""Testes end-to-end do app_central com mocks.

Exercita o fluxo completo: frame → pipeline → métricas, cobrindo os três níveis
de confiança sem chamadas externas reais.
"""

# pylint: disable=missing-function-docstring,protected-access,C1803,too-few-public-methods,no-member,no-name-in-module

from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from app_central.motors.motor_claude_logic import ValidationResult
from app_central.motors.motor_konecta_v3 import RecognitionResult
from app_central.pipeline.recognizer_pipeline import RecognizerPipeline
from app_central.utils.metrics import MetricsCollector

pytestmark = pytest.mark.anyio


def _frame():
    return np.zeros((240, 320, 3), dtype=np.uint8)


def _konecta(signal, confidence):
    return RecognitionResult(signal, confidence, 10.0, landmarks=[])


def _make_pipeline(**overrides):
    pipeline = RecognizerPipeline({})
    pipeline._schedule_side_effects = lambda result, uid: None
    for name, value in overrides.items():
        setattr(pipeline, name, value)
    return pipeline


async def test_e2e_high_confidence_flow():
    pipeline = _make_pipeline(
        konecta=Mock(process=AsyncMock(return_value=_konecta("OLA", 0.92)))
    )
    result = await pipeline.process_frame(_frame(), user_id="e2e_high")
    assert result.confidence_level == "high"
    assert result.recommendation == "accept"

    collector = MetricsCollector()
    collector.record_result(result)
    stats = collector.get_stats()
    assert stats["total_processed"] == 1
    assert stats["confidence_distribution"]["85-100%"] == 1
    assert stats["signal_frequency"]["OLA"] == 1
    assert stats["model_performance"]["ensemble"]["count"] == 1


async def test_e2e_medium_confidence_flow():
    claude = Mock(
        validate_with_context=AsyncMock(
            return_value=ValidationResult(True, 0.79, "ok", "accept", 30.0)
        )
    )
    pipeline = _make_pipeline(
        konecta=Mock(process=AsyncMock(return_value=_konecta("OLA", 0.74))),
        claude=claude,
    )
    result = await pipeline.process_frame(_frame(), user_id="e2e_med")
    assert result.confidence_level == "medium"
    assert result.validated_by == "claude_logic"
    assert result.confidence == pytest.approx(0.79)
    claude.validate_with_context.assert_awaited_once()


async def test_e2e_low_confidence_flow():
    grok = Mock(
        enrich_with_context=AsyncMock(
            return_value={
                "most_likely_signal": "SIM",
                "top_candidates": [],
                "confidence_adjusted": 0.6,
                "fallback_used": False,
            }
        )
    )
    pipeline = _make_pipeline(
        konecta=Mock(process=AsyncMock(return_value=_konecta("NAO", 0.55))),
        grok=grok,
    )
    result = await pipeline.process_frame(_frame(), user_id="e2e_low")
    assert result.confidence_level == "low"
    assert result.signal == "SIM"
    assert result.validated_by == "grok_context"
    grok.enrich_with_context.assert_awaited_once()


async def test_e2e_error_flow_surfaces_error_result():
    pipeline = _make_pipeline(
        konecta=Mock(process=AsyncMock(side_effect=RuntimeError("e2e falha")))
    )
    result = await pipeline.process_frame(_frame())
    assert result.status == "error"
    assert result.signal == "ERROR"


async def test_e2e_metrics_across_levels():
    pipeline = _make_pipeline(
        konecta=Mock(process=AsyncMock(return_value=_konecta("OLA", 0.95)))
    )
    collector = MetricsCollector(window_size=100)

    for _ in range(3):
        result = await pipeline.process_frame(_frame())
        collector.record_result(result)

    assert collector.get_stats()["total_processed"] == 3
    summary = collector.get_summary()
    assert "OLA" in summary


async def test_e2e_multiple_users_isolation():
    grok = Mock(
        enrich_with_context=AsyncMock(
            return_value={
                "most_likely_signal": "X",
                "top_candidates": [],
                "confidence_adjusted": 0.5,
                "fallback_used": False,
            }
        )
    )
    pipeline = _make_pipeline(
        konecta=Mock(process=AsyncMock(return_value=_konecta("X", 0.5))),
        grok=grok,
    )
    result = await pipeline.process_frame(_frame(), user_id="alice")
    assert result.status == "success"
    assert result.signal == "X"
