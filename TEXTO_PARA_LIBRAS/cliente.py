"""Cliente: envia texto ao avatar VLibras pelo WebSocket."""

import asyncio

import websockets

URL = "ws://127.0.0.1:8300/ws"


class AvatarVLibras:
    def __init__(self, url: str = URL):
        self.url = url
        self._sock = None

    async def conectar(self) -> None:
        self._sock = await websockets.connect(self.url)

    async def falar(self, texto: str) -> None:
        if self._sock is None:
            await self.conectar()
        try:
            await self._sock.send(texto)
        except websockets.ConnectionClosed:
            await self.conectar()
            await self._sock.send(texto)

    async def fechar(self) -> None:
        if self._sock is not None:
            await self._sock.close()
            self._sock = None

    async def __aenter__(self) -> "AvatarVLibras":
        await self.conectar()
        return self

    async def __aexit__(self, *_) -> None:
        await self.fechar()


async def _main(frases: list[str]) -> None:
    async with AvatarVLibras() as avatar:
        for i, frase in enumerate(frases):
            print(f"enviando: {frase}")
            await avatar.falar(frase)
            if i < len(frases) - 1:
                await asyncio.sleep(5)


if __name__ == "__main__":
    import sys

    asyncio.run(_main(sys.argv[1:] or ["ola", "bom dia", "obrigado"]))
