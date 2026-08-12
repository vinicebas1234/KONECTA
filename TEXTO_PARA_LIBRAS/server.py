"""Servidor do avatar VLibras: serve a página e repassa textos via WebSocket."""

import asyncio
from pathlib import Path
from typing import Literal, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

PORTA = 8300
ESTATICOS = Path(__file__).parent / "static"

app = FastAPI()
clientes: set[WebSocket] = set()
trava = asyncio.Lock()


@app.middleware("http")
async def sem_cache(requisicao, proxima):
    """Os arquivos vêm do disco ao lado; cachear só faz editar e não ver efeito."""
    resposta = await proxima(requisicao)
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


class Mensagem(BaseModel):
    """Contrato do serviço central do Konecta (transcricao_tempo_real.py)."""

    origem: Literal["audio", "libras"]
    tipo: Literal["parcial", "final"]
    texto: str
    latencia_s: Optional[float] = None


async def transmitir(texto: str, origem: Optional[WebSocket] = None) -> None:
    async with trava:
        destinos = [c for c in clientes if c is not origem]
    for destino in destinos:
        try:
            await destino.send_text(texto)
        except (WebSocketDisconnect, RuntimeError):
            async with trava:
                clientes.discard(destino)


@app.post("/publicar")
async def publicar(msg: Mensagem) -> dict:
    # Só as frases fechadas viram sinal: as parciais mudam a cada 0,6s e
    # interromperiam a animação do avatar antes de ela terminar.
    if msg.tipo == "final" and msg.texto.strip():
        await transmitir(msg.texto.strip())
    return {"ok": True}


@app.websocket("/ws")
async def websocket(sock: WebSocket) -> None:
    await sock.accept()
    async with trava:
        clientes.add(sock)
    try:
        while True:
            await transmitir(await sock.receive_text(), sock)
    except WebSocketDisconnect:
        pass
    finally:
        async with trava:
            clientes.discard(sock)


app.mount("/", StaticFiles(directory=ESTATICOS, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORTA)
