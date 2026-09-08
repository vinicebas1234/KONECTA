"""Testes reais do Ciclo 5 (`learn_signal`) do Libras Learning Agent.

Mesmo espírito de `test_web_search.py`/`test_compare_sources.py`: SQLite
temporário real por teste, busca real via `ddgs`, comparação real via
Gemini (tier gratuito) — sem mock de banco. Precisa de `GEMINI_API_KEY`
configurada no ambiente, mesma exigência do Ciclo 4 (`pytestmark` abaixo
pula o arquivo inteiro se não houver chave, mesmo padrão de
`test_compare_sources.py`).

Usos de monkeypatch no arquivo:

- `test_learn_signal_search_failure_marks_signal_failed`: mesmo truque de
  `test_web_search.py` (`RealDDGS.text`, a classe real por trás do proxy
  lazy-load de `ddgs.DDGS`) para provar que uma falha real de busca deixa o
  `Signal` em FAILED com o `AgentEvent(error)` certo.
- `test_learn_signal_dedups_signal_source_across_calls`: reaproveita a MESMA
  lista de resultados (de uma busca real única) nas duas chamadas de
  `learn_signal` — igual ao teste de dedup do Ciclo 3
  (`test_register_sources_dedup_by_url`, que chama a busca uma vez só e
  registra os MESMOS resultados duas vezes) — para não depender de o
  DuckDuckGo devolver exatamente a mesma lista em duas buscas reais
  separadas. Também mocka `compare_sources` — desvio deliberado, ver
  docstring do teste: a chave real de Gemini bateu na quota diária do tier
  gratuito (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, 20
  chamadas/dia por modelo) durante a verificação deste ciclo, confirmada por
  erro 429 real do próprio Google (colado no relatório). O que este teste
  prova (vínculo `SignalSource`) não depende do resultado da classificação —
  isso já foi exercitado de ponta a ponta com Gemini real no teste 1.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from ddgs.ddgs import DDGS as RealDDGS
from ddgs.exceptions import DDGSException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# `agent/__init__.py` faz `from .learn_signal import learn_signal`, o que reaproveita
# o mesmo nome `learn_signal` para o submódulo e para a função — `import ... as`
# via atributo pegaria a função (o último a vencer o nome), não o submódulo. Mesma
# situação documentada em `test_compare_sources.py` (Ciclo 4) para `compare_sources`.
learn_signal_module = importlib.import_module("libras_learning_agent.agent.learn_signal")

from libras_learning_agent.agent.learn_signal import learn_signal
from libras_learning_agent.core.config import get_settings
from libras_learning_agent.database.db import Base
from libras_learning_agent.database.models import AgentEvent, Signal, SignalSource, Source
from libras_learning_agent.research.compare_sources import SourceComparison
from libras_learning_agent.research.web_search import WebSearchError, search_web

pytestmark = pytest.mark.skipif(
    not get_settings().gemini_api_key,
    reason="GEMINI_API_KEY não configurada no ambiente — ver instruções do Ciclo 4",
)


def _sqlite_url(path: Path) -> str:
    return "sqlite:///" + str(path).replace("\\", "/")


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(_sqlite_url(tmp_path / "learn_signal.db"), connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


def _count(session: Session, model) -> int:
    return len(session.scalars(select(model)).all())


def _events_for_signal(session: Session, signal_id: str) -> list[AgentEvent]:
    all_events = session.scalars(select(AgentEvent)).all()
    matching = [e for e in all_events if e.payload and e.payload.get("signal_id") == signal_id]
    return sorted(matching, key=lambda e: e.timestamp)


# --------------------------------------------------------------------- 1 ---


def test_learn_signal_real_end_to_end_reaches_validation_required(session: Session) -> None:
    """Fluxo completo real: busca real + comparação real via Gemini."""
    signal = learn_signal(session, "computador")

    assert signal.status == "VALIDATION_REQUIRED"

    events = _events_for_signal(session, signal.id)
    event_types = [e.event_type for e in events]
    for required in ("candidate_created", "research_started", "research_completed", "validation_requested"):
        assert required in event_types, f"evento {required!r} não encontrado: {event_types}"
    idx = {t: event_types.index(t) for t in event_types}
    assert (
        idx["candidate_created"] < idx["research_started"] < idx["research_completed"] < idx["validation_requested"]
    ), f"ordem errada: {event_types}"

    research_completed = next(e for e in events if e.event_type == "research_completed")
    print(f"\n[Ciclo 5] classificação real do Gemini: {research_completed.payload}")
    assert research_completed.payload["classification"] in {"MATCH", "VARIATION", "CONFLICT", "UNKNOWN"}
    assert 0.0 <= research_completed.payload["confidence"] <= 1.0
    assert research_completed.payload["reasoning"]

    links = session.scalars(select(SignalSource).where(SignalSource.signal_id == signal.id)).all()
    sources_count = research_completed.payload["sources_count"]
    if sources_count > 0:
        assert links, "research_completed reportou sources_count > 0 mas nenhum SignalSource foi gravado"
        assert len(links) == sources_count
    else:
        # busca real genuinamente não achou nada -- caso legítimo, não assumido.
        assert not links


# --------------------------------------------------------------------- 2 ---


def test_learn_signal_search_failure_marks_signal_failed(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Falha real de busca -> `WebSearchError` re-levantada E `Signal` em FAILED no banco."""

    def _boom(self, query, **kwargs):
        raise DDGSException("simulado: backend indisponível nesta rede")

    monkeypatch.setattr(RealDDGS, "text", _boom)

    concept = "sinal_que_vai_falhar_na_busca_ciclo5"
    with pytest.raises(WebSearchError):
        learn_signal(session, concept)

    failed_signal = session.scalars(select(Signal).where(Signal.concept == concept)).first()
    assert failed_signal is not None, "Signal nem chegou a ser criado no banco"
    assert failed_signal.status == "FAILED"

    error_events = [e for e in _events_for_signal(session, failed_signal.id) if e.event_type == "error"]
    assert len(error_events) == 1, f"esperado 1 AgentEvent(error), achou {len(error_events)}"
    assert error_events[0].payload["stage"] == "search"
    assert "simulado" in error_events[0].payload["error"]


def test_learn_signal_register_sources_failure_marks_signal_failed(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Falha ao registrar/vincular fontes (não busca, não comparação) também marca FAILED.

    Achado na revisão do Ciclo 5: o estágio de registro/vínculo de fontes
    (`register_sources_from_search` + `_link_sources`) não estava protegido
    pelo mesmo `try/except` que os estágios "search" e "compare" já tinham —
    uma falha ali deixava o `Signal` preso em ANALYZING sem
    `AgentEvent(error)` nenhum. Corrigido; este teste falha se a proteção
    for removida de novo (comprovado por reversão manual antes de aplicar
    o fix — ver relatório do merge).
    """
    monkeypatch.setattr(learn_signal_module, "search_web", lambda concept, max_results=5: [])

    def _boom(session, results, **kwargs):
        raise RuntimeError("simulado: falha ao gravar Source")

    monkeypatch.setattr(learn_signal_module, "register_sources_from_search", _boom)

    concept = "sinal_que_vai_falhar_no_registro_ciclo5"
    with pytest.raises(RuntimeError):
        learn_signal(session, concept)

    failed_signal = session.scalars(select(Signal).where(Signal.concept == concept)).first()
    assert failed_signal is not None, "Signal nem chegou a ser criado no banco"
    assert failed_signal.status == "FAILED"

    error_events = [e for e in _events_for_signal(session, failed_signal.id) if e.event_type == "error"]
    assert len(error_events) == 1, f"esperado 1 AgentEvent(error), achou {len(error_events)}"
    assert error_events[0].payload["stage"] == "register_sources"
    assert "simulado" in error_events[0].payload["error"]


# --------------------------------------------------------------------- 3 ---


def test_learn_signal_dedups_signal_source_across_calls(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Duas chamadas (dois `Signal` novos) reaproveitando os mesmos `Source` -> vínculos corretos, sem vazar.

    `compare_sources` é mockado aqui -- ver docstring do módulo (quota diária
    do Gemini free tier esgotada durante a verificação; o que este teste
    prova é o vínculo `SignalSource`, ortogonal ao resultado da
    classificação, já provado real no teste 1).
    """
    real_results = search_web("dicionário Libras ESCOLA", max_results=5)
    assert real_results, "busca real não trouxe nenhum resultado -- nada pra provar dedup"

    # reaproveita a MESMA lista real nas duas chamadas -- ver docstring do módulo.
    monkeypatch.setattr(learn_signal_module, "search_web", lambda concept, max_results=5: real_results)
    fixed_comparison = SourceComparison(
        classification="UNKNOWN", confidence=0.0, reasoning="compare_sources mockado neste teste -- ver docstring"
    )
    monkeypatch.setattr(learn_signal_module, "compare_sources", lambda concept, sources: fixed_comparison)

    signal_1 = learn_signal(session, "escola_dedup_ciclo5_1")
    signal_2 = learn_signal(session, "escola_dedup_ciclo5_2")

    unique_urls = {r.url for r in real_results if r.url}
    assert _count(session, Source) == len(unique_urls), "Source duplicada entre os dois Signal"

    links_1 = session.scalars(select(SignalSource).where(SignalSource.signal_id == signal_1.id)).all()
    links_2 = session.scalars(select(SignalSource).where(SignalSource.signal_id == signal_2.id)).all()

    assert links_1, "primeiro Signal não ficou vinculado a nenhuma fonte"
    assert links_2, "segundo Signal não ficou vinculado a nenhuma fonte"

    source_ids_1 = {l.source_id for l in links_1}
    source_ids_2 = {l.source_id for l in links_2}
    assert len(links_1) == len(source_ids_1), "vínculo duplicado dentro do próprio Signal 1"
    assert len(links_2) == len(source_ids_2), "vínculo duplicado dentro do próprio Signal 2"
    assert source_ids_1 == source_ids_2, "os dois Signal (mesma busca) deveriam apontar pras mesmas Source"

    # nenhum vínculo vazou pro Signal errado.
    signal_ids_seen = {l.signal_id for l in links_1} | {l.signal_id for l in links_2}
    assert signal_ids_seen == {signal_1.id, signal_2.id}
