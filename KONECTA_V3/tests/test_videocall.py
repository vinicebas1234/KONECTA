"""Testes dos adaptadores de videochamada (ciclo 7).

Nenhum teste toca plataforma real: as chamadas HTTP sao interceptadas.
"""

import asyncio

import pytest

from app_central.videocall.adaptadores import (
    AdaptadorMeet,
    AdaptadorNulo,
    AdaptadorTeams,
    AdaptadorZoom,
    criar_adaptador,
)


class _RespostaFalsa:
    def __init__(self, status=200):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


class _SessaoFalsa:
    def __init__(self, status=200):
        self.status = status
        self.chamadas = []
        self.closed = False

    def post(self, url, data=None, headers=None):
        self.chamadas.append({"url": url, "data": data, "headers": headers})
        return _RespostaFalsa(self.status)

    async def close(self):
        self.closed = True


def _com_sessao(adaptador, sessao):
    async def _obter():
        return sessao

    adaptador._obter_sessao = _obter
    return adaptador


def test_zoom_envia_texto_utf8():
    a = _com_sessao(AdaptadorZoom(url_legenda="https://zoom.example/cc"), _SessaoFalsa())
    assert asyncio.run(a.enviar_legenda("olá surdo")) is True
    sessao = asyncio.run(a._obter_sessao())
    assert sessao.chamadas[0]["data"] == "olá surdo".encode("utf-8")
    assert "charset=utf-8" in sessao.chamadas[0]["headers"]["Content-Type"]


def test_zoom_incrementa_sequencia():
    """Zoom usa seq para ordenar; repetir numero faz legenda sumir."""
    sessao = _SessaoFalsa()
    a = _com_sessao(AdaptadorZoom(url_legenda="https://zoom.example/cc"), sessao)
    asyncio.run(a.enviar_legenda("um"))
    asyncio.run(a.enviar_legenda("dois"))
    assert "seq=0" in sessao.chamadas[0]["url"]
    assert "seq=1" in sessao.chamadas[1]["url"]


def test_zoom_preserva_query_existente():
    sessao = _SessaoFalsa()
    a = _com_sessao(AdaptadorZoom(url_legenda="https://zoom.example/cc?id=42"), sessao)
    asyncio.run(a.enviar_legenda("x"))
    assert "id=42" in sessao.chamadas[0]["url"]
    assert "&seq=0" in sessao.chamadas[0]["url"]


def test_teams_nao_mexe_na_url():
    sessao = _SessaoFalsa()
    a = _com_sessao(AdaptadorTeams(url_legenda="https://teams.example/cart"), sessao)
    asyncio.run(a.enviar_legenda("oi"))
    assert sessao.chamadas[0]["url"] == "https://teams.example/cart"


def test_erro_http_nao_derruba():
    """Falha de legenda degrada; a conversa continua."""
    a = _com_sessao(AdaptadorZoom(url_legenda="https://zoom.example/cc"), _SessaoFalsa(status=500))
    assert asyncio.run(a.enviar_legenda("oi")) is False


def test_sem_url_configurada_nao_tenta():
    sessao = _SessaoFalsa()
    a = _com_sessao(AdaptadorZoom(url_legenda=""), sessao)
    assert asyncio.run(a.enviar_legenda("oi")) is False
    assert sessao.chamadas == []


def test_texto_vazio_e_ignorado():
    sessao = _SessaoFalsa()
    a = _com_sessao(AdaptadorZoom(url_legenda="https://zoom.example/cc"), sessao)
    assert asyncio.run(a.enviar_legenda("   ")) is False
    assert sessao.chamadas == []


def test_meet_declara_a_limitacao():
    """Meet nao tem API de injecao: precisa dizer isso, nao fingir."""
    a = AdaptadorMeet()
    assert a.injecao_direta is False
    assert "não permite" in a.LIMITACAO


def test_meet_guarda_texto_mesmo_sem_qt():
    a = AdaptadorMeet()
    asyncio.run(a.enviar_legenda("frase para colar"))
    assert a.ultimo_texto == "frase para colar"


def test_adaptador_nulo_nunca_envia():
    assert asyncio.run(AdaptadorNulo().enviar_legenda("x")) is False


def test_fabrica_por_nome():
    assert isinstance(criar_adaptador("zoom", "http://x"), AdaptadorZoom)
    assert isinstance(criar_adaptador("TEAMS", "http://x"), AdaptadorTeams)
    assert isinstance(criar_adaptador("meet"), AdaptadorMeet)


def test_plataforma_desconhecida_nao_quebra():
    """Nova plataforma sem adaptador nao pode impedir o app de rodar."""
    assert isinstance(criar_adaptador("plataforma_do_futuro"), AdaptadorNulo)
    assert isinstance(criar_adaptador(""), AdaptadorNulo)


def test_nucleo_nao_precisa_saber_a_plataforma():
    """O contrato e' o mesmo para todos - e o ponto da §5."""
    for nome in ("zoom", "teams", "meet", "nenhum"):
        a = criar_adaptador(nome, "http://x")
        assert hasattr(a, "enviar_legenda")
        assert asyncio.iscoroutinefunction(a.enviar_legenda)
