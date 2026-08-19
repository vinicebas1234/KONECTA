"""Testes da medicao de acuracia."""

from pathlib import Path

import pytest

from app_central.core.avaliacao import Avaliacao

VOCAB = ["pai", "mae", "filho", "filha", "cachorro"]


def _sessao(rodadas=10):
    return Avaliacao(vocabulario=list(VOCAB), rodadas_alvo=rodadas)


def test_distribui_alvos_igualmente():
    """Sorteio puro deixaria sinais sem amostra e o placar por sinal sem valor."""
    a = _sessao(rodadas=10)
    contagem = {nome: a._ordem.count(nome) for nome in VOCAB}
    assert sum(contagem.values()) == 10
    assert all(n == 2 for n in contagem.values()), contagem


def test_conta_acerto_e_erro():
    a = _sessao(rodadas=4)
    a.proximo_alvo()
    a.registrar(a.alvo_atual, 0.9, 1.0)          # acerto
    a.proximo_alvo()
    errado = next(s for s in VOCAB if s != a.alvo_atual)
    a.registrar(errado, 0.9, 1.0)                 # erro
    assert a.acertos == 1
    assert a.acuracia == pytest.approx(0.5)


def test_nada_reconhecido_conta_como_erro():
    a = _sessao(rodadas=2)
    a.proximo_alvo()
    a.registrar(None, 0.0, 3.0)
    assert a.acertos == 0
    assert a.rodadas[0].reconhecido is None


def test_placar_por_sinal():
    a = _sessao(rodadas=4)
    a.alvo_atual = "pai"
    a.registrar("pai", 0.9, 1.0)
    a.alvo_atual = "pai"
    a.registrar("mae", 0.9, 1.0)
    assert a.por_sinal()["pai"] == (1, 2)


def test_matriz_de_confusao():
    """Saber PARA ONDE o erro vai importa mais que a taxa: filho vira filha?"""
    a = _sessao(rodadas=6)
    for _ in range(3):
        a.alvo_atual = "filho"
        a.registrar("filha", 0.9, 1.0)
    a.alvo_atual = "pai"
    a.registrar("mae", 0.9, 1.0)
    confusoes = a.confusoes()
    assert confusoes[0] == ("filho", "filha", 3)


def test_termina_no_numero_de_rodadas():
    a = _sessao(rodadas=3)
    for _ in range(3):
        assert a.proximo_alvo() is not None
        a.registrar("x", 0.5, 1.0)
    assert a.terminou
    assert a.proximo_alvo() is None


def test_resumo_traz_acuracia_e_confusoes():
    a = _sessao(rodadas=2)
    a.alvo_atual = "pai"
    a.registrar("pai", 0.9, 1.0)
    a.alvo_atual = "filho"
    a.registrar("filha", 0.8, 1.0)
    resumo = a.resumo()
    assert "50%" in resumo
    assert "filho" in resumo and "filha" in resumo


def test_salva_csv_com_gabarito(tmp_path):
    """O CSV e' o que sustenta o numero no TCC."""
    a = _sessao(rodadas=2)
    a.alvo_atual = "pai"
    a.registrar("pai", 0.91, 1.5)
    a.alvo_atual = "mae"
    a.registrar("filha", 0.72, 2.0)
    caminho = a.salvar_csv(tmp_path)
    linhas = caminho.read_text(encoding="utf-8").strip().split("\n")
    assert linhas[0].startswith("alvo,reconhecido,acertou")
    assert len(linhas) == 3
    assert ",1," in linhas[1] and ",0," in linhas[2]


def test_vocabulario_vazio_nao_quebra():
    a = Avaliacao(vocabulario=[], rodadas_alvo=5)
    assert a.proximo_alvo() is None
    assert a.resumo() == "Nenhuma rodada registrada."
