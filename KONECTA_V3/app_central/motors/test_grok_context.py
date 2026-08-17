"""
Testes do Motor Grok Context.

Cobertura:
  - Cache (100 sinais, O(1), TTL)
  - Análise de padrões
  - Contexto temporal
  - Votação ponderada (top-3, confidence < 0.7)
  - Fallback com histórico vazio
  - Latência < 1000ms
  - Memória < 500MB
"""

from __future__ import annotations

import asyncio
import sys
import time
import unittest
from pathlib import Path

# Garante import do pacote (raiz do projeto no path)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app_central.motors.motor_grok_context import (  # noqa: E402
    HistoryCache,
    MotorGrokContext,
    PatternAnalyzer,
    SignalRecord,
    TemporalAnalyzer,
    WeightedVoter,
)


def _await(coro):
    """Executa coroutine de forma compatível com unittest."""
    return asyncio.run(coro)


class TestHistoryCache(unittest.TestCase):
    """Testes do cache de histórico de sinais por usuário."""

    def setUp(self) -> None:
        self.cache = HistoryCache(max_signals_per_user=100, ttl_seconds=3600)

    def test_put_and_get_o1_access(self) -> None:
        """Inserção e leitura preservam a ordem cronológica."""
        self.cache.put("u1", "OLA", 0.9)
        self.cache.put("u1", "SIM", 0.8)
        hist = self.cache.get("u1")
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist[0].signal, "OLA")
        self.assertEqual(hist[1].signal, "SIM")

    def test_max_100_signals(self) -> None:
        """Janela fica limitada aos 100 sinais mais recentes (FIFO)."""
        for i in range(150):
            self.cache.put("u1", f"S{i % 10}", 0.9)
        hist = self.cache.get("u1")
        self.assertEqual(len(hist), 100)
        # FIFO: primeiros 50 saíram
        self.assertEqual(hist[0].signal, "S0")  # S50 % 10 = S0
        self.assertEqual(self.cache.stats()["total_records"], 100)

    def test_frequency_index(self) -> None:
        """Índice de frequência consultado em O(1)."""
        for s in ["A", "B", "A", "A", "C"]:
            self.cache.put("u1", s, 1.0)
        freq = self.cache.frequency("u1")
        self.assertEqual(freq["A"], 3)
        self.assertEqual(freq["B"], 1)
        self.assertEqual(self.cache.frequency("u1", "A")["A"], 3)

    def test_ttl_expiration(self) -> None:
        """Registros mais antigos que o TTL são expurgados."""
        cache = HistoryCache(max_signals_per_user=100, ttl_seconds=0.15)
        now = time.time()
        cache.put("u1", "OLD", 1.0, timestamp=now - 1.0)
        cache.put("u1", "NEW", 1.0, timestamp=now)
        time.sleep(0.2)
        # OLD deve expirar; NEW também se passou TTL desde put...
        # Reinsere NEW fresco e verifica purge
        cache2 = HistoryCache(max_signals_per_user=100, ttl_seconds=0.2)
        cache2.put("u1", "OLD", 1.0, timestamp=time.time() - 1.0)
        cache2.put("u1", "FRESH", 1.0, timestamp=time.time())
        hist = cache2.get("u1")
        signals = [r.signal for r in hist]
        self.assertIn("FRESH", signals)
        self.assertNotIn("OLD", signals)

    def test_empty_user_returns_empty(self) -> None:
        self.assertEqual(self.cache.get("nobody"), [])
        self.assertEqual(self.cache.frequency("nobody"), {})

    def test_memory_under_500mb(self) -> None:
        """Memória estimada fica bem abaixo do teto de 500MB."""
        for u in range(50):
            for i in range(100):
                self.cache.put(f"user_{u}", f"SIG_{i % 20}", 0.85)
        mb = self.cache.memory_estimate_mb()
        self.assertLess(mb, 500.0, f"Memória estimada {mb:.1f}MB excede 500MB")
        self.assertLess(mb, 50.0, f"Esperado << 500MB, got {mb:.1f}MB")

    def test_session_split_on_gap(self) -> None:
        """Gaps maiores que 5 minutos iniciam uma nova sessão."""
        t0 = time.time()
        self.cache.put("u1", "A", 1.0, timestamp=t0)
        self.cache.put("u1", "B", 1.0, timestamp=t0 + 10)
        # Gap > 5 min → nova sessão
        self.cache.put("u1", "C", 1.0, timestamp=t0 + 400)
        hist = self.cache.get("u1")
        self.assertEqual(hist[0].session_id, hist[1].session_id)
        self.assertNotEqual(hist[1].session_id, hist[2].session_id)


class TestPatternAnalyzer(unittest.TestCase):
    """Testes do analisador de padrões de sequência."""

    def setUp(self) -> None:
        self.pa = PatternAnalyzer()

    def _recs(self, signals) -> list:
        t = time.time()
        return [
            SignalRecord(s, 0.9, t + i, "sess1", hour_of_day=10)
            for i, s in enumerate(signals)
        ]

    def test_common_sequences(self) -> None:
        """Encontra n-gramas mais frequentes no histórico."""
        sigs = ["OLA", "TUDO_BEM", "OLA", "TUDO_BEM", "SIM", "OLA", "TUDO_BEM"]
        seqs = self.pa.find_common_sequences(sigs)
        self.assertTrue(len(seqs) > 0)
        top = seqs[0]["sequence"]
        self.assertEqual(top, ["OLA", "TUDO_BEM"])

    def test_pattern_change_detection(self) -> None:
        """Detecta mudança de padrão entre janelas recente e anterior."""
        # Janela antiga: A/B; recente: X/Y → mudança
        older = ["A", "B"] * 5
        recent = ["X", "Y"] * 5
        change = self.pa.detect_pattern_change(older + recent, window=10)
        self.assertTrue(change["changed"])
        self.assertGreaterEqual(change["score"], 0.45)

    def test_pattern_stable(self) -> None:
        sigs = ["A", "B"] * 20
        change = self.pa.detect_pattern_change(sigs, window=10)
        self.assertFalse(change["changed"])

    def test_signal_similarity(self) -> None:
        self.assertEqual(self.pa.signal_similarity("OLA", "OLA"), 1.0)
        self.assertGreater(self.pa.signal_similarity("OLHO", "OLHOS"), 0.7)
        self.assertLess(self.pa.signal_similarity("OLA", "OBRIGADO"), 0.5)

    def test_predict_next(self) -> None:
        """Prevê o próximo sinal por Markov de ordem 1."""
        # last=C → sem transição; use last A
        preds_a = self.pa.predict_next(["A", "B", "A", "B", "A"])
        self.assertEqual(preds_a[0]["signal"], "B")

    def test_analyze_empty(self) -> None:
        result = self.pa.analyze([], "OLA")
        self.assertEqual(result["status"], "empty")


class TestTemporalAnalyzer(unittest.TestCase):
    """Testes do analisador de contexto temporal."""

    def setUp(self) -> None:
        self.ta = TemporalAnalyzer()

    def test_hour_and_errors(self) -> None:
        """Analisa distribuição por hora, sessões e histórico de erros."""
        t = time.time()
        history = [
            SignalRecord("OLA", 0.9, t, "s1", is_error=False, hour_of_day=9),
            SignalRecord("SIM", 0.5, t + 1, "s1", is_error=True, hour_of_day=9),
            SignalRecord("NAO", 0.9, t + 2, "s1", is_error=False, hour_of_day=14),
            SignalRecord("OLA", 0.4, t + 3, "s2", is_error=True, hour_of_day=14,
                         corrected_signal="OLHO"),
        ]
        result = self.ta.analyze(history, current_hour=9)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["errors"]["total"], 2)
        self.assertGreater(result["errors"]["rate"], 0)
        self.assertEqual(result["sessions"]["count"], 2)
        self.assertIn(9, result["hour_of_day"]["distribution"])

    def test_empty_history(self) -> None:
        result = self.ta.analyze([])
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["errors"]["total"], 0)


class TestWeightedVoter(unittest.TestCase):
    """Testes do votador ponderado top-3."""

    def setUp(self) -> None:
        self.voter = WeightedVoter(top_k=3)

    def _hist(self, signals) -> list:
        t = time.time()
        return [
            SignalRecord(s, 0.9, t + i, "sess", hour_of_day=time.localtime().tm_hour)
            for i, s in enumerate(signals)
        ]

    def test_fallback_empty_history(self) -> None:
        result = self.voter.vote("OLA", 0.5, [])
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["most_likely_signal"], "OLA")
        self.assertEqual(len(result["top_candidates"]), 1)

    def test_top3_candidates(self) -> None:
        """Retorna até 3 candidatos e o mais provável pela transição."""
        # Histórico termina em OLA → Markov favorece SIM como próximo
        hist = self._hist(
            ["OLA", "SIM", "OLA", "SIM", "OLA", "SIM", "NAO", "OLA"]
        )
        result = self.voter.vote("XYZ", 0.4, hist)
        self.assertFalse(result["fallback_used"])
        self.assertLessEqual(len(result["top_candidates"]), 3)
        self.assertGreaterEqual(len(result["top_candidates"]), 1)
        # Após OLA, SIM é o mais provável pela transição
        self.assertEqual(result["most_likely_signal"], "SIM")
        top_signals = [c["signal"] for c in result["top_candidates"]]
        self.assertEqual(len(top_signals), 3)

    def test_model_signal_boosted_when_frequent(self) -> None:
        hist = self._hist(["OLA"] * 20 + ["SIM"] * 2)
        result = self.voter.vote("OLA", 0.55, hist)
        self.assertEqual(result["most_likely_signal"], "OLA")
        self.assertGreaterEqual(result["confidence_adjusted"], 0.55)


class TestMotorGrokContext(unittest.TestCase):
    """Testes do motor principal de enriquecimento contextual."""

    def setUp(self) -> None:
        self.motor = MotorGrokContext(
            history_size=100,
            ttl_seconds=3600,
            confidence_threshold=0.7,
            auto_record=True,
        )

    def test_enrich_empty_history_fallback(self) -> None:
        """Histórico vazio cai no fallback mantendo a predição original."""
        result = _await(self.motor.enrich_with_context("OLA", 0.5, "new_user"))
        self.assertEqual(result["most_likely_signal"], "OLA")
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["status"], "success")
        self.assertIn("top_3_candidates", result)

    def test_enrich_with_history_voting(self) -> None:
        """Votação é disparada com histórico e devolve top-3 candidatos."""
        for s in ["OLA", "TUDO_BEM", "OLA", "TUDO_BEM", "OLA", "TUDO_BEM", "SIM"]:
            self.motor.record_signal("u1", s, 0.9)

        result = _await(
            self.motor.enrich_with_context("???", 0.4, "u1", record=False)
        )
        self.assertFalse(result["fallback_used"])
        self.assertEqual(len(result["top_3_candidates"]), 3)
        self.assertIn("pattern_analysis", result)
        self.assertIn("temporal_context", result)
        self.assertTrue(result["voting_details"]["triggered"])
        # Após SIM no fim, mas sequência OLA→TUDO_BEM é forte;
        # com current ??? a votação deve preferir sinais do histórico
        self.assertIn(
            result["most_likely_signal"],
            {"OLA", "TUDO_BEM", "SIM"},
        )

    def test_no_vote_when_high_confidence(self) -> None:
        """Confiança alta não dispara votação e mantém a predição."""
        self.motor.record_signal("u1", "OLA", 0.9)
        result = _await(
            self.motor.enrich_with_context("OLA", 0.85, "u1", record=False)
        )
        self.assertFalse(result["voting_details"]["triggered"])
        self.assertEqual(result["most_likely_signal"], "OLA")

    def test_latency_under_1000ms(self) -> None:
        """Latência média e P99 ficam abaixo de 1000ms."""
        for i in range(100):
            self.motor.record_signal("u_lat", f"S{i % 15}", 0.8)

        latencies = []
        for _ in range(50):
            result = _await(
                self.motor.enrich_with_context("S1", 0.45, "u_lat", record=False)
            )
            latencies.append(result["latency_ms"])

        avg = sum(latencies) / len(latencies)
        p99 = sorted(latencies)[int(0.99 * (len(latencies) - 1))]
        self.assertLess(avg, 1000.0, f"avg latency {avg:.1f}ms >= 1000ms")
        self.assertLess(p99, 1000.0, f"p99 latency {p99:.1f}ms >= 1000ms")
        # Em prática deve ser bem abaixo de 100ms
        self.assertLess(avg, 100.0, f"avg {avg:.1f}ms inesperadamente alto")

    def test_pipeline_compatible_keys(self) -> None:
        """Pipeline usa result.get('most_likely_signal')."""
        result = _await(self.motor.enrich_with_context("X", 0.3, "u"))
        self.assertIn("most_likely_signal", result)
        self.assertIsInstance(result["most_likely_signal"], str)

    def test_record_error_feeds_temporal(self) -> None:
        """Erros registrados alimentam o histórico temporal."""
        self.motor.record_signal("u1", "OLA", 0.9)
        self.motor.record_error("u1", "OLHO", 0.4, corrected_signal="OLA")
        temporal = self.motor.analyze_temporal("u1")
        self.assertEqual(temporal["errors"]["total"], 1)
        self.assertEqual(temporal["errors"]["recent"][0]["corrected"], "OLA")

    def test_stats_and_memory(self) -> None:
        """Estatísticas expõem contadores, memória e flag de limite."""
        _await(self.motor.enrich_with_context("A", 0.4, "u"))
        stats = self.motor.get_stats()
        self.assertGreaterEqual(stats["total_calls"], 1)
        self.assertTrue(stats["memory_ok"])
        self.assertLess(stats["memory_mb"], 500.0)

    def test_history_capped_at_100(self) -> None:
        """Histórico por usuário fica limitado a 100 sinais."""
        for i in range(200):
            self.motor.record_signal("cap", f"S{i}", 0.9)
        self.assertEqual(len(self.motor.get_user_history("cap")), 100)


class TestIntegrationScenario(unittest.TestCase):
    """Cenário realista: usuário com padrão OLA → TUDO_BEM → SIM."""

    def test_disambiguation_low_confidence(self) -> None:
        """Contexto resolve ambiguidade quando a confiança do modelo é baixa."""
        motor = MotorGrokContext(auto_record=False)
        pattern = ["OLA", "TUDO_BEM", "SIM"] * 8
        for s in pattern:
            motor.record_signal("signer_01", s, 0.92)

        # Modelo incerto após OLA (último do histórico se gravássemos,
        # mas aqui simulamos: histórico termina em SIM, próxima seria OLA)
        # Força histórico terminando em OLA:
        motor.record_signal("signer_01", "OLA", 0.9)

        result = _await(
            motor.enrich_with_context(
                signal="OBRIGADO",  # modelo errou
                confidence=0.42,
                user_id="signer_01",
            )
        )
        # Sequência sugere TUDO_BEM após OLA
        self.assertEqual(result["most_likely_signal"], "TUDO_BEM")
        top_signals = [c["signal"] for c in result["top_3_candidates"]]
        self.assertIn("TUDO_BEM", top_signals)
        self.assertLess(result["latency_ms"], 1000.0)


def run_all() -> None:
    """Executa a suíte completa de testes do Grok Context."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in (
        TestHistoryCache,
        TestPatternAnalyzer,
        TestTemporalAnalyzer,
        TestWeightedVoter,
        TestMotorGrokContext,
        TestIntegrationScenario,
    ):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    run_all()
