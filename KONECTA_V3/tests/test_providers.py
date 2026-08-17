"""Testes dos contratos de provider e da implementação local."""

import asyncio
from pathlib import Path

import numpy as np
import pytest

from app_central.providers import Motores, ProviderIndisponivel, ResultadoTexto
from app_central.providers.local_sinais import SEM_MAOS, SinaisLocais


class _ResultadoMotor:
    def __init__(self, signal, confidence=0.9, status="success"):
        self.signal = signal
        self.confidence = confidence
        self.latency_ms = 5.0
        self.status = status
        self.model_version = "v1"


class _MotorFalso:
    def __init__(self, resultado=None, erro=None):
        self._resultado = resultado
        self._erro = erro

    async def process(self, _frame):
        if self._erro:
            raise self._erro
        return self._resultado


def _frame():
    return np.zeros((48, 64, 3), dtype=np.uint8)


def test_reconhece_sinal():
    p = SinaisLocais()
    p._motor = _MotorFalso(_ResultadoMotor("OBRIGADO", 0.87))
    r = asyncio.run(p.reconhecer(_frame()))
    assert r.texto == "OBRIGADO"
    assert r.confianca == pytest.approx(0.87)
    assert r.fonte == "konecta_v3_local"


def test_sem_maos_nao_e_erro():
    """A maior parte dos frames de uma conversa nao tem sinal nenhum."""
    p = SinaisLocais()
    p._motor = _MotorFalso(_ResultadoMotor(SEM_MAOS, 0.0, status="no_input"))
    r = asyncio.run(p.reconhecer(_frame()))
    assert r.texto == ""
    assert r.confianca == 0.0


def test_falha_do_motor_vira_erro_tratavel():
    """O motor nao pode derrubar o app: vira ProviderIndisponivel (§14)."""
    p = SinaisLocais()
    p._motor = _MotorFalso(erro=RuntimeError("mediapipe explodiu"))
    with pytest.raises(ProviderIndisponivel):
        asyncio.run(p.reconhecer(_frame()))


def test_indisponivel_sem_modelo(tmp_path):
    """Sem modelo, o provider precisa admitir - senao o app finge funcionar."""
    p = SinaisLocais(caminho_modelo=str(tmp_path / "nao_existe"))
    assert asyncio.run(p.disponivel()) is False


def test_disponivel_com_modelo(tmp_path):
    pasta = tmp_path / "v1"
    pasta.mkdir()
    (pasta / "modelo.pkl").write_bytes(b"x")
    p = SinaisLocais(caminho_modelo=str(pasta))
    assert asyncio.run(p.disponivel()) is True


def test_modelo_atual_do_projeto_esta_ausente():
    """Documenta o estado real: models/ esta vazio, entao nao ha reconhecimento.

    Se alguem adicionar os modelos, este teste avisa que a situacao mudou.
    """
    raiz = Path(__file__).resolve().parent.parent
    p = SinaisLocais(caminho_modelo=str(raiz / "models" / "v1"))
    assert asyncio.run(p.disponivel()) is False, "models/v1 agora existe - atualize o plano"


def test_sequencia_usa_ultimo_frame():
    p = SinaisLocais()
    p._motor = _MotorFalso(_ResultadoMotor("AMOR"))
    r = asyncio.run(p.reconhecer_sequencia([_frame(), _frame()]))
    assert r.texto == "AMOR"


def test_sequencia_vazia_falha():
    p = SinaisLocais()
    with pytest.raises(ProviderIndisponivel):
        asyncio.run(p.reconhecer_sequencia([]))


def test_motores_ausentes_sao_estado_normal():
    """Ouvinte nao precisa do motor de Libras, e vice-versa."""
    m = Motores()
    assert m.sinais_para_texto is None
    asyncio.run(m.encerrar())  # nao pode explodir


def test_motores_encerra_os_presentes():
    encerrados = []

    class _P(SinaisLocais):
        async def encerrar(self):
            encerrados.append(self.nome)

    m = Motores(sinais_para_texto=_P())
    asyncio.run(m.encerrar())
    assert encerrados == ["konecta_v3_local"]
