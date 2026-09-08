"""Ciclo 3 do Libras Learning Agent: grava `SearchResult` como `Source` no banco.

Segue o mesmo estilo de `agent/candidate_manager.py` (Ciclo 2): função pura
Python + banco, tudo numa transação, `try/except` com `session.rollback()`
para nunca deixar nada pendente na sessão se algo falhar no meio — mesma
lição do fix real do Ciclo 2 em `register_validation` (um `add` sem o
rollback correspondente vazaria pro banco no próximo `commit()` de quem
chamou).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from libras_learning_agent.database.models import AgentEvent, Source
from libras_learning_agent.research.web_search import SearchResult


def register_sources_from_search(
    session: Session,
    results: list[SearchResult],
    *,
    source_type: str = "web_search_result",
) -> list[Source]:
    """Grava cada `SearchResult` como `Source`, deduplicado por `url`.

    - `url` já existente no banco (ou repetida dentro da própria lista
      `results`) é reaproveitada: nenhuma linha nova, nenhum `AgentEvent`.
    - `url` nova gera uma linha `Source` + `AgentEvent(source_found)`.
    - `reliability_score` fica sempre `None` aqui de propósito: a busca em
      si não avalia confiabilidade ("internet = evidência, não verdade") —
      isso é curadoria humana/de um ciclo futuro.
    """
    sources: list[Source] = []
    try:
        for result in results:
            existing = None
            if result.url:
                existing = session.scalars(select(Source).where(Source.url == result.url)).first()
            if existing is not None:
                sources.append(existing)
                continue

            source = Source(
                url=result.url or None,
                title=result.title or None,
                source_type=source_type,
                retrieved_at=datetime.now(timezone.utc),
                usage_notes=result.snippet or None,
                reliability_score=None,
            )
            session.add(source)
            session.flush()  # popula source.id sem commitar ainda (e deixa a URL visível pro dedup do próximo item do loop)

            session.add(
                AgentEvent(
                    event_type="source_found",
                    payload={"source_id": source.id, "url": source.url, "title": source.title},
                )
            )
            sources.append(source)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return sources
