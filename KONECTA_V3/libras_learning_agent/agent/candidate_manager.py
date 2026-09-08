"""Ciclo 2 do Libras Learning Agent: máquina de estados do sinal candidato.

Puro Python + banco (SQLAlchemy) — sem IA, sem rede, sem vídeo. Ciclos
futuros (pesquisa web, visão computacional em lote, treino) vão USAR
`advance_status`/`register_validation` daqui para persistir o que
encontrarem, em vez de escrever `signal.status = ...` direto.

Nome do módulo: "candidate_manager", não "orchestrator" — esse nome já
nomeia outra coisa em `app_central/pipeline/recognizer_pipeline.py` no
resto do projeto; evitar a confusão.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from libras_learning_agent.database.models import AgentEvent, Signal, Validation


class IllegalTransitionError(Exception):
    """Transição de status fora de `LEGAL_TRANSITIONS`. Nunca é silenciosa."""


# Estados terminais: nenhuma transição sai deles neste ciclo. Reabrir um
# sinal REJECTED/FAILED/ARCHIVED é decisão de ciclo futuro, não inventada aqui.
TERMINAL_STATUSES = frozenset({"REJECTED", "FAILED", "ARCHIVED"})

# Tabela de transições legais (fluxo da spec original + estados extra).
LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "DISCOVERED": frozenset({"ANALYZING", "FAILED"}),
    "ANALYZING": frozenset({"CANDIDATE", "FAILED"}),
    "CANDIDATE": frozenset({"VALIDATION_REQUIRED", "FAILED"}),
    # approved -> VALIDATED; rejected -> REJECTED (terminal); corrected e
    # needs_review -> volta pra CANDIDATE (precisa mais trabalho antes de
    # validar de novo). Espelha os 4 valores do CHECK de Validation.decision.
    "VALIDATION_REQUIRED": frozenset({"VALIDATED", "REJECTED", "CANDIDATE", "FAILED"}),
    "VALIDATED": frozenset({"TRAINING", "FAILED"}),
    "TRAINING": frozenset({"EVALUATED", "FAILED"}),
    # aprovado -> PRODUCTION; regressão detectada na avaliação -> REJECTED;
    # descartado sem promover -> ARCHIVED.
    "EVALUATED": frozenset({"PRODUCTION", "REJECTED", "ARCHIVED", "FAILED"}),
    # retirado/substituído -> ARCHIVED. Sem FAILED aqui: um modelo já em
    # produção não "falha em processar", é retirado por decisão (ARCHIVED).
    "PRODUCTION": frozenset({"ARCHIVED"}),
    "REJECTED": frozenset(),
    "FAILED": frozenset(),
    "ARCHIVED": frozenset(),
}

# decision (CHECK constraint de Validation) -> status de destino.
_VALIDATION_DECISION_TARGET = {
    "approved": "VALIDATED",
    "rejected": "REJECTED",
    "corrected": "CANDIDATE",
    "needs_review": "CANDIDATE",
}

# event_type default por transição (from, to): reaproveita os valores já
# documentados no comentário de AgentEvent, usando "<atividade>_completed"
# para a atividade que está encerrando (from) e "<atividade>_started" para a
# que está começando (to). "status_changed" é o fallback genérico onde não
# há match documentado bom (ex. PRODUCTION -> ARCHIVED); o chamador sempre
# pode passar `event_type` explícito para ser mais específico.
_DEFAULT_EVENT_TYPES: dict[tuple[str, str], str] = {
    ("DISCOVERED", "ANALYZING"): "research_started",
    ("ANALYZING", "CANDIDATE"): "research_completed",
    ("CANDIDATE", "VALIDATION_REQUIRED"): "validation_requested",
    ("VALIDATION_REQUIRED", "VALIDATED"): "validation_completed",
    ("VALIDATION_REQUIRED", "REJECTED"): "validation_completed",
    ("VALIDATION_REQUIRED", "CANDIDATE"): "validation_completed",
    ("VALIDATED", "TRAINING"): "training_started",
    ("TRAINING", "EVALUATED"): "training_completed",
    ("EVALUATED", "PRODUCTION"): "model_promoted",
    ("EVALUATED", "REJECTED"): "evaluation_completed",
    ("EVALUATED", "ARCHIVED"): "evaluation_completed",
    ("PRODUCTION", "ARCHIVED"): "status_changed",
}


def _default_event_type(from_status: str, to_status: str) -> str:
    # Qualquer transição para FAILED é "error", não precisa duplicar a
    # entrada pra cada (from, "FAILED") na tabela acima.
    if to_status == "FAILED":
        return "error"
    return _DEFAULT_EVENT_TYPES.get((from_status, to_status), "status_changed")


def advance_status(
    session: Session,
    signal: Signal,
    new_status: str,
    *,
    event_type: Optional[str] = None,
    payload: Optional[dict] = None,
) -> Signal:
    """Avança `signal.status` -> `new_status` se a transição for legal.

    Tudo em uma transação só: a legalidade é checada ANTES de qualquer
    `session.add`/mutação, então uma transição ilegal levanta
    `IllegalTransitionError` sem gravar nada (nem status novo, nem evento).
    """
    from_status = signal.status
    legal_targets = LEGAL_TRANSITIONS.get(from_status, frozenset())
    if new_status not in legal_targets:
        raise IllegalTransitionError(
            f"Transição ilegal: {from_status!r} -> {new_status!r}. "
            f"Destinos legais a partir de {from_status!r}: "
            f"{sorted(legal_targets) if legal_targets else '(nenhum, estado terminal)'}"
        )

    event_payload = {"signal_id": signal.id, "from_status": from_status, "to_status": new_status}
    if payload:
        event_payload.update(payload)

    signal.status = new_status
    session.add(signal)
    session.add(AgentEvent(event_type=event_type or _default_event_type(from_status, new_status), payload=event_payload))
    session.commit()
    session.refresh(signal)
    return signal


def create_signal_candidate(
    session: Session,
    concept: str,
    *,
    category: Optional[str] = None,
    description: Optional[str] = None,
) -> Signal:
    """Cria um `Signal` novo em DISCOVERED e grava o evento `candidate_created`.

    Caso especial fora de `advance_status`: é criação, não transição (não há
    `from_status` anterior) — mas grava evento do mesmo jeito, pra manter o
    log completo desde o início.
    """
    signal = Signal(concept=concept, category=category, description=description, status="DISCOVERED")
    session.add(signal)
    session.flush()  # popula signal.id (default client-side) sem commitar ainda

    session.add(
        AgentEvent(event_type="candidate_created", payload={"signal_id": signal.id, "concept": concept})
    )
    session.commit()
    session.refresh(signal)
    return signal


def register_validation(
    session: Session,
    signal: Signal,
    decision: str,
    validator: str,
    *,
    notes: Optional[str] = None,
) -> Validation:
    """Grava uma `Validation` e avança `signal.status` conforme `decision`.

    `decision` é validado em Python primeiro, com mensagem legível — não
    deixa o CHECK constraint do banco ser quem barra um valor inválido.

    Se `signal` não estiver no estado certo para essa `decision` (ex. sinal
    ainda em DISCOVERED e alguém chama decision="approved"), `advance_status`
    levanta `IllegalTransitionError`. Sem o `except` abaixo, o `Validation`
    já adicionado à sessão ficaria pendente (`session.new`) e vazaria pro
    banco no próximo `commit()` de quem chamou — uma linha "approved" sem
    a transição de status correspondente ter ocorrido de fato. `rollback()`
    desfaz esse `add` pendente antes de propagar o erro.
    """
    if decision not in _VALIDATION_DECISION_TARGET:
        raise ValueError(
            f"decision inválida: {decision!r}. Valores aceitos: {sorted(_VALIDATION_DECISION_TARGET)}"
        )

    validation = Validation(signal_id=signal.id, decision=decision, validator=validator, notes=notes)
    session.add(validation)

    target_status = _VALIDATION_DECISION_TARGET[decision]
    try:
        advance_status(
            session,
            signal,
            target_status,
            event_type="validation_completed",
            payload={"decision": decision, "validator": validator},
        )
    except IllegalTransitionError:
        session.rollback()
        raise
    session.refresh(validation)
    return validation


def get_signal(session: Session, signal_id: str) -> Optional[Signal]:
    return session.get(Signal, signal_id)


def list_signals_by_status(session: Session, status: str) -> list[Signal]:
    return list(session.scalars(select(Signal).where(Signal.status == status)))
