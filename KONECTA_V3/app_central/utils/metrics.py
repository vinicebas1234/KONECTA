"""Coleta e análise de métricas de performance do reconhecimento."""

import logging
import statistics
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Deque, Dict, Protocol

logger = logging.getLogger(__name__)

# Faixas de confiança usadas na distribuição
CONFIDENCE_BINS = ("0-50%", "50-70%", "70-85%", "85-100%")


class ResultLike(Protocol):
    """Contrato mínimo de um resultado aceito por ``record_result``."""

    signal: str
    confidence: float
    latency_ms: float
    confidence_level: str
    validated_by: str


@dataclass
class MetricsSample:
    """Amostra individual de métrica."""

    timestamp: float
    signal: str
    confidence: float
    latency_ms: float
    confidence_level: str
    model: str


class MetricsCollector:
    """Coleta métricas de performance com janela deslizante."""

    def __init__(self, window_size: int = 1000):
        self.window_size = max(1, int(window_size))
        self.samples: Deque[MetricsSample] = deque(maxlen=self.window_size)
        self.stats: Dict[str, Any] = self._empty_stats()

    def record_result(self, result: ResultLike) -> None:
        """Registra um resultado na janela de amostras e recalcula estatísticas."""
        try:
            sample = MetricsSample(
                timestamp=time.time(),
                signal=result.signal,
                confidence=result.confidence,
                latency_ms=result.latency_ms,
                confidence_level=result.confidence_level,
                model=result.validated_by,
            )
            self.samples.append(sample)
            self._update_stats()
        except Exception as error:
            logger.error("Erro ao registrar métrica: %s", error)

    def _update_stats(self) -> None:
        """Recomputa estatísticas a partir da janela atual de amostras."""
        if not self.samples:
            return

        latencies = [s.latency_ms for s in self.samples]
        confidences = [s.confidence for s in self.samples]
        signals = [s.signal for s in self.samples]
        models = [s.model for s in self.samples]

        self.stats["total_processed"] = len(self.samples)
        self.stats["avg_latency_ms"] = statistics.mean(latencies)
        if len(latencies) >= 20:
            sorted_lat = sorted(latencies)
            self.stats["p95_latency_ms"] = sorted_lat[int(len(sorted_lat) * 0.95)]
            self.stats["p99_latency_ms"] = sorted_lat[int(len(sorted_lat) * 0.99)]

        self.stats["confidence_distribution"] = self._confidence_distribution(confidences)
        self.stats["signal_frequency"] = self._signal_frequency(signals)
        self.stats["model_performance"] = self._model_performance(models)

    @staticmethod
    def _confidence_distribution(confidences: list[float]) -> Dict[str, int]:
        """Distribui as confianças em faixas percentuais fixas."""
        return {
            "0-50%": sum(1 for c in confidences if c < 0.5),
            "50-70%": sum(1 for c in confidences if 0.5 <= c < 0.7),
            "70-85%": sum(1 for c in confidences if 0.7 <= c < 0.85),
            "85-100%": sum(1 for c in confidences if c >= 0.85),
        }

    @staticmethod
    def _signal_frequency(signals: list[str]) -> Dict[str, int]:
        """Conta a frequência dos sinais, ordenada do mais ao menos frequente."""
        counts: Dict[str, int] = {}
        for signal in signals:
            counts[signal] = counts.get(signal, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True)[:10])

    def _model_performance(self, models: list[str]) -> Dict[str, Any]:
        """Agrega latência e confiança média por modelo/validador."""
        performance: Dict[str, Any] = {}
        for model in set(models):
            model_samples = [s for s in self.samples if s.model == model]
            performance[model] = {
                "count": len(model_samples),
                "avg_latency": statistics.mean([s.latency_ms for s in model_samples]),
                "avg_confidence": statistics.mean([s.confidence for s in model_samples]),
            }
        return performance

    def get_stats(self) -> Dict:
        """Retorna estatísticas atualizadas."""
        return self.stats

    def get_summary(self) -> str:
        """Retorna resumo textual das estatísticas."""
        stats = self.stats
        summary = f"""
╔════════════════════════════════════════╗
║     KONECTA Intelligence Hub Stats     ║
╚════════════════════════════════════════╝

📊 Performance Geral:
   • Processados: {stats['total_processed']} sinais
   • Latência Média: {stats['avg_latency_ms']:.0f}ms
   • P95 Latência: {stats['p95_latency_ms']:.0f}ms
   • P99 Latência: {stats['p99_latency_ms']:.0f}ms

📈 Distribuição de Confiança:
"""
        for bin_name in CONFIDENCE_BINS:
            summary += (
                f"   • {bin_name}:  "
                f"{stats['confidence_distribution'].get(bin_name, 0)} sinais\n"
            )

        summary += "\n🎯 Top 5 Sinais:\n"
        for signal, count in list(stats["signal_frequency"].items())[:5]:
            summary += f"   • {signal}: {count}x\n"

        summary += "\n🔧 Performance por Modelo:\n"
        for model, perf in stats["model_performance"].items():
            summary += (
                f"   • {model}: {perf['count']} sinais, "
                f"{perf['avg_latency']:.0f}ms avg, "
                f"{perf['avg_confidence']:.0%} conf\n"
            )
        return summary

    def export_json(self) -> Dict[str, Any]:
        """Exporta métricas (estatísticas + amostras) em dicionário JSON-serializável."""
        return {
            "timestamp": datetime.now().isoformat(),
            "stats": self.stats,
            "samples": [asdict(sample) for sample in self.samples],
        }

    def reset(self) -> None:
        """Reseta a janela de amostras e as estatísticas."""
        self.samples.clear()
        self.stats = self._empty_stats()

    @staticmethod
    def _empty_stats() -> Dict[str, Any]:
        """Retorna um dicionário de estatísticas zerado."""
        return {
            "total_processed": 0,
            "avg_latency_ms": 0,
            "p95_latency_ms": 0,
            "p99_latency_ms": 0,
            "error_rate": 0,
            "confidence_distribution": {},
            "signal_frequency": {},
            "model_performance": {},
        }
