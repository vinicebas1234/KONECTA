"""Ciclo 3 do Libras Learning Agent: busca web REAL, gratuita e sem API key.

Usa `ddgs` (sucessor mantido de `duckduckgo-search`, que foi congelado em
julho/2025 e não recebe mais correções contra bloqueio anti-bot — ver
`requirements.txt`). Sem cadastro, sem cartão, sem chave. Nenhuma chamada à
API da Anthropic/Claude acontece neste módulo nem no resto de `research/` —
comparação/curadoria via IA fica para um ciclo futuro que vai LER o que este
ciclo grava no banco (`source_registry.py`).

Regra dura: falha de rede/biblioteca sempre levanta `WebSearchError`, nunca
vira `[]` disfarçada de "não achou nada". Lista vazia só é um resultado
legítimo quando a busca de fato rodou e não encontrou nada.
"""

from __future__ import annotations

from dataclasses import dataclass

from ddgs import DDGS
from ddgs.exceptions import DDGSException


class WebSearchError(Exception):
    """Busca falhou de verdade (rede, rate limit, backend fora do ar, biblioteca).

    Nunca é engolida em silêncio para virar lista vazia — ver docstring do módulo.
    """


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def search_web(query: str, max_results: int = 5) -> list[SearchResult]:
    """Busca `query` na web via DuckDuckGo (gratuito, sem API key, sem mock).

    `[]` é devolvido só quando a busca rodou e genuinamente não achou nada.
    Qualquer falha de rede/biblioteca levanta `WebSearchError`.
    """
    if not query or not query.strip():
        raise WebSearchError("query vazia: nada para buscar")

    try:
        raw_results = DDGS().text(query, max_results=max_results)
    except DDGSException as erro:
        raise WebSearchError(f"Falha ao buscar {query!r} via DuckDuckGo (ddgs): {erro}") from erro
    except Exception as erro:  # biblioteca externa: rede/parsing podem falhar fora de DDGSException
        raise WebSearchError(f"Falha inesperada ao buscar {query!r} via DuckDuckGo (ddgs): {erro}") from erro

    return [
        SearchResult(title=r.get("title") or "", url=r.get("href") or "", snippet=r.get("body") or "")
        for r in raw_results
    ]
