"""Pesquisa e comparação de fontes do Libras Learning Agent.

Ciclo 3 (pesquisa web, sem IA, sem API key): `web_search.search_web` busca de
verdade via `ddgs`; `source_registry.register_sources_from_search` grava os
achados como `Source` no banco, deduplicados por `url`.

Ciclo 4 (comparação de fontes via Gemini, tier gratuito): `compare_sources`
classifica a relação entre `Source` já registrados (MATCH/VARIATION/
CONFLICT/UNKNOWN) — nunca decide promoção/validação, isso é humano. Sem
chamada à API da Anthropic/Claude em nenhum dos dois ciclos.
"""

from libras_learning_agent.research.compare_sources import (
    CLASSIFICATIONS,
    SourceComparison,
    SourceComparisonError,
    compare_sources,
)
from libras_learning_agent.research.source_registry import register_sources_from_search
from libras_learning_agent.research.web_search import SearchResult, WebSearchError, search_web

__all__ = [
    "CLASSIFICATIONS",
    "SearchResult",
    "SourceComparison",
    "SourceComparisonError",
    "WebSearchError",
    "compare_sources",
    "register_sources_from_search",
    "search_web",
]
