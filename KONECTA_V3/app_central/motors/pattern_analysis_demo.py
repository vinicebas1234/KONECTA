"""
Demo interativa — Análise de padrões do Motor Grok Context.

Mostra:
  1. Cache de histórico (últimos 100, TTL)
  2. Sequências comuns e mudança de padrão
  3. Contexto temporal (hora, sessão, erros)
  4. Votação ponderada top-3 quando confidence < 0.7
  5. Latência e uso de memória

Uso:
  python -m app_central.motors.pattern_analysis_demo
  python app_central/motors/pattern_analysis_demo.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import List

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# pylint: disable=wrong-import-position
from app_central.motors.motor_grok_context import MotorGrokContext  # noqa: E402
# pylint: enable=wrong-import-position


# Sequência típica de conversa em Libras (simulada)
CONVERSATION: List[str] = [
    "OLA",
    "TUDO_BEM",
    "SIM",
    "NOME",
    "EU",
    "PRAZER",
    "OLA",
    "TUDO_BEM",
    "NAO",
    "OBRIGADO",
    "OLA",
    "TUDO_BEM",
    "SIM",
    "TCHAU",
    "OLA",
    "TUDO_BEM",
    "SIM",
    "POR_FAVOR",
    "AGUA",
    "OBRIGADO",
    "OLA",
    "TUDO_BEM",
    "SIM",
]

# Segunda fase: muda o padrão (consulta médica)
PATTERN_SHIFT: List[str] = [
    "DOR",
    "CABECA",
    "SIM",
    "DOR",
    "COSTAS",
    "NAO",
    "REMEDIO",
    "DOR",
    "CABECA",
    "SIM",
]


def _banner(title: str) -> None:
    """Imprime um cabeçalho de seção no console."""
    print("\n" + "═" * 64)
    print(f"  {title}")
    print("═" * 64)


def _kv(label: str, value) -> None:
    """Imprime um par rótulo/valor alinhado."""
    print(f"  • {label:<28} {value}")


async def run_demo() -> None:
    """Executa a demonstração completa do Motor Grok Context."""
    # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    # Script linear de demonstração: cada seção corresponde a um _banner.
    motor = MotorGrokContext(
        history_size=100,
        ttl_seconds=3600,
        confidence_threshold=0.7,
        auto_record=False,
    )
    user = "demo_signer"

    # ── 1. Popular histórico ─────────────────────────────────
    _banner("1. Cache de histórico")
    t0 = time.time()
    for i, sig in enumerate(CONVERSATION):
        # Simula timestamps espaçados de ~30s
        motor.record_signal(
            user, sig, confidence=0.88 + (i % 5) * 0.02, timestamp=t0 + i * 30
        )
    # Injeta alguns erros
    motor.record_error(user, "OLHO", 0.35, corrected_signal="OLA")
    motor.record_error(user, "BOCA", 0.40, corrected_signal="AGUA")

    hist = motor.get_user_history(user)
    _kv("Sinais armazenados", len(hist))
    _kv("Últimos 8", " → ".join(hist[-8:]))
    _kv("Memória estimada", f"{motor.cache.memory_estimate_mb():.3f} MB")
    _kv("Capacidade máx/user", motor.cache.max_signals_per_user)
    _kv("TTL", f"{motor.cache.ttl_seconds:.0f}s")

    # ── 2. Análise de padrões ────────────────────────────────
    _banner("2. Análise de padrões")
    patterns = motor.analyze_patterns(user, current_signal="OLA")
    print("  Sequências comuns (top 5):")
    for seq in patterns["common_sequences"][:5]:
        chain = " → ".join(seq["sequence"])
        print(
            f"    [{seq['count']}x | support={seq['support']:.0%}]  {chain}"
        )
    change = patterns["pattern_change"]
    _kv("Mudança de padrão?", f"{change['changed']} (score={change['score']})")
    _kv("Motivo", change["reason"])
    print("  Similaridade com 'OLA':")
    for sig, sim in list(patterns["similarity"].items())[:5]:
        print(f"    {sig:<16} {sim:.2%}")
    print("  Próximo sinal previsto (Markov):")
    for p in patterns["predicted_next"][:3]:
        print(f"    {p['signal']:<16} P={p['probability']:.0%}  (n={p['count']})")

    # ── 3. Contexto temporal ─────────────────────────────────
    _banner("3. Contexto temporal")
    temporal = motor.analyze_temporal(user)
    hod = temporal["hour_of_day"]
    _kv("Hora atual", hod["current_hour"])
    _kv("Hora influencia sinais?", hod["influences_signals"])
    _kv("Entropia por hora", hod["hour_entropy"])
    if hod["peak_hours"]:
        peaks = ", ".join(
            f"{p['hour']}h({p['count']})" for p in hod["peak_hours"]
        )
        _kv("Horários de pico", peaks)
    sess = temporal["sessions"]
    _kv("Sessões", sess["count"])
    _kv("Tamanho médio sessão", sess["avg_length"])
    err = temporal["errors"]
    _kv("Erros totais", f"{err['total']} (taxa={err['rate']:.0%})")
    if err["most_error_prone"]:
        _kv("Sinais com mais erro", err["most_error_prone"])

    # ── 4. Votação (confidence < 0.7) ─────────────────────────
    _banner("4. Votação ponderada (confidence < 0.7)")

    # Garante que o último sinal seja OLA → sequência sugere TUDO_BEM
    motor.record_signal(user, "OLA", 0.9, timestamp=time.time())

    scenarios = [
        ("TUDO_BEM", 0.55, "modelo incerto, mas alinhado ao padrão"),
        ("OBRIGADO", 0.38, "modelo errou — padrão sugere TUDO_BEM"),
        ("XYZ_UNKNOWN", 0.25, "sinal desconhecido — histórico decide"),
        ("SIM", 0.82, "confiança alta — sem votação"),
    ]

    for signal, conf, note in scenarios:
        result = await motor.enrich_with_context(
            signal=signal, confidence=conf, user_id=user, record=False
        )
        print(f"\n  Cenário: {note}")
        print(f"    input     : {signal} @ {conf:.0%}")
        print(f"    output    : {result['most_likely_signal']} "
              f"@ {result['confidence_adjusted']:.0%}")
        print(f"    vote?     : {result['voting_details']['triggered']}")
        print(f"    fallback? : {result['fallback_used']}")
        print(f"    recommend : {result['recommendation']}")
        print(f"    latency   : {result['latency_ms']:.2f} ms")
        print("    top-3:")
        for i, c in enumerate(result["top_3_candidates"], 1):
            sources = ", ".join(
                f"{k}={v:.3f}" for k, v in c.get("sources", {}).items()
            )
            print(f"      {i}. {c['signal']:<12} score={c['score']:.3f}  [{sources}]")

    # ── 5. Mudança de padrão ─────────────────────────────────
    _banner("5. Detecção de mudança de padrão")
    shift_t0 = time.time() + 1000
    for i, sig in enumerate(PATTERN_SHIFT):
        motor.record_signal(
            user, sig, 0.9, timestamp=shift_t0 + i * 20
        )
    patterns2 = motor.analyze_patterns(user, "DOR")
    change2 = patterns2["pattern_change"]
    _kv("Mudança detectada?", change2["changed"])
    _kv("Score", change2["score"])
    _kv("Motivo", change2["reason"])
    if "recent_top" in change2:
        _kv("Top recente", change2["recent_top"])
    if "older_top" in change2:
        _kv("Top anterior", change2["older_top"])

    # ── 6. Fallback histórico vazio ──────────────────────────
    _banner("6. Fallback (histórico vazio)")
    empty = await motor.enrich_with_context("NOVO", 0.4, "ghost_user")
    _kv("most_likely", empty["most_likely_signal"])
    _kv("fallback_used", empty["fallback_used"])
    _kv("reason", empty["voting_details"]["reason"])

    # ── 7. Benchmark rápido de latência ──────────────────────
    _banner("7. Benchmark de latência (100 chamadas)")
    # Aquece
    for _ in range(5):
        await motor.enrich_with_context("DOR", 0.4, user, record=False)

    latencies = []
    for _ in range(100):
        r = await motor.enrich_with_context("DOR", 0.4, user, record=False)
        latencies.append(r["latency_ms"])

    latencies.sort()
    avg = sum(latencies) / len(latencies)
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(0.95 * (len(latencies) - 1))]
    p99 = latencies[int(0.99 * (len(latencies) - 1))]
    _kv("avg", f"{avg:.3f} ms")
    _kv("p50", f"{p50:.3f} ms")
    _kv("p95", f"{p95:.3f} ms")
    _kv("p99", f"{p99:.3f} ms")
    _kv("max", f"{max(latencies):.3f} ms")
    _kv("meta < 1000ms?", "OK ✓" if p99 < 1000 else "FALHOU ✗")

    # ── Stats finais ─────────────────────────────────────────
    _banner("Stats finais")
    stats = motor.get_stats()
    for k, v in stats.items():
        if k == "cache":
            print("  • cache:")
            for ck, cv in v.items():
                print(f"      - {ck}: {cv}")
        else:
            _kv(k, v)

    print("\n✅ Demo concluída.\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
