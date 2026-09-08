"""Ciclo 2 do Libras Learning Agent: gestão de estado do sinal candidato.

Máquina de estados (`LEGAL_TRANSITIONS`) + log de eventos do agente
(`agent_events`). Ver `candidate_manager.py` para a tabela de transições e o
porquê de cada decisão.

Ciclo 5 (`learn_signal.py`): amarra `candidate_manager` + `research/` num
fluxo só — "Aprenda o sinal X" da spec original. Ver docstring do módulo.
"""

from libras_learning_agent.agent.candidate_manager import (
    IllegalTransitionError,
    LEGAL_TRANSITIONS,
    TERMINAL_STATUSES,
    advance_status,
    create_signal_candidate,
    get_signal,
    list_signals_by_status,
    register_validation,
)
from libras_learning_agent.agent.learn_signal import learn_signal

__all__ = [
    "IllegalTransitionError",
    "LEGAL_TRANSITIONS",
    "TERMINAL_STATUSES",
    "advance_status",
    "create_signal_candidate",
    "get_signal",
    "learn_signal",
    "list_signals_by_status",
    "register_validation",
]
