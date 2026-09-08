"""Ciclo 12 do Libras Learning Agent: cache local de `compare_sources` (Gemini).

Por que arquivo, não tabela nova no banco: o cache é só get/set por chave +
checagem de timestamp — não precisa de índice relacional, join, nem
migration (comparar com `database/migrations/versions/0002_add_signal_sources.py`,
que existe porque `SignalSource` participa de queries relacionais de verdade).
Um JSON por entrada sob `settings.data_dir/compare_cache/` resolve o problema
com menos código e fica trivial de inspecionar manualmente (abrir o
`.json`) — ponytail: não força uma tabela onde um arquivo já resolve.

Chave de cache: sha256(concept normalizado + identificadores ordenados de
cada `Source`). O identificador de cada fonte é `source.id` (UUID4 atribuído
pelo banco em `register_sources_from_search` — colisão entre duas `Source`
diferentes é praticamente impossível) quando já persistido, ou o conteúdo da
fonte (`url`/`title`/`usage_notes`) quando `id` ainda é `None` (objeto criado
sem passar por sessão/flush — só acontece em teste direto, nunca no fluxo
real via `learn_signal`). Isso garante que duas comparações só reaproveitam
o mesmo cache se forem, de fato, o mesmo `concept` sobre o mesmo conjunto de
fontes — nunca um falso-positivo por coincidência de contagem/None.

Falha de cache (arquivo corrompido, campo faltando, timestamp inválido) nunca
quebra o fluxo real: é tratada como cache-miss, e `compare_sources` segue
para a chamada real de API.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from libras_learning_agent.core.config import get_settings
from libras_learning_agent.database.models import Source


def _cache_dir() -> Path:
    d = Path(get_settings().data_dir) / "compare_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _source_key(source: Source) -> str:
    return source.id or f"{source.url}|{source.title}|{source.usage_notes}"


def cache_key(concept: str, sources: list[Source]) -> str:
    """Chave estável para `concept` + o conjunto exato de `sources` — ver docstring do módulo."""
    normalized_concept = concept.strip().casefold()
    source_ids = sorted(_source_key(s) for s in sources)
    raw = json.dumps({"concept": normalized_concept, "sources": source_ids}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read_cached(concept: str, sources: list[Source]) -> Optional[dict[str, Any]]:
    """Devolve o payload de comparação em cache (dict pronto para `SourceComparison(**payload)`)
    se existir e ainda estiver dentro do TTL (`settings.compare_cache_ttl_days`), senão `None`.
    """
    path = _cache_dir() / f"{cache_key(concept, sources)}.json"
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data["cached_at"])
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return None

    ttl_seconds = get_settings().compare_cache_ttl_days * 86400
    age_seconds = (datetime.now(timezone.utc) - cached_at).total_seconds()
    if age_seconds > ttl_seconds:
        return None

    return data.get("comparison")


def write_cache(concept: str, sources: list[Source], comparison: dict[str, Any]) -> None:
    """Grava `comparison` (já serializado, ex. `dataclasses.asdict(SourceComparison(...))`) no cache."""
    path = _cache_dir() / f"{cache_key(concept, sources)}.json"
    data = {
        "concept": concept,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "comparison": comparison,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
