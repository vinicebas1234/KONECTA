"""Testes reais do Ciclo 12 (cache local de `compare_sources`) do Libras Learning Agent.

Só testa `research/cache.py` diretamente (`cache_key`/`read_cached`/`write_cache`)
— sem tocar a API do Gemini, por isso, ao contrário de `test_compare_sources.py`,
não precisa de `GEMINI_API_KEY` nem gasta cota nenhuma. `read_cached`/`write_cache`
são funções reais de I/O em arquivo (não mockadas) contra um `tmp_path` isolado
por teste, via monkeypatch de `cache.get_settings` — nunca toca
`data/compare_cache/` do projeto de verdade.

A integração completa (cache evitando uma segunda chamada real de API, TTL
expirado forçando uma chamada nova) fica em `test_compare_sources.py`, que já
tem a infra/skip de `GEMINI_API_KEY`.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from libras_learning_agent.database.models import Source
from libras_learning_agent.research import cache as cache_module


def _settings(tmp_path: Path, *, ttl_days: int = 7) -> SimpleNamespace:
    return SimpleNamespace(data_dir=str(tmp_path), compare_cache_ttl_days=ttl_days)


@pytest.fixture(autouse=True)
def _isolated_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Toda função de `cache.py` lê `data_dir` via `get_settings()` — troca por um
    `tmp_path` isolado antes de cada teste, para nunca escrever no `data/compare_cache/`
    real do projeto (nem colidir entre testes rodando em paralelo).
    """
    monkeypatch.setattr(cache_module, "get_settings", lambda: _settings(tmp_path))


# --------------------------------------------------------------------- chave de cache ---


def test_cache_key_stable_for_same_concept_and_sources() -> None:
    """Mesma chamada (concept + sources) duas vezes seguidas -> mesma chave, sempre."""
    sources = [Source(id="uuid-a", url="https://a.com", title="A"), Source(id="uuid-b", url="https://b.com", title="B")]

    k1 = cache_module.cache_key("computador", sources)
    k2 = cache_module.cache_key("computador", sources)

    assert k1 == k2


def test_cache_key_ignores_source_order() -> None:
    """IDs são ordenados antes do hash — a ordem em que as fontes chegam não deveria importar."""
    a = Source(id="uuid-a", url="https://a.com", title="A")
    b = Source(id="uuid-b", url="https://b.com", title="B")

    assert cache_module.cache_key("computador", [a, b]) == cache_module.cache_key("computador", [b, a])


def test_cache_key_normalizes_concept_case_and_whitespace() -> None:
    """" Computador " e "computador" são o mesmo conceito pesquisado -> mesma chave."""
    sources = [Source(id="uuid-a", url="https://a.com", title="A")]

    assert cache_module.cache_key(" Computador ", sources) == cache_module.cache_key("computador", sources)


def test_cache_key_differs_for_different_concept() -> None:
    """Mesmo conjunto de fontes, concept diferente -> chave diferente (nunca colide)."""
    sources = [Source(id="uuid-a", url="https://a.com", title="A")]

    assert cache_module.cache_key("computador", sources) != cache_module.cache_key("casa", sources)


def test_cache_key_differs_for_different_source_set() -> None:
    """Mesmo concept, conjunto de fontes diferente -> chave diferente."""
    sources_1 = [Source(id="uuid-a", url="https://a.com", title="A")]
    sources_2 = [Source(id="uuid-c", url="https://c.com", title="C")]

    assert cache_module.cache_key("computador", sources_1) != cache_module.cache_key("computador", sources_2)


def test_cache_key_no_false_positive_same_content_different_ids() -> None:
    """Duas `Source` com EXATAMENTE o mesmo título/url/trecho mas `id` (UUID) diferente
    são, de fato, duas fontes diferentes no banco (ex. a mesma página cadastrada duas
    vezes por engano) — a chave não pode colapsar as duas em uma coincidência de cache.
    """
    same_content = dict(url="https://x.com", title="X", usage_notes="mesmo trecho")
    s1 = Source(id="uuid-x1", **same_content)
    s2 = Source(id="uuid-x2", **same_content)

    assert cache_module.cache_key("computador", [s1]) != cache_module.cache_key("computador", [s2])


# --------------------------------------------------------------------- read/write ---


def test_write_then_read_roundtrip() -> None:
    sources = [Source(id="uuid-a", url="https://a.com", title="A")]
    payload = {"classification": "MATCH", "confidence": 0.9, "reasoning": "ok", "variants_mentioned": [], "conflicts_mentioned": []}

    cache_module.write_cache("computador", sources, payload)

    assert cache_module.read_cached("computador", sources) == payload


def test_read_cached_missing_returns_none() -> None:
    sources = [Source(id="uuid-nunca-gravado", url="https://a.com", title="A")]

    assert cache_module.read_cached("conceito_nunca_cacheado", sources) is None


def test_read_cached_expired_returns_none_and_forces_recompute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Entrada gravada, mas com `cached_at` manipulado para fora do TTL -> cache-miss."""
    monkeypatch.setattr(cache_module, "get_settings", lambda: _settings(tmp_path, ttl_days=7))
    sources = [Source(id="uuid-a", url="https://a.com", title="A")]
    payload = {"classification": "MATCH", "confidence": 0.5, "reasoning": "x", "variants_mentioned": [], "conflicts_mentioned": []}
    cache_module.write_cache("computador", sources, payload)

    # Ainda dentro do TTL (7 dias) -> hit.
    assert cache_module.read_cached("computador", sources) == payload

    # Reescreve `cached_at` do próprio arquivo gravado para 8 dias atrás (fora do
    # TTL de 7 dias) -> deve virar cache-miss (None), forçando quem chama a
    # recalcular de verdade.
    path = tmp_path / "compare_cache" / f"{cache_module.cache_key('computador', sources)}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["cached_at"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    path.write_text(json.dumps(data), encoding="utf-8")

    assert cache_module.read_cached("computador", sources) is None


def test_read_cached_corrupted_file_returns_none_never_raises(tmp_path: Path) -> None:
    """Arquivo de cache corrompido (JSON inválido) nunca pode quebrar o fluxo real —
    vira cache-miss silencioso, não uma exceção.
    """
    sources = [Source(id="uuid-a", url="https://a.com", title="A")]
    path = tmp_path / "compare_cache" / f"{cache_module.cache_key('computador', sources)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ isso nao eh json valido", encoding="utf-8")

    assert cache_module.read_cached("computador", sources) is None
