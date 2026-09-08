"""Permite `python -m libras_learning_agent`.

Ciclo 0: só inicializa config + logging + banco. Pesquisa web, extração de
landmarks e treino são fases futuras.
"""

from __future__ import annotations

from libras_learning_agent.core.config import get_settings
from libras_learning_agent.core.logging_setup import configure_logging
from libras_learning_agent.database.db import init_db


def main() -> None:
    settings = get_settings()
    logger = configure_logging(settings)
    logger.info("fundação iniciando", extra={"event": "foundation_startup"})

    init_db(settings)
    logger.info("banco inicializado", extra={"event": "foundation_db_ready"})

    print("Libras Learning Agent — fundação OK. Fases de pesquisa/visão/treino ainda não implementadas.")


if __name__ == "__main__":
    main()
