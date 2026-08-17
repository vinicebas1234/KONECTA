"""Testes do RecognizerPipeline (orquestração) e integração entre motores."""

# pylint: disable=missing-function-docstring,protected-access,unused-argument,C1803,too-few-public-methods,no-member,no-name-in-module

import asyncio
import base64
from unittest.mock import AsyncMock, Mock

import pytest

from app_central.motors.motor_claude_logic import ValidationResult
from app_central.motors.motor_konecta_v3 import RecognitionResult
from app_central.pipeline.recognizer_pipeline import (
    ConfidenceLevel,
    DEFAULT_IMAGE_QUALITY,
    HIGH_CONFIDENCE_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,
    PipelineResult,
    RecognizerPipeline,
)

anyio = pytest.mark.anyio


def _make_pipeline(config=None, **attachments) -> RecognizerPipeline:
    pipeline = RecognizerPipeline(config or {})
    for name, value in attachments.items():
        setattr(pipeline, name, value)
    return pipeline


def _konecta_result(signal="OLA", confidence=0.9, status="success"):
    return RecognitionResult(
        signal=signal,
        confidence=confidence,
        latency_ms=12.0,
        landmarks=[],
        status=status,
    )


async def _process_frame_no_side_effects(pipeline, frame, user_id="default"):
    """process_frame com side effects desligados (evita task pendente)."""
    pipeline._schedule_side_effects = lambda result, uid: None
    return await pipeline.process_frame(frame, user_id)


# ── classificação de confiança ─────────────────────────────────

@pytest.mark.parametrize(
    ("confidence", "expected"),
    [
        (0.86, ConfidenceLevel.HIGH),
        (0.85, ConfidenceLevel.MEDIUM),
        (0.7, ConfidenceLevel.MEDIUM),
        (0.69, ConfidenceLevel.LOW),
        (0.0, ConfidenceLevel.LOW),
    ],
)
def test_get_confidence_level(confidence, expected):
    pipeline = _make_pipeline()
    assert pipeline._get_confidence_level(confidence) is expected


def test_confidence_constants_sane():
    assert HIGH_CONFIDENCE_THRESHOLD > MEDIUM_CONFIDENCE_THRESHOLD
    assert HIGH_CONFIDENCE_THRESHOLD == 0.85
    assert MEDIUM_CONFIDENCE_THRESHOLD == 0.7


# ── helpers ─────────────────────────────────────────────────────

def test_extract_quality_from_gemini_none():
    assert (
        RecognizerPipeline._extract_quality_from_gemini(None)
        == DEFAULT_IMAGE_QUALITY
    )


def test_extract_quality_from_gemini_partial():
    quality = RecognizerPipeline._extract_quality_from_gemini(
        {"quality_score": 90}
    )
    assert quality["quality_score"] == 90
    assert quality["hands_visible"] == DEFAULT_IMAGE_QUALITY["hands_visible"]


def test_extract_quality_from_gemini_full():
    quality = RecognizerPipeline._extract_quality_from_gemini(
        {"quality_score": 77, "hands_visible": True, "lighting_ok": True}
    )
    assert quality == {"quality_score": 77, "hands_visible": True, "lighting_ok": True}


def test_frame_to_base64(small_frame):
    encoded = RecognizerPipeline._frame_to_base64(small_frame)
    raw = base64.b64decode(encoded)
    assert raw[:2] == b"\xff\xd8"


def test_get_user_history_no_cache_manager():
    pipeline = _make_pipeline()
    assert asyncio.run(pipeline._get_user_history("u1")) == []


def test_get_user_history_with_cache_manager():
    pipeline = _make_pipeline()
    pipeline.cache_manager = Mock()
    pipeline.cache_manager.get_history = AsyncMock(return_value=["A", "B"])
    assert asyncio.run(pipeline._get_user_history("u1")) == ["A", "B"]


def test_update_cache_and_notify_success(small_frame):
    pipeline = _make_pipeline()
    pipeline.cache_manager = Mock()
    pipeline.cache_manager.save_result = AsyncMock()
    pipeline.n8n_client = Mock()
    pipeline.n8n_client.notify_signal = AsyncMock()
    result = asyncio.run(_process_frame_no_side_effects(pipeline, small_frame))
    asyncio.run(pipeline._update_cache_and_notify(result, "u1"))
    pipeline.cache_manager.save_result.assert_awaited_once_with("u1", result)
    pipeline.n8n_client.notify_signal.assert_awaited_once_with(result, "u1")


def test_update_cache_and_notify_swallows_errors(small_frame):
    pipeline = _make_pipeline()
    pipeline.cache_manager = Mock()
    pipeline.cache_manager.save_result = AsyncMock(
        side_effect=RuntimeError("n8n offline")
    )
    result = asyncio.run(_process_frame_no_side_effects(pipeline, small_frame))
    asyncio.run(pipeline._update_cache_and_notify(result, "u1"))  # não deve lançar


# ── fluxos de processamento ─────────────────────────────────────

@anyio
async def test_process_high_confidence(small_frame):
    pipeline = _make_pipeline(
        konecta=Mock(process=AsyncMock(return_value=_konecta_result("OLA", 0.95)))
    )
    result = await _process_frame_no_side_effects(pipeline, small_frame)
    assert result.status == "success"
    assert result.signal == "OLA"
    assert result.confidence == pytest.approx(0.95)
    assert result.confidence_level == "high"
    assert result.validated_by == "ensemble"
    assert result.recommendation == "accept"
    assert result.detailed_results["konecta_v3"]["signal"] == "OLA"
    assert pipeline.performance_stats["high_confidence"] == 1


@anyio
async def test_process_medium_confidence_with_claude(small_frame):
    pipeline = _make_pipeline(
        konecta=Mock(process=AsyncMock(return_value=_konecta_result("OLA", 0.75))),
        claude=Mock(
            validate_with_context=AsyncMock(
                return_value=ValidationResult(
                    is_valid=True,
                    confidence_adjusted=0.81,
                    reasoning="faz sentido",
                    recommendation="accept",
                    latency_ms=50.0,
                )
            )
        ),
    )
    result = await _process_frame_no_side_effects(pipeline, small_frame, "user_x")
    assert result.confidence_level == "medium"
    assert result.validated_by == "claude_logic"
    assert result.confidence == pytest.approx(0.81)
    assert result.recommendation == "accept"
    assert result.user_history == []
    assert "claude_logic" in result.detailed_results
    pipeline.claude.validate_with_context.assert_awaited_once()


@anyio
async def test_process_low_confidence_without_grok(small_frame):
    pipeline = _make_pipeline(
        konecta=Mock(process=AsyncMock(return_value=_konecta_result("OLA", 0.5)))
    )
    result = await _process_frame_no_side_effects(pipeline, small_frame)
    assert result.confidence_level == "low"
    assert result.validated_by == "grok_context"
    assert result.signal == "OLA"
    assert result.recommendation == "accept"
    assert pipeline.performance_stats["low_confidence"] == 1


@anyio
async def test_process_low_confidence_with_grok(small_frame):
    pipeline = _make_pipeline(
        konecta=Mock(process=AsyncMock(return_value=_konecta_result("B", 0.5))),
        grok=Mock(
            enrich_with_context=AsyncMock(
                return_value={
                    "most_likely_signal": "A",
                    "top_candidates": [],
                    "confidence_adjusted": 0.62,
                    "fallback_used": False,
                }
            )
        ),
    )
    result = await _process_frame_no_side_effects(pipeline, small_frame)
    assert result.signal == "A"
    assert result.validated_by == "grok_context"
    assert "grok_context" in result.detailed_results
    pipeline.grok.enrich_with_context.assert_awaited_once()


@anyio
async def test_process_with_gemini_validation(small_frame):
    pipeline = _make_pipeline(
        konecta=Mock(process=AsyncMock(return_value=_konecta_result("OLA", 0.75))),
        gemini=Mock(
            validate=AsyncMock(
                return_value={
                    "quality_score": 88,
                    "hands_visible": True,
                    "lighting_ok": True,
                }
            )
        ),
        claude=Mock(
            validate_with_context=AsyncMock(
                return_value=ValidationResult(
                    True, 0.8, "ok", "accept", 10.0
                )
            )
        ),
    )
    result = await _process_frame_no_side_effects(pipeline, small_frame)
    assert "gemini_vision" in result.detailed_results
    assert result.confidence_level == "medium"
    # confirma que a qualidade do Gemini chegou ao prompt do Claude
    kwargs = pipeline.claude.validate_with_context.await_args.kwargs
    assert kwargs["image_quality"]["quality_score"] == 88


@anyio
async def test_process_timeout(small_frame):
    pipeline = _make_pipeline()

    async def _slow(frame):
        await asyncio.sleep(5.0)
        return _konecta_result()

    pipeline.konecta.process = _slow
    result = await _process_frame_no_side_effects(pipeline, small_frame)
    assert result.status == "error"
    assert result.error == "Pipeline timeout"
    assert pipeline.performance_stats["errors"] == 1


@anyio
async def test_process_exception_path(small_frame):
    pipeline = _make_pipeline(
        konecta=Mock(process=AsyncMock(side_effect=RuntimeError("modelo falhou")))
    )
    result = await _process_frame_no_side_effects(pipeline, small_frame)
    assert result.status == "error"
    assert result.signal == "ERROR"
    assert "modelo falhou" in result.error


def test_result_error_builds_and_tracks(small_frame):
    pipeline = _make_pipeline()
    result = pipeline._result_error(0.0, "x")
    assert result.status == "error"
    assert result.confidence_level == "low"
    assert result.recommendation == "retry"
    assert pipeline.performance_stats["errors"] == 1


# ── estatísticas ────────────────────────────────────────────────

@anyio
async def test_get_stats_after_processing(small_frame):
    pipeline = _make_pipeline(
        konecta=Mock(process=AsyncMock(return_value=_konecta_result("OLA", 0.95)))
    )
    await _process_frame_no_side_effects(pipeline, small_frame)
    await _process_frame_no_side_effects(pipeline, small_frame)
    stats = pipeline.get_stats()
    assert stats["total_processed"] == 2
    assert stats["success_rate"] == pytest.approx(1.0)
    assert stats["distribution"]["high_confidence"] == pytest.approx(1.0)
    assert stats["avg_latency_ms"] >= 0


def test_get_stats_empty():
    pipeline = _make_pipeline()
    stats = pipeline.get_stats()
    assert stats["total_processed"] == 0
    assert "success_rate" not in stats


def test_pipeline_result_defaults():
    result = PipelineResult("OLA", 0.9, 10.0, "high", "ensemble", "accept", [])
    assert result.status == "success"
    assert result.error is None
    assert result.detailed_results is None
