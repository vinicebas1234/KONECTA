"""Testes do Motor Gemini Vision (validação de qualidade de frame)."""

# pylint: disable=missing-function-docstring,protected-access,unused-argument,C1803,too-few-public-methods,no-member,no-name-in-module

import asyncio
import base64

import pytest

from app_central.motors.motor_gemini_vision import (
    FALLBACK_RESULT,
    GeminiValidationResult,
    MotorGeminiVision,
)


def _make_motor() -> MotorGeminiVision:
    return MotorGeminiVision(api_key="test-key")


# ── validate ────────────────────────────────────────────────────

def test_validate_success_fast_path():
    motor = _make_motor()
    result = asyncio.run(motor.validate("base64frame=="))
    assert result.status == "success"
    assert result.quality_score == 85
    assert result.hands_visible is True
    assert result.lighting_ok is True
    assert result.background_noise == "low"
    assert result.latency_ms >= 0


def test_validate_error_path(monkeypatch):
    motor = _make_motor()

    def _boom(*args, **kwargs):
        raise RuntimeError("api offline")

    monkeypatch.setattr("asyncio.sleep", _boom)
    result = asyncio.run(motor.validate("base64frame=="))
    assert result.status == "error"
    assert result.quality_score == FALLBACK_RESULT["quality_score"]
    assert result.hands_visible == FALLBACK_RESULT["hands_visible"]
    assert result.lighting_ok == FALLBACK_RESULT["lighting_ok"]
    assert result.background_noise == FALLBACK_RESULT["background_noise"]
    assert result.error == "api offline"


# ── helpers estáticos ───────────────────────────────────────────

def test_build_prompt_contains_json_contract():
    prompt = MotorGeminiVision._build_prompt()
    assert "quality_score" in prompt
    assert "hands_visible" in prompt
    assert "lighting_ok" in prompt
    assert "background_noise" in prompt


def test_encode_frame_returns_jpeg_base64(small_frame):
    encoded = MotorGeminiVision.encode_frame(small_frame)
    assert isinstance(encoded, str)
    raw = base64.b64decode(encoded)
    assert raw[:2] == b"\xff\xd8"  # magic JPEG
    assert raw.endswith(b"\xff\xd9")


def test_parse_quality_json_full():
    parsed = MotorGeminiVision.parse_quality_json(
        '{"quality_score": 72, "hands_visible": true, '
        '"lighting_ok": false, "background_noise": "medium"}'
    )
    assert parsed == {
        "quality_score": 72,
        "hands_visible": True,
        "lighting_ok": False,
        "background_noise": "medium",
    }


def test_parse_quality_json_defaults():
    parsed = MotorGeminiVision.parse_quality_json('{"quality_score": 10}')
    assert parsed["quality_score"] == 10
    assert parsed["hands_visible"] is False
    assert parsed["lighting_ok"] is False
    assert parsed["background_noise"] == "medium"


def test_parse_quality_json_with_surrounding_text():
    parsed = MotorGeminiVision.parse_quality_json(
        'texto {"quality_score": 90, "hands_visible": true} fim'
    )
    assert parsed["quality_score"] == 90


def test_parse_quality_json_missing_braces_raises():
    with pytest.raises(ValueError):
        MotorGeminiVision.parse_quality_json("sem json")


def test_parse_quality_json_type_coercion():
    parsed = MotorGeminiVision.parse_quality_json(
        '{"quality_score": "95", "hands_visible": 1}'
    )
    assert parsed["quality_score"] == 95
    assert parsed["hands_visible"] is True


def test_success_result_constructs_valid_dataclass():
    result = MotorGeminiVision._success_result(0.0)
    assert isinstance(result, GeminiValidationResult)
    assert result.status == "success"


def test_fallback_result_contract():
    assert FALLBACK_RESULT["quality_score"] == 50
    assert set(FALLBACK_RESULT.keys()) == {
        "quality_score",
        "hands_visible",
        "lighting_ok",
        "background_noise",
    }
