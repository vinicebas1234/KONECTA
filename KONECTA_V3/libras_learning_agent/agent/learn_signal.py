"""Ciclo 5 do Libras Learning Agent: fluxo `learn_signal` (o "Aprenda o sinal X" da spec).

Amarra o que os Ciclos 2-4 já resolveram — não reimplementa nada:
`candidate_manager` (máquina de estados + eventos), `web_search` (busca
real), `source_registry` (grava/dedup de `Source`), `compare_sources`
(classificação via Gemini). Cada um desses já faz seu próprio
`session.commit()`/`rollback()`; este módulo não empilha outra camada de
transação por cima — só adiciona a transação própria para o vínculo
`SignalSource`, que é a única coisa nova aqui.

Nome do módulo: "learn_signal", não "orchestrator"/"orquestrador" — esse
nome já nomeia outra coisa em `app_central/pipeline/recognizer_pipeline.py`.

Regra de ouro do projeto: o agente nunca decide sozinho. Mesmo com
classification=UNKNOWN e confidence baixa, o sinal sempre vai para
VALIDATION_REQUIRED — nunca vira rejeição automática.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from libras_learning_agent.agent.candidate_manager import advance_status, create_signal_candidate
from libras_learning_agent.database.models import Signal, SignalSource, Source
from libras_learning_agent.research.compare_sources import SourceComparisonError, compare_sources
from libras_learning_agent.research.source_registry import register_sources_from_search
from libras_learning_agent.research.web_search import WebSearchError, search_web


def _link_sources(session: Session, signal: Signal, sources: list[Source]) -> None:
    """Grava `SignalSource(signal, source)` para cada fonte, sem duplicar.

    Dedup por (signal_id, source_id) — cobre tanto uma `Source` repetida
    dentro da própria lista (URL duplicada dentro de uma busca) quanto rodar
    `learn_signal` de novo sobre o mesmo `Signal`. Transação própria (nenhuma
    das funções chamadas em `learn_signal` cuida deste vínculo).
    """
    try:
        for source in sources:
            existing = session.scalars(
                select(SignalSource).where(
                    SignalSource.signal_id == signal.id, SignalSource.source_id == source.id
                )
            ).first()
            if existing is not None:
                continue
            session.add(SignalSource(signal_id=signal.id, source_id=source.id))
            session.flush()  # visível pro dedup do próximo item do loop
        session.commit()
    except Exception:
        session.rollback()
        raise


def learn_signal(session: Session, concept: str, *, max_results: int = 5) -> Signal:
    """Pesquisa `concept`, registra fontes e deixa o `Signal` pronto para validação humana.

    Fluxo: DISCOVERED -> ANALYZING -> (busca + fontes + comparação) ->
    CANDIDATE -> VALIDATION_REQUIRED. Nunca decide promoção/rejeição sozinho
    — isso é sempre humano, fora do escopo daqui.

    Em falha de busca, de registro/vínculo de fontes ou de comparação, o
    `Signal` é movido para FAILED (com `AgentEvent(event_type="error")`
    registrando `stage` — "search"/"register_sources"/"compare" —
    e `error`) e a exceção original é sempre RE-LEVANTADA — a função nunca
    retorna silenciosamente em caminho de erro; quem chamou decide o que
    fazer a partir da exceção, e o `Signal` já está persistido em FAILED no
    banco (recuperável por `signal.id`, se necessário).
    """
    signal = create_signal_candidate(session, concept)
    advance_status(session, signal, "ANALYZING")

    try:
        results = search_web(concept, max_results=max_results)
    except WebSearchError as erro:
        advance_status(
            session, signal, "FAILED", event_type="error", payload={"stage": "search", "error": str(erro)}
        )
        raise

    try:
        sources = register_sources_from_search(session, results)
        _link_sources(session, signal, sources)
    except Exception as erro:
        advance_status(
            session,
            signal,
            "FAILED",
            event_type="error",
            payload={"stage": "register_sources", "error": str(erro)},
        )
        raise

    try:
        comparison = compare_sources(concept, sources)
    except SourceComparisonError as erro:
        advance_status(
            session, signal, "FAILED", event_type="error", payload={"stage": "compare", "error": str(erro)}
        )
        raise

    advance_status(
        session,
        signal,
        "CANDIDATE",
        event_type="research_completed",
        payload={
            "classification": comparison.classification,
            "confidence": comparison.confidence,
            "reasoning": comparison.reasoning,
            "sources_count": len(sources),
        },
    )
    advance_status(session, signal, "VALIDATION_REQUIRED")

    return signal
