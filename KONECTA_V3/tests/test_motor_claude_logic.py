"""Testes do Motor Claude Logic (validação contextual)."""

# pylint: disable=missing-function-docstring,protected-access,unused-argument,C1803,too-few-public-methods,no-member,no-name-in-module,no-value-for-parameter,missing-kwoa

import asyncio
from types import SimpleNamespace

import anthropic
import pytest

from app_central.motors.motor_claude_logic import MotorClaudeLogic, ValidationResult


def _make_motor(client=None) -> MotorClaudeLogic:
    motor = MotorClaudeLogic(api_key="test-key")
    if client is not None:
        motor.client = client
    return motor


def _fake_response(text: str):
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


def _fake_client(text: str):
    """Cliente fake com latência mínima para medir timing."""
    import time

    class _Messages:
        def create(self, **kwargs):
            time.sleep(0.001)
            return _fake_response(text)

    class _Client:
        messages = _Messages()

    return _Client()


# ── Sucesso ─────────────────────────────────────────────────────

def test_validate_success_with_json_response():
    motor = _make_motor(_fake_client(
        '{"is_valid": true, "confidence_adjusted": 0.82, '
        '"reasoning": "ok", "recommendation": "accept"}'
    ))

    result = asyncio.run(
        motor.validate_with_context(
            signal="OLA", confidence=0.78,
            user_history=["BOCA", "OLA"], image_quality={"quality_score": 80},
        )
    )

    assert result.status == "success"
    assert result.is_valid is True
    assert result.confidence_adjusted == pytest.approx(0.82)
    assert result.recommendation == "accept"
    assert result.reasoning == "ok"
    assert motor.performance_stats["total_calls"] == 1
    assert motor.performance_stats["total_time_ms"] > 0


def test_validate_success_defaults_when_json_partial():
    motor = _make_motor(_fake_client('{"is_valid": true}'))
    result = asyncio.run(motor.validate_with_context("OLA", 0.7, [], {}))
    assert result.is_valid is True
    assert result.confidence_adjusted == pytest.approx(0.7)  # default = confiança
    assert result.recommendation == "accept"


# ── Erros ───────────────────────────────────────────────────────

def test_validate_api_error_path(monkeypatch):
    motor = _make_motor()
    monkeypatch.setattr(
        "app_central.motors.motor_claude_logic.anthropic.APIError",
        type("APIError", (Exception,), {}),
    )
    motor.client.messages.create = lambda **kwargs: (_ for _ in ()).throw(
        anthropic.APIError("timeout")
    )
    result = asyncio.run(motor.validate_with_context("OLA", 0.7, [], {}))
    assert result.status == "error"
    assert result.recommendation == "retry"
    assert motor.performance_stats["api_errors"] == 1


def test_validate_generic_exception_path():
    motor = _make_motor()
    motor.client.messages.create = lambda **kwargs: (_ for _ in ()).throw(
        ValueError("boom")
    )
    result = asyncio.run(motor.validate_with_context("OLA", 0.7, [], {}))
    assert result.status == "error"
    assert result.recommendation == "accept"  # fallback seguro
    assert result.error == "boom"


# ── Parse de resposta ───────────────────────────────────────────

def test_parse_response_direct_json():
    motor = _make_motor()
    parsed = motor._parse_response('{"is_valid": false, "recommendation": "retry"}')
    assert parsed["is_valid"] is False
    assert parsed["recommendation"] == "retry"


def test_parse_response_extracted_from_text():
    motor = _make_motor()
    text = 'texto antes {"is_valid": true, "reasoning": "sim"} e depois'
    parsed = motor._parse_response(text)
    assert parsed["is_valid"] is True


def test_parse_response_fallback():
    motor = _make_motor()
    parsed = motor._parse_response("sem json nenhum aqui")
    assert parsed["is_valid"] is False
    assert parsed["recommendation"] == "accept"
    assert parsed["confidence_adjusted"] == 0.5


def test_extract_json_valid():
    parsed = MotorClaudeLogic._extract_json('{"a": 1} trailing')
    assert parsed == {"a": 1}


def test_extract_json_missing_raises():
    with pytest.raises(ValueError):
        MotorClaudeLogic._extract_json("nada de chaves")


# ── Análise de padrão ───────────────────────────────────────────

def test_analyze_pattern_empty_history():
    motor = _make_motor()
    result = motor._analyze_pattern("OLA", [])
    assert result["pattern"] == "sem histórico"
    assert result["frequency"] == {}


def test_analyze_pattern_short_history():
    motor = _make_motor()
    result = motor._analyze_pattern("OLA", ["BOCA", "MÃO"])
    assert result["pattern"] == "sinais: BOCA, MÃO"
    assert result["frequency"] == {"BOCA": 1, "MÃO": 1}
    assert result["total_history"] == 2


def test_analyze_pattern_long_history_sequence():
    motor = _make_motor()
    history = ["A", "B", "C", "A", "B", "C"]
    result = motor._analyze_pattern("C", history)
    assert result["pattern"] == "sequência recente: A → B → C"
    assert result["frequency"]["A"] == 2
    assert result["total_history"] == 6


def test_build_prompt_contains_context():
    motor = _make_motor()
    prompt = motor._build_validation_prompt(
        signal="OLA",
        confidence=0.75,
        user_history=["BOCA", "OLA"],
        image_quality={"quality_score": 85, "hands_visible": True, "lighting_ok": True},
        pattern_analysis={"pattern": "sequência", "frequency": {"OLA": 3}},
    )
    assert "OLA" in prompt
    assert "75.0%" in prompt
    assert "BOCA, OLA" in prompt
    assert "3 vezes" in prompt


# ── Estatísticas ────────────────────────────────────────────────

def test_get_stats_before_calls():
    motor = _make_motor()
    stats = motor.get_stats()
    assert stats["total_calls"] == 0
    assert "avg_latency_ms" not in stats


def test_get_stats_after_calls():
    motor = _make_motor(_fake_client(
        '{"is_valid": true, "confidence_adjusted": 0.8, "recommendation": "accept"}'
    ))
    asyncio.run(motor.validate_with_context("OLA", 0.75, [], {}))
    stats = motor.get_stats()
    assert stats["total_calls"] == 1
    assert stats["avg_latency_ms"] > 0
    assert stats["error_rate"] == 0


def test_validation_result_defaults():
    result = ValidationResult(False, 0.5, "x", "accept", 1.0)
    assert result.status == "success"
    assert result.error is None
