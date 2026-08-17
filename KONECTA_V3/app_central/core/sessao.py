"""Estado da sessão em um lugar só (§12 da spec).

Antes, o estado vivia espalhado em atributos soltos da janela
(``is_running``, ``camera_worker``, ``pipeline``...). Isso torna impossível
responder com segurança a duas perguntas que a §11 exige mostrar ao usuário:
*a câmera está ligada agora?* e *o motor está respondendo?*

Aqui o estado é explícito e observável. Quem quiser reagir a mudanças registra
um ouvinte; a UI faz isso para acender os indicadores.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Estado(Enum):
    """Estados possíveis de um recurso, no vocabulário da §11."""

    DESLIGADO = "desligado"
    LIGANDO = "ligando"
    ATIVO = "ativo"
    ERRO = "erro"


class EstadoConexao(Enum):
    OFFLINE = "offline"
    CONECTANDO = "conectando"
    ONLINE = "online"


@dataclass
class Sessao:
    """Estado corrente da sessão de comunicação."""

    camera: Estado = Estado.DESLIGADO
    microfone: Estado = Estado.DESLIGADO
    conexao: EstadoConexao = EstadoConexao.OFFLINE
    motor_sinais: Estado = Estado.DESLIGADO
    motor_audio: Estado = Estado.DESLIGADO
    motor_texto_sinais: Estado = Estado.DESLIGADO
    ultimo_erro: Optional[str] = None
    frames_processados: int = 0
    frames_descartados: int = 0
    historico: List[str] = field(default_factory=list)

    def captando(self) -> bool:
        """Há captura ativa? É o que justifica avisar o usuário (§9)."""
        return Estado.ATIVO in (self.camera, self.microfone)


class GerenciadorSessao:
    """Guarda a sessão e avisa quem observa quando ela muda."""

    LIMITE_HISTORICO = 50

    def __init__(self):
        self._sessao = Sessao()
        self._lock = threading.Lock()
        self._ouvintes: List[Callable[[Sessao], None]] = []

    @property
    def sessao(self) -> Sessao:
        return self._sessao

    def observar(self, ouvinte: Callable[[Sessao], None]) -> None:
        self._ouvintes.append(ouvinte)

    def atualizar(self, **campos) -> None:
        """Aplica mudanças e notifica. Ignora campo desconhecido em vez de quebrar."""
        with self._lock:
            for nome, valor in campos.items():
                if hasattr(self._sessao, nome):
                    setattr(self._sessao, nome, valor)
                else:
                    logger.warning("Campo de sessão desconhecido: %s", nome)
        self._notificar()

    def registrar_erro(self, mensagem: str) -> None:
        self.atualizar(ultimo_erro=mensagem)

    def registrar_sinal(self, texto: str) -> None:
        if not texto:
            return
        with self._lock:
            self._sessao.historico.append(texto)
            if len(self._sessao.historico) > self.LIMITE_HISTORICO:
                del self._sessao.historico[: -self.LIMITE_HISTORICO]
            self._sessao.frames_processados += 1
        self._notificar()

    def desligar_tudo(self) -> None:
        """Corta câmera e microfone imediatamente (§9: desligamento imediato)."""
        self.atualizar(
            camera=Estado.DESLIGADO,
            microfone=Estado.DESLIGADO,
            motor_sinais=Estado.DESLIGADO,
            motor_audio=Estado.DESLIGADO,
        )
        logger.info("Captura desligada pelo usuário")

    def _notificar(self) -> None:
        for ouvinte in list(self._ouvintes):
            try:
                ouvinte(self._sessao)
            except Exception as erro:
                # um observador ruim não pode derrubar a sessão
                logger.error("Ouvinte de sessão falhou: %s", erro)


# Textos prontos para a UI (§11), para não espalhar emoji e string pelo código
SIMBOLOS: Dict[Estado, str] = {
    Estado.DESLIGADO: "🔴",
    Estado.LIGANDO: "🟡",
    Estado.ATIVO: "🟢",
    Estado.ERRO: "🔴",
}

SIMBOLOS_CONEXAO: Dict[EstadoConexao, str] = {
    EstadoConexao.OFFLINE: "🔴",
    EstadoConexao.CONECTANDO: "🟡",
    EstadoConexao.ONLINE: "🟢",
}


def rotulo(nome: str, estado: Estado) -> str:
    return f"{nome}: {SIMBOLOS[estado]} {estado.value.upper()}"
