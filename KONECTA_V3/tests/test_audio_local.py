"""Testes do provider de audio -> texto.

Nenhum teste carrega o Whisper de verdade: o modelo e' substituido. O que se
verifica aqui e' o contrato e o comportamento nos casos ruins.
"""

import asyncio

import numpy as np
import pytest

from app_central.providers.audio_local import (
    DURACAO_MINIMA_S,
    TAXA_ESPERADA,
    AudioLocalWhisper,
)
from app_central.providers.base import AudioParaTextoProvider, ProviderIndisponivel


class _WhisperFalso:
    def __init__(self, texto="oi tudo bem", erro=None):
        self.texto = texto
        self.erro = erro
        self.chamadas = []

    def transcribe(self, amostras, **kwargs):
        if self.erro:
            raise self.erro
        self.chamadas.append({"n": len(amostras), "kwargs": kwargs})
        seg = type("S", (), {"text": self.texto})()
        return [seg], None


def _audio(segundos=1.0):
    return np.random.randn(int(TAXA_ESPERADA * segundos)).astype(np.float32) * 0.1


def _provider(whisper=None):
    p = AudioLocalWhisper()
    p._whisper = whisper if whisper is not None else _WhisperFalso()
    return p


def test_implementa_o_contrato():
    assert isinstance(AudioLocalWhisper(), AudioParaTextoProvider)


def test_transcreve_audio():
    p = _provider()
    r = asyncio.run(p.transcrever(_audio(), TAXA_ESPERADA))
    assert r.texto == "oi tudo bem"
    assert r.fonte == "whisper_local"
    assert r.latencia_ms >= 0


def test_taxa_errada_e_recusada():
    """44.1kHz num modelo de 16kHz produziria texto errado silenciosamente."""
    p = _provider()
    with pytest.raises(ProviderIndisponivel, match="16000"):
        asyncio.run(p.transcrever(_audio(), 44100))


def test_audio_curto_nao_roda_o_modelo():
    whisper = _WhisperFalso()
    p = _provider(whisper)
    curto = np.zeros(int(TAXA_ESPERADA * (DURACAO_MINIMA_S / 2)), dtype=np.float32)
    r = asyncio.run(p.transcrever(curto, TAXA_ESPERADA))
    assert r.texto == ""
    assert r.detalhes["status"] == "curto_demais"
    assert whisper.chamadas == [], "nao vale gastar CPU com ruido curto"


def test_falha_do_modelo_vira_erro_tratavel():
    p = _provider(_WhisperFalso(erro=RuntimeError("modelo explodiu")))
    with pytest.raises(ProviderIndisponivel):
        asyncio.run(p.transcrever(_audio(), TAXA_ESPERADA))


def test_silencio_devolve_texto_vazio_sem_erro():
    p = _provider(_WhisperFalso(texto=""))
    r = asyncio.run(p.transcrever(_audio(), TAXA_ESPERADA))
    assert r.texto == ""
    assert r.confianca == 0.0


def test_parametros_de_tempo_real():
    """beam pequeno e sem arrastar contexto: escolhas para latencia baixa."""
    whisper = _WhisperFalso()
    p = _provider(whisper)
    asyncio.run(p.transcrever(_audio(), TAXA_ESPERADA))
    kwargs = whisper.chamadas[0]["kwargs"]
    assert kwargs["beam_size"] == 1
    assert kwargs["condition_on_previous_text"] is False
    assert kwargs["language"] == "pt"


def test_audio_multicanal_e_achatado():
    p = _provider()
    estereo = np.random.randn(TAXA_ESPERADA, 1).astype(np.float32)
    r = asyncio.run(p.transcrever(estereo, TAXA_ESPERADA))
    assert r.texto == "oi tudo bem"


def test_nao_bloqueia_a_thread_do_loop():
    """A transcricao tem de sair do loop, senao trava o reconhecimento de Libras."""
    import threading

    thread_do_loop = []
    thread_do_modelo = []

    class _Espiao(_WhisperFalso):
        def transcribe(self, amostras, **kwargs):
            thread_do_modelo.append(threading.current_thread().name)
            return super().transcribe(amostras, **kwargs)

    p = _provider(_Espiao())

    async def _cenario():
        thread_do_loop.append(threading.current_thread().name)
        await p.transcrever(_audio(), TAXA_ESPERADA)

    asyncio.run(_cenario())
    assert thread_do_modelo[0] != thread_do_loop[0]


def test_encerrar_libera_modelo():
    p = _provider()
    asyncio.run(p.encerrar())
    assert p._whisper is None
