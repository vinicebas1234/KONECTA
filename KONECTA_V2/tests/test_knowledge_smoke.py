"""Smoke test do Knowledge Engine sobre um dataset sintetico minimo.

Roda sem framework de teste: `python tests/test_knowledge_smoke.py`
Valida os contratos entre os modulos de ponta a ponta.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from core.types import Amostra
from knowledge import DatasetAnalyzer
from knowledge.reports import ReportGenerator


def _amostra(id_: str, sinal: str, sinalizante: str, semente: int, ruim: bool = False) -> Amostra:
    rng = np.random.default_rng(semente)
    n_frames = 4 if ruim else 30
    base = rng.random((1, 21, 3))
    trajetoria = base + np.cumsum(rng.normal(0, 0.01, (n_frames, 21, 3)), axis=0)
    return Amostra(
        id=id_,
        sinal=sinal,
        sinalizante=sinalizante,
        n_frames=n_frames,
        fps=30.0,
        duracao_s=n_frames / 30.0,
        confianca_media=0.3 if ruim else 0.9,
        taxa_landmarks_perdidos=0.05,
        landmarks=trajetoria,
    )


def main() -> None:
    amostras = []
    idx = 0
    for sinal in ("CASA", "PREDIO", "ESCOLA"):
        for sinalizante in ("Articulador01", "Articulador02"):
            for _ in range(3):
                amostras.append(_amostra(f"amostra_{idx:03d}", sinal, sinalizante, idx))
                idx += 1
    # Uma amostra ruim para exercitar o QualityAnalyzer
    amostras.append(_amostra(f"amostra_{idx:03d}", "ESCOLA", "Articulador01", idx, ruim=True))

    analise = DatasetAnalyzer().analisar(amostras)

    e = analise.estatisticas
    assert e.n_amostras == len(amostras)
    assert e.n_sinais == 3
    assert e.n_sinalizantes == 2
    assert 0.0 < e.balanceamento <= 1.0
    assert len(analise.perfis_sinalizantes) == 2
    assert len(analise.perfis_sinais) == 3
    assert all(p.velocidade_media is not None for p in analise.perfis_sinais.values())

    reprovadas = [q for q in analise.qualidade if not q.aprovada]
    assert len(reprovadas) == 1, f"esperava 1 reprovada, veio {len(reprovadas)}"

    assert analise.recomendacoes, "dataset pequeno deveria gerar recomendacoes"

    relatorio = ReportGenerator().gerar_markdown(analise)
    assert "Relatorio do Knowledge Engine" in relatorio

    print(relatorio)
    print("OK — Knowledge Engine smoke test passou.")


if __name__ == "__main__":
    main()
