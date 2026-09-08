"""Libras Learning Agent (LLA) — subsistema do KONECTA_V3.

Agente que pesquisa sinais de Libras, extrai landmarks, valida com humanos e
treina modelos. Ciclo 0 entrega apenas a fundação: pacote, configuração,
banco de dados e logging. Pesquisa web, visão computacional e treino vêm em
fases futuras.

Isolamento: este subsistema nunca lê nem escreve em `KONECTA_V3/models/`
(auto-discovery de modelos de produção — ver `KONECTA_V3/models/LEIA-ME.md`).
Os próprios dados/modelos do agente vivem em `libras_learning_agent/`.
"""

__version__ = "0.1.0"
