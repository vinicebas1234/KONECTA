"""WebSocket de analise: progresso em tempo real do Knowledge Engine.

Protocolo:
  cliente -> {"fonte": "v1_dinamicos" | "v1_estaticos" | "sintetico", "limite_sinais": int?}
  servidor -> {"tipo": "progresso", "mensagem": str}   (varias vezes)
  servidor -> {"tipo": "concluido", "analise": {...}}
  servidor -> {"tipo": "erro", "mensagem": str}
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.schemas import analise_para_dict
from backend.services import dataset_provider
from backend.services.analysis_service import service

router = APIRouter()

_FIM = object()


@router.websocket("/ws/analise")
async def ws_analise(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        pedido = await websocket.receive_json()
        fonte = pedido.get("fonte", "sintetico")
        limite_sinais = pedido.get("limite_sinais")

        if fonte not in dataset_provider.fontes_disponiveis():
            await websocket.send_json({"tipo": "erro", "mensagem": f"Fonte desconhecida: {fonte}"})
            return

        loop = asyncio.get_running_loop()
        fila: asyncio.Queue = asyncio.Queue()

        def on_progresso(mensagem: str) -> None:
            loop.call_soon_threadsafe(fila.put_nowait, mensagem)

        def executar():
            try:
                return service.analisar(fonte, limite_sinais, on_progresso)
            finally:
                loop.call_soon_threadsafe(fila.put_nowait, _FIM)

        tarefa = loop.run_in_executor(None, executar)

        while True:
            item = await fila.get()
            if item is _FIM:
                break
            await websocket.send_json({"tipo": "progresso", "mensagem": item})

        analise = await tarefa
        await websocket.send_json({
            "tipo": "concluido",
            "analise": analise_para_dict(analise, fonte=fonte),
        })
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 — erro reportado ao cliente
        try:
            await websocket.send_json({"tipo": "erro", "mensagem": str(exc)})
        except Exception:
            pass
