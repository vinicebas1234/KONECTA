"""Testes do Motor Grok Context (enriquecimento contextual).

Cobre HistoryCache, PatternAnalyzer, TemporalAnalyzer, WeightedVoter e o
orquestrador MotorGrokContext.
"""

# pylint: disable=missing-function-docstring,protected-access,unused-argument,C1803,too-few-public-methods,no-member,no-name-in-module

import asyncio
import time

import pytest

from app_central.motors.motor_grok_context import (
    SESSION_GAP_SECONDS,
    CandidateVote,
    ContextResult,
    HistoryCache,
    MotorGrokContext,
    PatternAnalyzer,
    SignalRecord,
    TemporalAnalyzer,
    WeightedVoter,
)


# ════════════════════════════════════════════════════════════════
# SignalRecord
# ════════════════════════════════════════════════════════════════

def test_signal_record_infers_hour():
    from datetime import datetime

    timestamp = datetime(2026, 8, 11, 21, 30).timestamp()
    record = SignalRecord(
        signal="OLA", confidence=0.9, timestamp=timestamp, session_id="s"
    )
    expected_hour = time.localtime(timestamp).tm_hour
    assert record.hour_of_day == expected_hour


def test_signal_record_keeps_explicit_hour():
    record = SignalRecord(
        signal="OLA", confidence=0.9, timestamp=0.0, session_id="s", hour_of_day=7
    )
    assert record.hour_of_day == 7


def test_candidate_vote_to_dict_rounds():
    vote = CandidateVote(
        signal="OLA", score=0.81234, votes=3.0, sources={"model": 0.123456}
    )
    data = vote.to_dict()
    assert data["score"] == 0.8123
    assert data["sources"]["model"] == 0.1235


# ════════════════════════════════════════════════════════════════
# HistoryCache
# ════════════════════════════════════════════════════════════════

def test_cache_put_get_roundtrip():
    cache = HistoryCache()
    cache.put("u1", "OLA", 0.9)
    history = cache.get("u1")
    assert len(history) == 1
    assert history[0].signal == "OLA"
    assert history[0].confidence == pytest.approx(0.9)
    assert history[0].session_id.startswith("u1:")


def test_cache_get_unknown_user_empty():
    cache = HistoryCache()
    assert cache.get("ghost") == []


def test_cache_get_signals_chronological():
    cache = HistoryCache()
    for signal in ("A", "B", "C"):
        cache.put("u1", signal)
    assert cache.get_signals("u1") == ["A", "B", "C"]


def test_cache_frequency():
    cache = HistoryCache()
    cache.put("u1", "A")
    cache.put("u1", "B")
    cache.put("u1", "A")
    assert cache.frequency("u1") == {"A": 2, "B": 1}
    assert cache.frequency("u1", "A") == {"A": 2}
    assert cache.frequency("u1", "Z") == {"Z": 0}
    assert cache.frequency("ghost") == {}


def test_cache_max_per_user_eviction():
    cache = HistoryCache(max_signals_per_user=3)
    for signal in ("A", "B", "C", "D"):
        cache.put("u1", signal)
    assert cache.get_signals("u1") == ["B", "C", "D"]
    assert cache.frequency("u1") == {"B": 1, "C": 1, "D": 1}
    assert cache.stats()["evictions"] == 0  # eviction via popleft, não LRU


def test_cache_max_users_lru_eviction():
    cache = HistoryCache(max_users=2)
    cache.put("u1", "A")
    cache.put("u2", "B")
    cache.put("u3", "C")
    stats = cache.stats()
    assert stats["users"] == 2
    assert stats["evictions"] == 1
    assert cache.get("u1") == []


def test_cache_ttl_expiration_and_full_removal():
    old = time.time() - 10_000
    cache = HistoryCache(ttl_seconds=60.0)
    cache.put("u1", "A", timestamp=old)
    cache.put("u1", "B", timestamp=time.time())
    removed = cache.purge_expired()
    assert removed == 1
    assert cache.get_signals("u1") == ["B"]


def test_cache_get_all_expired_returns_empty():
    old = time.time() - 10_000
    cache = HistoryCache(ttl_seconds=60.0)
    cache.put("u1", "A", timestamp=old)
    assert cache.get("u1") == []
    # usuário removido por completo
    assert cache.frequency("u1") == {}


def test_cache_session_rotation_after_gap():
    cache = HistoryCache()
    t0 = time.time()
    first = cache.put("u1", "A", timestamp=t0)
    second = cache.put("u1", "B", timestamp=t0 + SESSION_GAP_SECONDS + 10)
    assert first.session_id != second.session_id


def test_cache_session_reuses_within_gap():
    cache = HistoryCache()
    t0 = time.time()
    first = cache.put("u1", "A", timestamp=t0)
    second = cache.put("u1", "B", timestamp=t0 + 30)
    assert first.session_id == second.session_id


def test_cache_clear_user_and_all():
    cache = HistoryCache()
    cache.put("u1", "A")
    cache.put("u2", "B")
    cache.clear_user("u1")
    assert cache.get("u1") == []
    cache.clear_all()
    assert cache.get("u2") == []
    assert cache.stats()["users"] == 0


def test_cache_memory_estimate_and_stats():
    cache = HistoryCache()
    cache.put("u1", "A")
    stats = cache.stats()
    assert stats["users"] == 1
    assert stats["total_records"] == 1
    assert stats["memory_mb"] >= 0
    assert cache.memory_estimate_bytes() >= 256
    assert cache.memory_estimate_mb() >= 0


# ════════════════════════════════════════════════════════════════
# PatternAnalyzer
# ════════════════════════════════════════════════════════════════

def _records(signals, *, errors=None, session="s"):
    errors = errors or {}
    t0 = time.time()
    out = []
    for i, sig in enumerate(signals):
        out.append(
            SignalRecord(
                signal=sig,
                confidence=0.9,
                timestamp=t0 + i,
                session_id=session,
                is_error=errors.get(i, False),
                hour_of_day=10,
            )
        )
    return out


def test_pattern_analyzer_empty():
    result = PatternAnalyzer().analyze([], "OLA")
    assert result["status"] == "empty"
    assert result["pattern_change"]["changed"] is False
    assert result["common_sequences"] == []


def test_pattern_analyzer_basic():
    signals = ["A", "B", "A", "B", "A", "B"]
    result = PatternAnalyzer().analyze(_records(signals), "A")
    assert result["status"] == "ok"
    assert result["frequency"]["A"] == 3
    assert result["total_history"] == 6
    assert result["unique_signals"] == 2
    assert result["common_sequences"]
    assert "similarity" in result
    assert result["similarity"].get("A") == 1.0


def test_find_common_sequences_short():
    analyzer = PatternAnalyzer()
    assert analyzer.find_common_sequences(["A"]) == []


def test_find_common_sequences_ngrams():
    signals = ["A", "B", "A", "B", "A"]
    sequences = PatternAnalyzer().find_common_sequences(signals)
    assert any(s["sequence"] == ["A", "B"] for s in sequences)
    assert all(0 < s["support"] <= 1 for s in sequences)


def test_detect_pattern_change_insufficient():
    analyzer = PatternAnalyzer()
    result = analyzer.detect_pattern_change(["A", "B", "C"])
    assert result["changed"] is False
    assert "histórico insuficiente" in result["reason"]


def test_detect_pattern_change_shifted():
    signals = ["A"] * 10 + ["B"] * 10
    result = PatternAnalyzer().detect_pattern_change(signals, window=10)
    assert result["changed"] is True
    assert result["score"] >= 0.45


def test_detect_pattern_change_stable():
    signals = ["A", "B"] * 12
    result = PatternAnalyzer().detect_pattern_change(signals, window=10)
    assert result["changed"] is False


def test_signal_similarity_cases():
    assert PatternAnalyzer.signal_similarity("OLA", "OLA") == 1.0
    assert PatternAnalyzer.signal_similarity("ola", "OLA") == 1.0
    assert PatternAnalyzer.signal_similarity("", "X") == 0.0
    assert PatternAnalyzer.signal_similarity("OLA", "OLÁ") > 0.0
    assert PatternAnalyzer.signal_similarity("OLA", "NAO") < 1.0


def test_predict_next_markov():
    signals = ["A", "B", "A", "B", "A", "B"]
    predicted = PatternAnalyzer().predict_next(signals)
    assert predicted
    # Último sinal é "B"; transições B->A ocorrem 2x (sempre) => P(A)=1.0
    assert predicted[0]["signal"] == "A"
    assert predicted[0]["probability"] == pytest.approx(1.0)
    assert PatternAnalyzer().predict_next(["A"]) == []


# ════════════════════════════════════════════════════════════════
# TemporalAnalyzer
# ════════════════════════════════════════════════════════════════

def test_temporal_analyzer_empty():
    result = TemporalAnalyzer().analyze([])
    assert result["status"] == "empty"
    assert result["sessions"]["count"] == 0
    assert result["errors"]["total"] == 0


def test_temporal_analyzer_with_history():
    analyzer = TemporalAnalyzer()
    history = _records(["A", "B", "A", "A"], session="s1") + _records(
        ["C"], session="s2"
    )
    result = analyzer.analyze(history, current_hour=10)
    assert result["status"] == "ok"
    assert result["hour_of_day"]["current_hour"] == 10
    assert result["hour_of_day"]["distribution"] == {10: 5}
    assert result["sessions"]["count"] == 2
    assert result["sessions"]["avg_length"] == pytest.approx(2.5)
    assert result["errors"]["total"] == 0


def test_temporal_analyzer_error_history():
    history = _records(["A", "B", "A"], errors={1: True})
    result = TemporalAnalyzer().analyze(history, current_hour=9)
    assert result["errors"]["total"] == 1
    assert result["errors"]["rate"] == pytest.approx(0.3333)
    assert result["errors"]["most_error_prone"] == [("B", 1)]
    assert result["errors"]["recent"][0]["corrected"] is None


def test_hour_influences_single_hour_no_influence():
    history = _records(["A", "A"], session="s1")
    analyzer = TemporalAnalyzer()
    assert analyzer._hour_influences_signals(history)["influences"] is False


def test_hour_influences_two_hours_different_tops():
    t0 = time.time()
    history = [
        SignalRecord("A", 0.9, t0, "s", hour_of_day=9),
        SignalRecord("A", 0.9, t0 + 1, "s", hour_of_day=9),
        SignalRecord("B", 0.9, t0 + 2, "s", hour_of_day=14),
        SignalRecord("B", 0.9, t0 + 3, "s", hour_of_day=14),
    ]
    info = TemporalAnalyzer()._hour_influences_signals(history)
    assert info["influences"] is True
    assert info["entropy"] >= 0


def test_session_patterns_tail():
    history = _records(["A", "B", "C", "D", "E", "F"], session="s1")
    patterns = TemporalAnalyzer()._session_patterns(history)
    assert patterns["count"] == 1
    assert patterns["current_session_id"] == "s1"
    assert patterns["current_session_length"] == 6
    assert patterns["patterns"][0]["sequence_tail"] == ["B", "C", "D", "E", "F"]


# ════════════════════════════════════════════════════════════════
# WeightedVoter
# ════════════════════════════════════════════════════════════════

def test_vote_empty_history_fallback():
    result = WeightedVoter().vote("OLA", 0.55, [])
    assert result["fallback_used"] is True
    assert result["most_likely_signal"] == "OLA"
    assert result["confidence_adjusted"] == pytest.approx(0.55)
    assert result["candidates_considered"] == 1


def test_vote_frequency_dominates():
    history = _records(["A", "A", "A", "A", "A"])
    result = WeightedVoter().vote("B", 0.6, history, current_hour=10)
    assert result["fallback_used"] is False
    assert result["most_likely_signal"] == "A"
    assert result["candidates_considered"] >= 2
    assert 0.35 <= result["confidence_adjusted"] <= 0.90


def test_vote_when_best_equals_original_boosts():
    history = _records(["OLA", "OLA", "OLA"])
    result = WeightedVoter().vote("OLA", 0.5, history, current_hour=10)
    assert result["most_likely_signal"] == "OLA"
    assert result["confidence_adjusted"] <= 0.95


def test_vote_error_penalty():
    history = _records(
        ["BAD", "BAD", "BAD", "BAD", "GOOD"],
        errors={0: True, 1: True, 2: True, 3: True},
    )
    result = WeightedVoter().vote("BAD", 0.5, history, current_hour=10)
    assert result["most_likely_signal"] == "BAD"
    assert "error_penalty" in result["top_candidates"][0]["sources"]
    assert result["top_candidates"][0]["sources"]["error_penalty"] < 0


def test_vote_no_candidates_fallback():
    # Único histórico é sinal vazio e predição também vazia → nenhum candidato
    history = [SignalRecord("", 0.5, time.time(), "s", hour_of_day=10)]
    result = WeightedVoter().vote("", 0.5, history, current_hour=10)
    assert result["fallback_used"] is True
    assert result["most_likely_signal"] == ""
    assert result["candidates_considered"] == 0


def test_vote_similarity_boost():
    history = _records(["OLA", "BOM_DIA"])
    result = WeightedVoter().vote("OLÁ", 0.6, history, current_hour=10)
    assert result["candidates_considered"] >= 2


# ════════════════════════════════════════════════════════════════
# MotorGrokContext
# ════════════════════════════════════════════════════════════════

def _motor() -> MotorGrokContext:
    return MotorGrokContext()


def test_enrich_low_confidence_triggers_vote():
    motor = _motor()
    for sig in ("OLA", "OLA", "OLA"):
        motor.record_signal("u1", sig, confidence=0.9)
    result = asyncio.run(
        motor.enrich_with_context("OLA", 0.5, "u1")
    )
    assert result["status"] == "success"
    assert result["voting_details"]["triggered"] is True
    assert motor.performance_stats["votes_triggered"] == 1
    assert result["most_likely_signal"] == "OLA"
    assert result["recommendation"] in ("accept", "request_clarification", "retry")


def test_enrich_high_confidence_no_vote():
    motor = _motor()
    result = asyncio.run(
        motor.enrich_with_context("OLA", 0.9, "u1")
    )
    assert result["voting_details"]["triggered"] is False
    assert result["most_likely_signal"] == "OLA"
    assert result["confidence_adjusted"] == pytest.approx(0.9)
    assert motor.performance_stats["votes_triggered"] == 0


def test_enrich_empty_history_accept():
    motor = _motor()
    result = asyncio.run(motor.enrich_with_context("OLA", 0.5, "novo_user"))
    assert result["recommendation"] == "accept"
    assert result["fallback_used"] is True


def test_enrich_recommendation_by_adjusted():
    motor = _motor()
    result = asyncio.run(motor.enrich_with_context("X", 0.99, "u1"))
    assert result["recommendation"] == "accept"


def test_enrich_records_history_by_default():
    motor = _motor()
    asyncio.run(motor.enrich_with_context("OLA", 0.5, "u1"))
    assert motor.get_user_history("u1") == ["OLA"]


def test_enrich_no_record_when_disabled():
    motor = MotorGrokContext(auto_record=False)
    asyncio.run(motor.enrich_with_context("OLA", 0.5, "u1"))
    assert motor.get_user_history("u1") == []


def test_enrich_record_override():
    motor = MotorGrokContext(auto_record=False)
    asyncio.run(motor.enrich_with_context("OLA", 0.5, "u1", record=True))
    assert motor.get_user_history("u1") == ["OLA"]


def test_enrich_error_path(monkeypatch):
    motor = _motor()

    def _boom():
        raise RuntimeError("cache corrompido")

    monkeypatch.setattr(motor.cache, "get", _boom)
    result = asyncio.run(motor.enrich_with_context("OLA", 0.5, "u1"))
    assert result["status"] == "error"
    assert result["fallback_used"] is True
    assert result["most_likely_signal"] == "OLA"
    assert motor.performance_stats["errors"] == 1


def test_record_signal_and_error_helpers():
    motor = _motor()
    motor.record_signal("u1", "OLA", confidence=0.9)
    motor.record_error("u1", "BOCA", corrected_signal="BOCA_CORRIGIDO")
    records = motor.get_user_records("u1")
    assert [r.signal for r in records] == ["OLA", "BOCA"]
    assert records[1].is_error is True
    assert records[1].corrected_signal == "BOCA_CORRIGIDO"


def test_clear_user_and_analysis_helpers():
    motor = _motor()
    motor.record_signal("u1", "OLA")
    pattern = motor.analyze_patterns("u1", "OLA")
    assert pattern["status"] == "ok"
    temporal = motor.analyze_temporal("u1")
    assert temporal["status"] == "ok"
    motor.clear_user("u1")
    assert motor.get_user_history("u1") == []
    assert motor.analyze_patterns("u1")["status"] == "empty"


def test_vote_only_does_not_record():
    motor = _motor()
    motor.record_signal("u1", "OLA")
    result = motor.vote_only("OLA", 0.5, "u1")
    assert result["fallback_used"] is False
    assert motor.get_user_history("u1") == ["OLA"]  # sem duplicação


def test_get_stats_after_calls():
    motor = _motor()
    asyncio.run(motor.enrich_with_context("OLA", 0.9, "u1"))
    stats = motor.get_stats()
    assert stats["total_calls"] == 1
    assert stats["avg_latency_ms"] >= 0
    assert stats["error_rate"] == 0
    assert stats["fallback_rate"] == 0
    assert stats["memory_ok"] is True
    assert "cache" in stats


def test_clear_stats():
    motor = _motor()
    asyncio.run(motor.enrich_with_context("OLA", 0.9, "u1"))
    motor.clear_stats()
    assert motor.get_stats()["total_calls"] == 0


def test_record_perf_high_latency_flag():
    motor = _motor()
    motor._record_perf(1500.0)
    assert motor.performance_stats["high_latency_count"] == 1
    assert motor.performance_stats["total_calls"] == 1


def test_context_result_to_dict():
    result = ContextResult(
        most_likely_signal="OLA",
        confidence_adjusted=0.8,
        top_3_candidates=[],
        original_signal="OLA",
        original_confidence=0.5,
        pattern_analysis={},
        temporal_context={},
        voting_details={},
        recommendation="accept",
        latency_ms=1.0,
    )
    data = result.to_dict()
    assert data["most_likely_signal"] == "OLA"
    assert data["status"] == "success"
