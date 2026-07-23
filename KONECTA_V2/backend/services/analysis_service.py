"""Orquestracao das analises do Knowledge Engine para a API.

Mantem em memoria a ultima `AnaliseDataset` produzida, para que os endpoints
REST sirvam recortes dela sem reprocessar.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from core.types import AnaliseDataset
from knowledge import DatasetAnalyzer
from backend.dataset.manager import listar as carregar_amostras


class AnalysisService:
    def __init__(self) -> None:
        self._analise: AnaliseDataset | None = None
        self._fonte: str | None = None
        self._lock = threading.Lock()

    @property
    def analise(self) -> AnaliseDataset | None:
        return self._analise

    @property
    def fonte(self) -> str | None:
        return self._fonte

    def analisar(
        self,
        fonte: str = "sintetico",
        limite_sinais: int | None = None,
        on_progresso: Optional[Callable[[str], None]] = None,
    ) -> AnaliseDataset:
        with self._lock:
            if on_progresso:
                on_progresso(f"Carregando amostras da fonte '{fonte}'")
            amostras = carregar_amostras(fonte, limite_sinais, usar_cache=False)
            if on_progresso:
                on_progresso(f"{len(amostras)} amostras carregadas")
            analise = DatasetAnalyzer().analisar(amostras, on_progresso=on_progresso)
            self._analise = analise
            self._fonte = fonte
            return analise


# Singleton do processo — compartilhado entre REST e WebSocket.
service = AnalysisService()
