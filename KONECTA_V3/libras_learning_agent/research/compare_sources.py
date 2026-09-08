"""Ciclo 4 do Libras Learning Agent: comparação de fontes via Google Gemini (tier gratuito).

Usa `google-genai` (`from google import genai`), o SDK Python oficial e
atualmente recomendado pela documentação do Gemini (sucessor do
`google-generativeai` mais antigo — ver `requirements.txt`), com o modelo
`gemini-3.5-flash` (Flash "Stable", listado como "Free of charge" em
ai.google.dev/gemini-api/docs/pricing em 2026-09-08). Os Flash mais novos
(`gemini-3.8-flash`, `gemini-3.6-flash`, e às vezes `gemini-3.7-flash`)
devolveram `503 UNAVAILABLE` ("high demand") de forma repetida durante a
verificação deste ciclo — `gemini-3.5-flash` foi o único que respondeu de
forma consistente em chamadas reais repetidas (3/3), por isso é o default
aqui. `gemini-2.5-flash` (o palpite antigo da spec) já devolve `404` — "no
longer available to new users" — confirmando que a família 2.x não é mais
o default gratuito em 2026. Nenhuma chamada à API
da Anthropic/Claude acontece neste módulo — decisão deliberada do dono do
projeto, ver `core/config.py` (`gemini_api_key`, separado de
`anthropic_api_key`).

Regra dura do projeto ("internet é evidência, não verdade"): este módulo só
CLASSIFICA o que as fontes dizem entre si (MATCH/VARIATION/CONFLICT/UNKNOWN);
nunca decide promoção/validação de um sinal — isso é humano, fora do escopo
daqui. Mesma regra de `web_search.py`: falha real de API/rede/parsing sempre
levanta `SourceComparisonError`, nunca vira um resultado fabricado — um
`UNKNOWN` só é válido quando o Gemini genuinamente respondeu isso (ou quando
não havia fonte nenhuma pra comparar), nunca como fallback de erro.

Controle de custo: só title/url/snippet de cada `Source` vão no prompt —
nunca o conteúdo bruto da página (que este projeto nem baixa).

Ciclo 12 (cache + erro de cota diferenciado): antes de qualquer chamada real,
`compare_sources` checa `research/cache.py` (arquivo local sob
`data_dir/compare_cache/`, TTL configurável via `Settings.compare_cache_ttl_days`)
— mesmo `concept` + mesmo conjunto de `sources` não gasta cota do tier
gratuito de novo. Uma falha 429 especificamente por cota esgotada (tier
gratuito: 20 chamadas/dia/modelo) levanta `QuotaExceededError` (subtipo de
`SourceComparisonError`), detectado via `google.genai.errors.APIError.code`/
`.status` (estruturado, nunca parsing de string da mensagem) — permite quem
chama (`learn_signal`, `POST /research`) diferenciar "cota acabou, tente
amanhã" de qualquer outra falha real de API/rede.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from libras_learning_agent.core.config import get_settings
from libras_learning_agent.database.models import Source
from libras_learning_agent.research.cache import read_cached, write_cache

# Vocabulário fixo do projeto para comparação de fontes — valor fora daqui é
# erro (`SourceComparisonError`), nunca aceito silenciosamente.
CLASSIFICATIONS = frozenset({"MATCH", "VARIATION", "CONFLICT", "UNKNOWN"})

# Flash estável e disponível no tier gratuito — ver docstring do módulo.
_MODEL = "gemini-3.5-flash"


class SourceComparisonError(Exception):
    """Falha real (API/rede/parsing) ao comparar fontes via Gemini.

    Nunca é engolida em silêncio para virar um `SourceComparison` fabricado
    — ver docstring do módulo.
    """

    is_quota_exceeded: bool = False


class QuotaExceededError(SourceComparisonError):
    """Cota diária do tier gratuito do Gemini esgotada (429 RESOURCE_EXHAUSTED).

    Subtipo de `SourceComparisonError` para quem só faz `except SourceComparisonError`
    continuar funcionando sem mudança — quem quer diferenciar "cota acabou" de
    qualquer outra falha checa `isinstance(erro, QuotaExceededError)` ou
    `erro.is_quota_exceeded`. Detecção via `google.genai.errors.APIError.code`/
    `.status` (ver `compare_sources`), nunca regex sobre a mensagem de erro.
    """

    is_quota_exceeded: bool = True


@dataclass
class SourceComparison:
    classification: str
    confidence: float
    reasoning: str
    variants_mentioned: list[str] = field(default_factory=list)
    conflicts_mentioned: list[str] = field(default_factory=list)


class _GeminiResponseSchema(BaseModel):
    """Schema de saída estruturada pedido ao Gemini (`response_schema`).

    `classification` fica `str` solto de propósito (não `Literal`/Enum): o
    schema JSON já orienta o Gemini a usar só os 4 valores do vocabulário
    (via prompt), mas a validação de verdade contra `CLASSIFICATIONS`
    acontece em Python logo abaixo, em `_to_comparison` — nunca confiamos
    só na conformidade do schema para pegar um 5º valor alucinado.
    """

    classification: str
    confidence: float
    reasoning: str
    variants_mentioned: list[str] = []
    conflicts_mentioned: list[str] = []


def _prompt(concept: str, sources: list[Source]) -> str:
    linhas = [
        f'Conceito/sinal de Libras sendo pesquisado: "{concept}"',
        "",
        "Fontes encontradas (resumo apenas — título, URL, trecho):",
    ]
    for i, s in enumerate(sources, start=1):
        linhas.append(f"{i}. título: {s.title or '(sem título)'}")
        linhas.append(f"   url: {s.url or '(sem url)'}")
        linhas.append(f"   trecho: {s.usage_notes or '(sem trecho)'}")
    linhas += [
        "",
        "Classifique a relação entre essas fontes sobre esse sinal/conceito em UMA destas 4 categorias:",
        "MATCH — as fontes concordam sobre o sinal.",
        "VARIATION — fontes descrevem variações legítimas (regional, estilo, contexto).",
        "CONFLICT — fontes se contradizem de forma que não parece variação.",
        "UNKNOWN — evidência insuficiente pra decidir.",
        "",
        "Importante: você está comparando o que as fontes DIZEM entre si, não decidindo sozinho "
        "se o sinal está correto — isso é validação humana, fora do seu papel aqui.",
        "",
        "Responda em JSON com os campos: classification (exatamente um dos 4 valores acima), "
        "confidence (número de 0.0 a 1.0), reasoning (texto curto explicando a decisão), "
        "variants_mentioned (lista de strings, pode ser vazia), "
        "conflicts_mentioned (lista de strings, pode ser vazia).",
    ]
    return "\n".join(linhas)


def _to_comparison(parsed: _GeminiResponseSchema) -> SourceComparison:
    """Valida a resposta estruturada do Gemini e monta o `SourceComparison`.

    Função pura (sem I/O) só para isolar a validação — permite testar o
    caso "Gemini alucinou uma 5ª classification" sem precisar simular a
    API, construindo `_GeminiResponseSchema` diretamente.
    """
    if parsed.classification not in CLASSIFICATIONS:
        raise SourceComparisonError(
            f"Gemini devolveu classification fora do vocabulário esperado: {parsed.classification!r}. "
            f"Esperado um de: {sorted(CLASSIFICATIONS)}"
        )
    if not (0.0 <= parsed.confidence <= 1.0):
        raise SourceComparisonError(
            f"Gemini devolveu confidence fora do intervalo [0.0, 1.0]: {parsed.confidence!r}"
        )

    return SourceComparison(
        classification=parsed.classification,
        confidence=parsed.confidence,
        reasoning=parsed.reasoning,
        variants_mentioned=list(parsed.variants_mentioned),
        conflicts_mentioned=list(parsed.conflicts_mentioned),
    )


def compare_sources(
    concept: str, sources: list[Source], *, api_key: Optional[str] = None
) -> SourceComparison:
    """Pede ao Gemini para classificar a relação entre `sources` sobre `concept`.

    `sources` vazia devolve `UNKNOWN` sem chamar a API (nada para comparar —
    economiza uma chamada à toa). Antes de qualquer chamada real, checa o
    cache local (`research/cache.py`) por `concept` + este exato conjunto de
    `sources`; só chama a API se não houver entrada válida (dentro do TTL).
    `api_key` sobrescreve `settings.gemini_api_key` (usado por testes para
    forçar uma chave inválida sem tocar a env var real do processo). Qualquer
    falha de API/rede/parsing levanta `SourceComparisonError` — nunca um
    resultado fabricado; 429 especificamente por cota esgotada levanta o
    subtipo `QuotaExceededError`.
    """
    if not sources:
        return SourceComparison(
            classification="UNKNOWN",
            confidence=0.0,
            reasoning=f"Nenhuma fonte encontrada para {concept!r} — nada para comparar.",
        )

    cached = read_cached(concept, sources)
    if cached is not None:
        return SourceComparison(**cached)

    key = api_key if api_key is not None else get_settings().gemini_api_key
    if not key:
        raise SourceComparisonError(
            "GEMINI_API_KEY não configurada (nem via parâmetro api_key, nem via env var/settings) "
            "— não é possível comparar fontes."
        )

    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=_MODEL,
            contents=_prompt(concept, sources),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_GeminiResponseSchema,
            ),
        )
    except genai_errors.APIError as erro:
        # Detecção estruturada (código HTTP + `status` da API, ambos campos
        # do SDK) — nunca parsing frágil da mensagem, que pode mudar de texto
        # a qualquer momento sem aviso. `code`/`status` vêm de
        # `google.genai.errors.APIError.__init__`, populados a partir do
        # corpo JSON real da resposta HTTP do Google.
        if erro.code == 429 or erro.status == "RESOURCE_EXHAUSTED":
            raise QuotaExceededError(
                f"Cota diária do Gemini (tier gratuito, 20 chamadas/dia/modelo) esgotada ao "
                f"comparar fontes de {concept!r}: {erro}"
            ) from erro
        raise SourceComparisonError(
            f"Falha ao chamar a API do Gemini para comparar fontes de {concept!r}: {erro}"
        ) from erro
    except Exception as erro:  # SDK externo: rede/auth podem falhar de outras formas
        raise SourceComparisonError(
            f"Falha ao chamar a API do Gemini para comparar fontes de {concept!r}: {erro}"
        ) from erro

    parsed = response.parsed
    if not isinstance(parsed, _GeminiResponseSchema):
        # `.parsed` não veio populado (resposta fora do schema) — tenta
        # parsear o JSON cru manualmente, com erro claro se vier mal formado.
        try:
            parsed = _GeminiResponseSchema.model_validate(json.loads(response.text))
        except Exception as erro:
            raise SourceComparisonError(
                f"Resposta do Gemini não pôde ser parseada como JSON válido: {response.text!r} ({erro})"
            ) from erro

    comparison = _to_comparison(parsed)
    write_cache(concept, sources, asdict(comparison))
    return comparison
