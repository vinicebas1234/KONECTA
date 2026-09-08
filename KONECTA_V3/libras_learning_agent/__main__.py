"""Permite `python -m libras_learning_agent`.

Ciclo 0: inicializava só config + logging + banco. Ciclo 6: sobe de verdade a
API HTTP isolada (`api/app.py`) via uvicorn, na porta própria do LLA
(`settings.api_port`, padrão 8010) — nunca a mesma porta de app_backend/
vision_lab. É o requisito da spec original: "o Agent deve poder ser
executado separadamente".
"""

from __future__ import annotations

import uvicorn

from libras_learning_agent.core.config import get_settings
from libras_learning_agent.core.logging_setup import configure_logging
from libras_learning_agent.database.db import init_db


def main() -> None:
    settings = get_settings()
    logger = configure_logging(settings)
    logger.info("fundação iniciando", extra={"event": "foundation_startup"})

    init_db(settings)
    logger.info("banco inicializado", extra={"event": "foundation_db_ready"})

    logger.info(
        "subindo API HTTP",
        extra={"event": "api_startup", "port": settings.api_port},
    )
    # host="127.0.0.1" (não "0.0.0.0") de propósito: a API não tem autenticação
    # nenhuma (dispara pesquisa que gasta cota do Gemini, aprova/rejeita
    # candidatos) — expor pra rede local por padrão seria um risco desnecessário
    # pra uma ferramenta de pesquisa local.
    uvicorn.run("libras_learning_agent.api.app:app", host="127.0.0.1", port=settings.api_port)


if __name__ == "__main__":
    main()
