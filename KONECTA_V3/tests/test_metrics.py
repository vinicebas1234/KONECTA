"""Testes do MetricsCollector (métricas de performance)."""

# pylint: disable=missing-function-docstring,protected-access,C1803,too-few-public-methods

from types import SimpleNamespace

import pytest

from app_central.utils.metrics import CONFIDENCE_BINS, MetricsCollector, MetricsSample


def _result(signal="OLA", confidence=0.9, latency=100.0, level="high", model="ensemble"):
    return SimpleNamespace(
        signal=signal,
        confidence=confidence,
        latency_ms=latency,
        confidence_level=level,
        validated_by=model,
    )


def test_record_result_populates_stats():
    collector = MetricsCollector()
    collector.record_result(_result())
    stats = collector.get_stats()
    assert stats["total_processed"] == 1
    assert stats["avg_latency_ms"] == pytest.approx(100.0)
    assert stats["confidence_distribution"]["85-100%"] == 1
    assert stats["signal_frequency"]["OLA"] == 1
    assert stats["model_performance"]["ensemble"]["count"] == 1


def test_window_size_limits_samples():
    collector = MetricsCollector(window_size=5)
    for i in range(10):
        collector.record_result(_result(signal=f"S{i}", latency=float(i)))
    assert len(collector.samples) == 5
    assert collector.get_stats()["total_processed"] == 5


def test_record_result_without_p95_before_20():
    collector = MetricsCollector()
    for i in range(5):
        collector.record_result(_result(latency=float(i)))
    stats = collector.get_stats()
    assert stats["p95_latency_ms"] == 0  # mantém default zerado


def test_p95_p99_after_20_samples():
    collector = MetricsCollector()
    for i in range(30):
        collector.record_result(_result(latency=float(i)))
    stats = collector.get_stats()
    sorted_lat = sorted(range(30))
    assert stats["p95_latency_ms"] == sorted_lat[int(30 * 0.95)]
    assert stats["p99_latency_ms"] == sorted_lat[int(30 * 0.99)]
    assert stats["p95_latency_ms"] <= stats["p99_latency_ms"]


def test_confidence_distribution_bins():
    collector = MetricsCollector()
    values = [0.1, 0.2, 0.55, 0.75, 0.9]
    for value in values:
        collector.record_result(_result(confidence=value))
    distribution = collector.get_stats()["confidence_distribution"]
    assert distribution == {
        "0-50%": 2,
        "50-70%": 1,
        "70-85%": 1,
        "85-100%": 1,
    }


def test_signal_frequency_top10_sorted():
    collector = MetricsCollector()
    for i in range(15):
        collector.record_result(_result(signal=f"S{i % 3}"))
    freq = collector.get_stats()["signal_frequency"]
    assert list(freq.values()) == sorted(freq.values(), reverse=True)
    assert len(freq) <= 10


def test_model_performance_averages():
    collector = MetricsCollector()
    collector.record_result(_result(model="konecta_v3", latency=100.0, confidence=0.9))
    collector.record_result(_result(model="konecta_v3", latency=200.0, confidence=0.8))
    collector.record_result(_result(model="claude_logic", latency=50.0, confidence=0.75))
    perf = collector.get_stats()["model_performance"]
    assert perf["konecta_v3"]["avg_latency"] == pytest.approx(150.0)
    assert perf["konecta_v3"]["avg_confidence"] == pytest.approx(0.85)
    assert perf["claude_logic"]["count"] == 1


def test_record_result_invalid_object_does_not_crash():
    collector = MetricsCollector()

    class _Broken:
        pass

    collector.record_result(_Broken())  # deve logar erro, não lançar
    assert collector.get_stats()["total_processed"] == 0


def test_get_summary_contains_sections():
    collector = MetricsCollector()
    collector.record_result(_result())
    summary = collector.get_summary()
    assert "Performance Geral" in summary
    assert "Distribuição de Confiança" in summary
    assert "Top 5 Sinais" in summary
    assert "Performance por Modelo" in summary
    for bin_name in CONFIDENCE_BINS:
        assert bin_name in summary


def test_export_json_structure():
    collector = MetricsCollector()
    collector.record_result(_result())
    payload = collector.export_json()
    assert "timestamp" in payload
    assert payload["stats"]["total_processed"] == 1
    assert len(payload["samples"]) == 1
    assert payload["samples"][0]["signal"] == "OLA"


def test_reset_clears_everything():
    collector = MetricsCollector()
    collector.record_result(_result())
    collector.reset()
    stats = collector.get_stats()
    assert stats["total_processed"] == 0
    assert list(collector.samples) == []
    assert stats["confidence_distribution"] == {}


def test_empty_stats_keys():
    stats = MetricsCollector._empty_stats()
    assert stats["total_processed"] == 0
    assert stats["avg_latency_ms"] == 0
    assert stats["p95_latency_ms"] == 0
    assert stats["p99_latency_ms"] == 0
    assert stats["error_rate"] == 0


def test_metrics_sample_dataclass():
    sample = MetricsSample(
        timestamp=0.0,
        signal="OLA",
        confidence=0.9,
        latency_ms=1.0,
        confidence_level="high",
        model="konecta_v3",
    )
    assert sample.signal == "OLA"
    assert sample.confidence_level == "high"
