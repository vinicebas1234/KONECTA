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

Ciclo 12 (cache + erro de cota diferenciado), seção final do arquivo: os
testes de cache tentam SEMPRE uma primeira chamada real primeiro. Se a cota
diária (20/dia/modelo) já estiver esgotada no momento da execução — situação
comum neste projeto, ver `research/compare_sources.py` — a própria
`QuotaExceededError` real é capturada e só ENTÃO a primeira resposta é
simulada (documentado em cada teste) só para poder popular o cache e provar
a mecânica da SEGUNDA chamada, que é o que estes testes realmente verificam.
Os testes de chave/TTL puros (sem precisar de API key) ficam em
`test_compare_cache.py`, não duplicados aqui.
"""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from google import genai as real_genai
from google.genai import errors as genai_errors

# `research/__init__.py` faz `from .compare_sources import compare_sources`, o que
# reaproveita o mesmo nome `compare_sources` para o submódulo e para a função —
# `import ... as` via atributo pegaria a função (o último a vencer o nome), não o
# submódulo. `importlib.import_module` busca o módulo direto em `sys.modules`,
# sem passar pelo atributo do pacote, então pega o submódulo de verdade.
compare_sources_module = importlib.import_module("libras_learning_agent.research.compare_sources")

from libras_learning_agent.core.config import get_settings
from libras_learning_agent.database.models import Source
from libras_learning_agent.research import cache as cache_module
from libras_learning_agent.research.compare_sources import (
    CLASSIFICATIONS,
    QuotaExceededError,
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


# --------------------------------------------------------------------- Ciclo 12: cache + cota ---


def _isolated_cache_settings(tmp_path: Path, *, ttl_days: int = 7) -> SimpleNamespace:
    return SimpleNamespace(data_dir=str(tmp_path), compare_cache_ttl_days=ttl_days)


def _fake_successful_response(monkeypatch: pytest.MonkeyPatch, *, reasoning: str) -> None:
    """Só usado quando a PRIMEIRA tentativa real deu `QuotaExceededError` (cota já
    esgotada no momento da execução) — simula uma resposta bem-sucedida do Gemini
    só para poder popular o cache e testar a mecânica da segunda chamada, que é o
    que estes testes de verdade verificam. Nunca usado para o teste de detecção de
    cota em si (esse usa o 429 real quando ele está disponível).
    """
    fake_parsed = _GeminiResponseSchema(
        classification="MATCH", confidence=0.8, reasoning=reasoning, variants_mentioned=[], conflicts_mentioned=[]
    )
    fake_response = SimpleNamespace(parsed=fake_parsed, text="{}")
    fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: fake_response))
    monkeypatch.setattr(compare_sources_module.genai, "Client", lambda api_key: fake_client)


def test_compare_sources_cache_hit_skips_second_api_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A SEGUNDA chamada com o MESMO concept+sources não pode instanciar `genai.Client`
    de novo — prova real de que veio do cache, não de uma resposta parecida por acaso.
    """
    monkeypatch.setattr(cache_module, "get_settings", lambda: _isolated_cache_settings(tmp_path))
    sources = [
        Source(
            id="uuid-cache-hit-1",
            url="https://exemplo.com/libras-computador",
            title="Dicionário Libras: computador",
            usage_notes="Sinal de computador em Libras, exemplo de trecho.",
        )
    ]
    concept = "computador_cache_hit_ciclo12"

    try:
        first = compare_sources(concept, sources)  # tentativa real — gasta 1 de cota se houver.
    except QuotaExceededError:
        # Cota já esgotada nesta execução (confirmado com 429 real durante o
        # desenvolvimento deste ciclo) — simula só esta primeira resposta para
        # poder popular o cache e testar a segunda chamada de verdade.
        _fake_successful_response(monkeypatch, reasoning="simulado (cota esgotada no momento do teste)")
        first = compare_sources(concept, sources)

    assert first.classification in CLASSIFICATIONS

    def _boom_client(*args, **kwargs):
        raise AssertionError(
            "genai.Client não deveria ser instanciado na segunda chamada — deveria ter vindo do cache"
        )

    monkeypatch.setattr(compare_sources_module.genai, "Client", _boom_client)

    second = compare_sources(concept, sources)

    assert second == first


def test_compare_sources_ttl_expired_forces_new_real_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uma entrada de cache com `cached_at` manipulado para fora do TTL não pode
    "grudar" — a chamada seguinte tem que tentar a API de verdade de novo.
    """
    monkeypatch.setattr(cache_module, "get_settings", lambda: _isolated_cache_settings(tmp_path, ttl_days=7))
    sources = [
        Source(
            id="uuid-ttl-1",
            url="https://exemplo.com/libras-casa",
            title="Dicionário Libras: casa",
            usage_notes="Sinal de casa em Libras, exemplo de trecho.",
        )
    ]
    concept = "casa_ttl_ciclo12"

    try:
        compare_sources(concept, sources)
    except QuotaExceededError:
        _fake_successful_response(monkeypatch, reasoning="simulado (cota esgotada no momento do teste)")
        compare_sources(concept, sources)

    # Expira o cache manualmente: reescreve `cached_at` para 8 dias atrás (TTL é 7).
    cache_path = tmp_path / "compare_cache" / f"{cache_module.cache_key(concept, sources)}.json"
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    data["cached_at"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    cache_path.write_text(json.dumps(data), encoding="utf-8")

    # Restaura o `genai.Client` REAL (desfaz qualquer simulação acima) — a
    # próxima chamada TEM que tentar a rede de verdade porque o cache expirou.
    monkeypatch.setattr(compare_sources_module.genai, "Client", real_genai.Client)

    try:
        fresh = compare_sources(concept, sources)
    except QuotaExceededError as erro:
        # A própria exceção 429 já é a prova de que uma tentativa de rede real
        # aconteceu — um cache "grudento" jamais produziria um erro de API,
        # só devolveria (silenciosamente) o resultado antigo já teria .
        assert erro.is_quota_exceeded is True
        return

    assert fresh.classification in CLASSIFICATIONS


def test_quota_exceeded_error_detected_structurally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prova que um 429 de cota vira `QuotaExceededError` (`is_quota_exceeded=True`),
    detectado via `google.genai.errors.APIError.code`/`.status` — nunca parsing de
    string da mensagem de erro.

    Durante o desenvolvimento deste ciclo a cota REAL já estava esgotada (429
    RESOURCE_EXHAUSTED, quotaId=GenerateRequestsPerDayPerProjectPerModel-FreeTier,
    limit=20) — a chamada abaixo aproveita esse 429 de verdade quando ele
    acontece, sem monkeypatch nenhum de erro. Só cai no fallback (simula o MESMO
    tipo de exceção que o SDK real levanta, com `code`/`status` reais, nunca uma
    string fabricada) se a cota tiver espaço no momento em que este teste
    específico rodar.
    """
    monkeypatch.setattr(cache_module, "get_settings", lambda: _isolated_cache_settings(tmp_path))
    sources = [
        Source(
            id="uuid-quota-1",
            url="https://exemplo.com/libras-carro",
            title="Dicionário Libras: carro",
            usage_notes="Sinal de carro em Libras, exemplo de trecho.",
        )
    ]

    try:
        compare_sources("carro_quota_ciclo12", sources)
    except QuotaExceededError as erro:
        assert erro.is_quota_exceeded is True
        assert isinstance(erro, SourceComparisonError)
        return  # 429 real — cota de fato esgotada nesta execução.

    # Cota tinha espaço agora: simula o mesmo tipo de exceção estruturada
    # (`google.genai.errors.ClientError`, code=429, status=RESOURCE_EXHAUSTED)
    # que o SDK real levantaria, sem gastar as 20 chamadas do dia.
    def _boom(*args, **kwargs):
        raise genai_errors.ClientError(
            429, {"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota simulada (fallback deste teste)"}}
        )

    monkeypatch.setattr(
        compare_sources_module.genai,
        "Client",
        lambda api_key: SimpleNamespace(models=SimpleNamespace(generate_content=_boom)),
    )

    with pytest.raises(QuotaExceededError) as exc_info:
        compare_sources("carro_quota_ciclo12_simulado", sources)
    assert exc_info.value.is_quota_exceeded is True
