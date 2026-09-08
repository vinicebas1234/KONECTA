"""Testes reais do Ciclo 3 (pesquisa web) do Libras Learning Agent.

Mesmo padrão de `test_candidate_manager.py`: SQLite temporário real por
teste, sem mocks de banco. A única simulação aceita no arquivo inteiro é a
do teste 3 (`test_search_web_raises_on_backend_failure`), que troca só o
método de baixo nível da biblioteca `ddgs` por um que levanta erro — para
provar que uma falha de rede/backend vira `WebSearchError`, nunca uma lista
vazia disfarçada de sucesso. Os testes 1 e 2 fazem busca real na internet.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ddgs.ddgs import DDGS as RealDDGS  # classe real por trás do proxy lazy-load de `ddgs.DDGS` — ver comentário no teste 3
from ddgs.exceptions import DDGSException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from libras_learning_agent.database.db import Base
from libras_learning_agent.database.models import AgentEvent, Source
from libras_learning_agent.research.source_registry import register_sources_from_search
from libras_learning_agent.research.web_search import WebSearchError, search_web


def _sqlite_url(path: Path) -> str:
    return "sqlite:///" + str(path).replace("\\", "/")


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(_sqlite_url(tmp_path / "web_search.db"), connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


def _count(session: Session, model) -> int:
    return len(session.scalars(select(model)).all())


# --------------------------------------------------------------------- 1 ---


def test_search_web_returns_real_results() -> None:
    """Busca real (sem mock) — prova que `ddgs` funciona de verdade nesta rede."""
    results = search_web("dicionário Libras COMPUTADOR", max_results=5)

    assert len(results) >= 1
    first = results[0]
    assert first.title
    assert first.url.startswith("http"), f"url não parece uma URL de verdade: {first.url!r}"
    assert any(r.snippet for r in results), "nenhum resultado real trouxe snippet"


# --------------------------------------------------------------------- 2 ---


def test_register_sources_dedup_by_url(session: Session) -> None:
    """Registra a mesma busca duas vezes — prova (contando linhas) que não duplica."""
    results = search_web("dicionário Libras CASA", max_results=5)
    unique_urls = {r.url for r in results if r.url}
    assert unique_urls, "busca real não trouxe nenhuma URL — nada pra deduplicar"

    sources_before = _count(session, Source)
    events_before = _count(session, AgentEvent)

    first_pass = register_sources_from_search(session, results)

    assert _count(session, Source) - sources_before == len(unique_urls), "número de Source novas != URLs únicas"
    assert _count(session, AgentEvent) - events_before == len(unique_urls), "número de AgentEvent(source_found) != URLs únicas"

    sources_after_first = _count(session, Source)
    events_after_first = _count(session, AgentEvent)

    # registra os MESMOS resultados de novo: nada deve duplicar.
    second_pass = register_sources_from_search(session, results)

    assert _count(session, Source) == sources_after_first, "Source duplicada ao reprocessar a mesma busca"
    assert _count(session, AgentEvent) == events_after_first, "AgentEvent(source_found) duplicado para fonte reaproveitada"
    assert {s.id for s in second_pass} == {s.id for s in first_pass}, "segundo registro não reaproveitou os mesmos Source"


# --------------------------------------------------------------------- 3 ---


def test_search_web_raises_on_backend_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falha da biblioteca externa (rede/backend indisponível) vira `WebSearchError`, nunca `[]`.

    `ddgs.DDGS` (o nome que `web_search.py` importa) é na verdade um proxy
    com lazy-load (`_DDGSProxy`/`_ProxyMeta` em `ddgs/__init__.py`): a
    primeira chamada `DDGS()` troca a classe por `ddgs.ddgs.DDGS` (a real) e
    instancia ESSA. Por isso o monkeypatch precisa ir na classe real
    (`RealDDGS`, importada de `ddgs.ddgs`) — patchar o proxy não afeta a
    instância que `search_web` de fato usa.
    """

    def _boom(self, query, **kwargs):
        raise DDGSException("simulado: backend indisponível nesta rede")

    monkeypatch.setattr(RealDDGS, "text", _boom)

    with pytest.raises(WebSearchError):
        search_web("qualquer coisa", max_results=3)

    # query vazia é erro claro, não busca vazia disfarçada de "não achou nada".
    with pytest.raises(WebSearchError):
        search_web("   ")
