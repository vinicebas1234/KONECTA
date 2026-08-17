"""Testes de config, credenciais, sessao e resiliencia (ciclos 3, 4 e 6)."""

import asyncio
import logging

import pytest

from app_central.core.config import Config, mascarar
from app_central.core.sessao import (
    Estado,
    EstadoConexao,
    GerenciadorSessao,
    rotulo,
)
from app_central.infra.resiliencia import (
    CircuitBreaker,
    CircuitoAberto,
    EstadoCircuito,
    com_retry,
    mensagem_amigavel,
)

# ---------------------------------------------------------------- config


def test_padrao_aponta_para_texto_para_libras():
    assert Config.carregar().texto_para_sinais.url == "http://127.0.0.1:8300"


def test_ambiente_sobrepoe_yaml(tmp_path, monkeypatch):
    arquivo = tmp_path / "c.yaml"
    arquivo.write_text("captura:\n  fps: 5\n", encoding="utf-8")
    assert Config.carregar(arquivo).captura.fps == 5
    monkeypatch.setenv("KONECTA_FPS", "24")
    assert Config.carregar(arquivo).captura.fps == 24


def test_config_invalida_nao_derruba(tmp_path):
    arquivo = tmp_path / "ruim.yaml"
    arquivo.write_text("isto: [nao fecha", encoding="utf-8")
    assert Config.carregar(arquivo).captura.fps == 15  # caiu no padrão


def test_config_ausente_nao_derruba(tmp_path):
    assert Config.carregar(tmp_path / "nao_existe.yaml").captura.fps == 15


def test_mascarar_nunca_revela_segredo():
    segredo = "sk-ant-api03-super-secreto-abcdef"
    saida = mascarar(segredo)
    assert segredo not in saida
    assert saida.startswith("sk-a")


def test_mascarar_segredo_curto_some_inteiro():
    assert mascarar("abc123") == "******"


def test_mascarar_ausente():
    assert mascarar(None) == "(não configurada)"


def test_credencial_nao_vaza_em_log(caplog, monkeypatch):
    """Regra da §8: token jamais aparece em log."""
    from app_central.core import config as mod

    monkeypatch.setenv("KONECTA_TESTE_SEGREDO", "valor-super-secreto-123")
    with caplog.at_level(logging.DEBUG):
        valor = mod.obter_credencial("teste_segredo")
    assert valor == "valor-super-secreto-123"
    assert "valor-super-secreto-123" not in caplog.text


# ---------------------------------------------------------------- sessao


def test_sessao_comeca_desligada():
    s = GerenciadorSessao().sessao
    assert s.camera is Estado.DESLIGADO
    assert s.conexao is EstadoConexao.OFFLINE
    assert not s.captando()


def test_observador_recebe_mudanca():
    g = GerenciadorSessao()
    vistos = []
    g.observar(lambda s: vistos.append(s.camera))
    g.atualizar(camera=Estado.ATIVO)
    assert vistos == [Estado.ATIVO]


def test_observador_quebrado_nao_derruba_sessao():
    g = GerenciadorSessao()
    g.observar(lambda _s: (_ for _ in ()).throw(RuntimeError("ops")))
    ok = []
    g.observar(lambda s: ok.append(s.camera))
    g.atualizar(camera=Estado.ATIVO)
    assert ok == [Estado.ATIVO]


def test_campo_desconhecido_e_ignorado():
    g = GerenciadorSessao()
    g.atualizar(nao_existe=1)  # não pode levantar


def test_desligar_tudo_corta_captura():
    g = GerenciadorSessao()
    g.atualizar(camera=Estado.ATIVO, microfone=Estado.ATIVO)
    assert g.sessao.captando()
    g.desligar_tudo()
    assert not g.sessao.captando()


def test_historico_tem_limite():
    g = GerenciadorSessao()
    for i in range(80):
        g.registrar_sinal(f"s{i}")
    assert len(g.sessao.historico) == g.LIMITE_HISTORICO
    assert g.sessao.historico[-1] == "s79"


def test_rotulo_mostra_estado():
    assert "🟢" in rotulo("CÂMERA", Estado.ATIVO)
    assert "🔴" in rotulo("CÂMERA", Estado.DESLIGADO)


# ---------------------------------------------------------------- resiliencia


def test_retry_ate_dar_certo():
    tentativas = []

    async def _op():
        tentativas.append(1)
        if len(tentativas) < 3:
            raise RuntimeError("ainda nao")
        return "ok"

    assert asyncio.run(com_retry(_op, tentativas=5, espera_inicial_s=0.001)) == "ok"
    assert len(tentativas) == 3


def test_retry_desiste_e_avisa():
    async def _op():
        raise RuntimeError("sempre falha")

    with pytest.raises(RuntimeError):
        asyncio.run(com_retry(_op, tentativas=2, espera_inicial_s=0.001))


def test_cancelamento_nao_e_repetido():
    """Cancelar e' intencao do chamador; repetir seria ignorar o usuario."""
    chamadas = []

    async def _op():
        chamadas.append(1)
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(com_retry(_op, tentativas=5, espera_inicial_s=0.001))
    assert len(chamadas) == 1


def test_circuito_abre_apos_falhas():
    b = CircuitBreaker("t", limite_falhas=3, espera_s=60)
    for _ in range(3):
        b.registrar_falha()
    assert b.estado is EstadoCircuito.ABERTO
    assert b.permitir() is False


def test_circuito_aberto_falha_na_hora():
    b = CircuitBreaker("t", limite_falhas=1, espera_s=60)
    b.registrar_falha()
    chamou = []

    async def _op():
        chamou.append(1)
        return "x"

    with pytest.raises(CircuitoAberto):
        asyncio.run(com_retry(_op, breaker=b))
    assert chamou == [], "circuito aberto nao pode tocar a rede"


def test_circuito_meio_aberto_deixa_testar():
    b = CircuitBreaker("t", limite_falhas=1, espera_s=0.01)
    b.registrar_falha()
    import time as _t

    _t.sleep(0.02)
    assert b.estado is EstadoCircuito.MEIO_ABERTO
    assert b.permitir() is True


def test_sucesso_fecha_circuito():
    b = CircuitBreaker("t", limite_falhas=2, espera_s=60)
    b.registrar_falha()
    b.registrar_sucesso()
    assert b.estado is EstadoCircuito.FECHADO


def test_mensagens_sao_amigaveis():
    """Nunca stack trace para o usuario (§14)."""
    assert "indisponível" in mensagem_amigavel(CircuitoAberto("x"))
    assert "demorando" in mensagem_amigavel(asyncio.TimeoutError())
    assert "conexão" in mensagem_amigavel(RuntimeError("connection refused"))
    assert "Credencial" in mensagem_amigavel(RuntimeError("unauthorized: api key"))
    for erro in (RuntimeError("boom"), ValueError("x"), CircuitoAberto("y")):
        assert "Traceback" not in mensagem_amigavel(erro)
