"""Ciclo 2 do Libras Learning Agent: gestão de estado do sinal candidato.

Máquina de estados (`LEGAL_TRANSITIONS`) + log de eventos do agente
(`agent_events`). Ver `candidate_manager.py` para a tabela de transições e o
porquê de cada decisão. Sem IA, sem rede, sem vídeo neste ciclo — isso é
escopo de ciclos futuros, que vão chamar as funções daqui para persistir o
que encontrarem.
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

__all__ = [
    "IllegalTransitionError",
    "LEGAL_TRANSITIONS",
    "TERMINAL_STATUSES",
    "advance_status",
    "create_signal_candidate",
    "get_signal",
    "list_signals_by_status",
    "register_validation",
]
