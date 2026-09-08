"""Ciclo 3 do Libras Learning Agent: pesquisa web gratuita (sem API key, sem custo por busca).

`web_search.search_web` busca de verdade via `ddgs`; `source_registry.register_sources_from_search`
grava os achados como `Source` no banco, deduplicados por `url`. Sem IA, sem
chamada à API da Anthropic/Claude — isso é escopo de um ciclo futuro que vai
LER o que este grava.
"""

from libras_learning_agent.research.source_registry import register_sources_from_search
from libras_learning_agent.research.web_search import SearchResult, WebSearchError, search_web

__all__ = [
    "SearchResult",
    "WebSearchError",
    "register_sources_from_search",
    "search_web",
]
