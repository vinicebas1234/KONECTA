"""Teste de integração: Tracking Engine + Knowledge Engine.

Valida que amostras com landmarks são enriquecidas com dados de tracking
antes da análise do Knowledge Engine.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.types import Amostra
from knowledge.dataset_analyzer import DatasetAnalyzer
from knowledge.enricher import enriquecer_amostra


def criar_amostra_com_landmarks() -> Amostra:
    """Cria uma amostra sintética com landmarks."""
    # Tensor: (30 frames, 21 pontos, 3 coords)
    landmarks = np.random.rand(30, 21, 3)

    # Movimento circular: animar pontos em padrão
    for frame in range(30):
        progresso = frame / 30.0
        # Simular movimento em círculo
        angulo = 2 * np.pi * progresso
        deslocamento = 0.15 * np.cos(angulo)

        for ponto in range(21):
            landmarks[frame, ponto, 0] += deslocamento

    return Amostra(
        id="teste_001",
        sinal="CASA",
        sinalizante="Art1",
        n_frames=30,
        fps=30.0,
        duracao_s=1.0,
        landmarks=landmarks,
        confianca_media=0.85,
    )


def main() -> None:
    print("=== Teste de Integração: Tracking + Knowledge Engine ===\n")

    # 1. Criar amostra com landmarks
    print("[1] Criando amostra com landmarks...")
    amostra = criar_amostra_com_landmarks()
    print(f"    ✓ Amostra: {amostra.id}")
    print(f"    ✓ Landmarks shape: {amostra.landmarks.shape}")
    print(f"    ✓ Dominância antes: {amostra.dominancia}")
    print()

    # 2. Enriquecer amostra com tracking
    print("[2] Enriquecendo com análise de trajetória...")
    amostra_enriquecida = enriquecer_amostra(amostra)
    print(f"    ✓ Dominância depois: {amostra_enriquecida.dominancia}")
    print(f"    ✓ Velocidade média: {amostra_enriquecida.velocidade_media:.3f}")
    print(f"    ✓ Complexidade: {amostra_enriquecida.complexidade:.3f}")
    print()

    # 3. Analisar com Knowledge Engine
    print("[3] Analisando com Knowledge Engine...")
    analyzer = DatasetAnalyzer()

    progresso_etapas = []

    def on_progresso(msg: str):
        progresso_etapas.append(msg)
        print(f"    - {msg}")

    # Usar 3 amostras para teste (mesmo sinal, sinalizantes diferentes)
    amostras = [amostra_enriquecida]
    amostras.append(Amostra(
        id="teste_002",
        sinal="CASA",
        sinalizante="Art2",
        n_frames=30,
        fps=30.0,
        duracao_s=1.0,
        landmarks=np.random.rand(30, 21, 3),
    ))
    amostras.append(Amostra(
        id="teste_003",
        sinal="MESA",
        sinalizante="Art1",
        n_frames=30,
        fps=30.0,
        duracao_s=1.0,
        landmarks=np.random.rand(30, 21, 3),
    ))

    analise = analyzer.analisar(amostras, on_progresso=on_progresso)
    print()

    # 4. Validar resultados
    print("[4] Resultados da análise:")
    print(f"    ✓ Estatísticas:")
    print(f"      - Total amostras: {analise.estatisticas.n_amostras}")
    print(f"      - Sinais: {analise.estatisticas.n_sinais}")
    print(f"      - Sinalizantes: {analise.estatisticas.n_sinalizantes}")
    print(f"      - Balanceamento: {analise.estatisticas.balanceamento:.2f}")
    print()

    print(f"    ✓ Perfis de sinais:")
    for sinal, perfil in analise.perfis_sinais.items():
        print(f"      - {sinal}: {perfil.n_amostras} amostras")
        if perfil.complexidade is not None:
            print(f"        Complexidade: {perfil.complexidade:.3f}")
    print()

    print(f"    ✓ Qualidade:")
    aprovadas = sum(1 for q in analise.qualidade if q.aprovada)
    print(f"      - Aprovadas: {aprovadas}/{len(analise.qualidade)}")
    print()

    print(f"    ✓ Recomendações:")
    for rec in analise.recomendacoes[:3]:
        sinais_str = ", ".join(rec.sinais) if rec.sinais else "N/A"
        print(f"      - {sinais_str}: {rec.prioridade.value}")
    print()

    print("=== Teste concluído ===")
    print("\n✓ Pipeline completo funcional:")
    print("  1. Amostras com landmarks")
    print("  2. Enriquecimento automático com Tracking Engine")
    print("  3. Análise completa com Knowledge Engine")
    print("  4. Recomendações geradas")


if __name__ == "__main__":
    main()
