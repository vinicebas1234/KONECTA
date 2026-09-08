"""Testes reais do Ciclo 4 (comparação de fontes via Gemini) do Libras Learning Agent.

Mesmo espírito de `test_web_search.py`: chamadas reais (busca real via
`search_web`, comparação real via `compare_sources`, sem mock da API do
Gemini). Os únicos dois usos de `monkeypatch` no arquivo inteiro são para
provar comportamento negativo/estrutural que não dá pra provar com uma
chamada real:

- `test_compare_sources_empty_sources_skips_api_call`: prova que lista vazia
  não instancia `genai.Client` (economiza a chamada), fazendo
  `genai.Client` explodir se for chamado.
- `test_to_comparison_rejects_hallucinated_classification` nem usa
  monkeypatch — chama `_to_comparison` (função pura) direto com uma
  `_GeminiResponseSchema` construída à mão simulando o Gemini alucinando um
  5º valor, sem precisar simular a API de verdade.

Precisa de `GEMINI_API_KEY` configurada no ambiente (real, tier gratuito) —
ver `core/config.py`.
"""

from __future__ import annotations

import importlib

import pytest

# `research/__init__.py` faz `from .compare_sources import compare_sources`, o que
# reaproveita o mesmo nome `compare_sources` para o submódulo e para a função —
# `import ... as` via atributo pegaria a função (o último a vencer o nome), não o
# submódulo. `importlib.import_module` busca o módulo direto em `sys.modules`,
# sem passar pelo atributo do pacote, então pega o submódulo de verdade.
compare_sources_module = importlib.import_module("libras_learning_agent.research.compare_sources")

from libras_learning_agent.core.config import get_settings
from libras_learning_agent.database.models import Source
from libras_learning_agent.research.compare_sources import (
    CLASSIFICATIONS,
    SourceComparisonError,
    _GeminiResponseSchema,
    _to_comparison,
    compare_sources,
)
from libras_learning_agent.research.web_search import search_web

pytestmark = pytest.mark.skipif(
    not get_settings().gemini_api_key,
    reason="GEMINI_API_KEY não configurada no ambiente — ver instruções do Ciclo 4",
)


# --------------------------------------------------------------------- 1 ---


def test_compare_sources_real_end_to_end() -> None:
    """Busca real (Ciclo 3) + comparação real (Ciclo 4), sem mock de nenhum dos dois."""
    results = search_web("dicionário Libras COMPUTADOR", max_results=5)
    assert results, "busca real não trouxe nenhum resultado — nada pra comparar"

    sources = [
        Source(url=r.url or None, title=r.title or None, usage_notes=r.snippet or None)
        for r in results
    ]

    comparison = compare_sources("computador", sources)

    assert comparison.classification in CLASSIFICATIONS
    assert 0.0 <= comparison.confidence <= 1.0
    assert comparison.reasoning
    assert isinstance(comparison.variants_mentioned, list)
    assert isinstance(comparison.conflicts_mentioned, list)


# --------------------------------------------------------------------- 2 ---


def test_compare_sources_empty_sources_skips_api_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lista de sources vazia devolve UNKNOWN sem gastar uma chamada de API."""

    def _boom_client(*args, **kwargs):
        raise AssertionError("genai.Client não deveria ser instanciado para lista de sources vazia")

    monkeypatch.setattr(compare_sources_module.genai, "Client", _boom_client)

    comparison = compare_sources("sinal_que_nao_existe_xyz", [])

    assert comparison.classification == "UNKNOWN"
    assert comparison.confidence == 0.0
    assert "sinal_que_nao_existe_xyz" in comparison.reasoning
    assert comparison.variants_mentioned == []
    assert comparison.conflicts_mentioned == []


# --------------------------------------------------------------------- 3 ---


def test_compare_sources_raises_on_invalid_api_key() -> None:
    """Chave inválida gera falha real de auth na API do Gemini -> `SourceComparisonError`, nunca um resultado fabricado.

    `api_key` é passado explicitamente (instância própria do client) — a
    `GEMINI_API_KEY` real do processo não é tocada.
    """
    sources = [Source(url="https://example.com", title="t", usage_notes="trecho qualquer")]

    with pytest.raises(SourceComparisonError):
        compare_sources("computador", sources, api_key="chave-invalida-de-teste-123")


# --------------------------------------------------------------------- 4 ---


def test_to_comparison_rejects_hallucinated_classification() -> None:
    """Uma classification fora de `CLASSIFICATIONS` (Gemini alucinando um 5º valor) vira erro, nunca passa batido."""
    parsed = _GeminiResponseSchema(classification="MAYBE", confidence=0.5, reasoning="alucinação simulada")

    with pytest.raises(SourceComparisonError):
        _to_comparison(parsed)


def test_to_comparison_rejects_confidence_out_of_range() -> None:
    """Mesma ideia para `confidence` fora de [0.0, 1.0] — também não pode passar batido."""
    parsed = _GeminiResponseSchema(classification="MATCH", confidence=1.5, reasoning="fora do intervalo")

    with pytest.raises(SourceComparisonError):
        _to_comparison(parsed)
