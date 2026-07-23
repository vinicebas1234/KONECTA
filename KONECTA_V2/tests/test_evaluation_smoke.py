"""Teste de Avaliação — Etapa 11.

Roda com: python tests/test_evaluation_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_engine import TreinadorModelo, TipoModelo
from core.types import Amostra
from evaluation import AvaliadorModelo


def criar_dataset_cross_signer() -> list[Amostra]:
    """Cria dataset com múltiplos sinalizantes."""
    amostras = []

    sinais = ["CASA", "MESA", "PORTA"]
    sinalizantes = ["Art1", "Art2", "Art3"]

    # Dados de treino com padrões por sinal E sinalizante
    for sinal_idx, sinal in enumerate(sinais):
        for art_idx, sinalizante in enumerate(sinalizantes):
            # 6 amostras por sinal/sinalizante
            for amostra_idx in range(6):
                landmarks = np.random.rand(30, 21, 3) * 0.4 + 0.3

                # Padrão do sinal (deve ser consistente)
                landmarks[:, :, 0] += sinal_idx * 0.12

                # Variação do sinalizante (dificulta generalização)
                landmarks[:, :, 1] += art_idx * 0.08

                # Variação aleatória (ruído)
                landmarks += np.random.randn(30, 21, 3) * 0.02

                amostra = Amostra(
                    id=f"{sinal}_{sinalizante}_{amostra_idx}",
                    sinal=sinal,
                    sinalizante=sinalizante,
                    n_frames=30,
                    fps=30.0,
                    duracao_s=1.0,
                    landmarks=landmarks,
                    confianca_media=0.85,
                )
                amostras.append(amostra)

    return amostras


def main() -> None:
    print("=== Etapa 11 — Avaliação Cross-Signer ===\n")

    # Criar dataset
    print("[1] Criando dataset com múltiplos sinalizantes...")
    amostras = criar_dataset_cross_signer()
    print(f"    ✓ {len(amostras)} amostras")
    print(f"    ✓ Sinais: {set(a.sinal for a in amostras)}")
    print(f"    ✓ Sinalizantes: {set(a.sinalizante for a in amostras)}")
    print()

    # Treinar
    print("[2] Treinando modelo...")
    treinador = TreinadorModelo()
    resultado_treino = treinador.treinar(
        amostras,
        tipo_modelo=TipoModelo.RANDOM_FOREST,
        test_size=0.2,
        val_size=0.1,
    )
    print(f"    ✓ Acurácia teste: {resultado_treino.metricas_teste.acuracia:.1%}")
    print()

    # Avaliar
    print("[3] Avaliação cross-signer...")
    avaliador = AvaliadorModelo(treinador)
    relatorio = avaliador.avaliar_cross_signer(amostras)

    print(f"    Acurácia geral: {relatorio.acurácia_geral:.1%}")
    print(f"    F1-score macro: {relatorio.macro_f1:.3f}")
    print(f"    F1-score weighted: {relatorio.weighted_f1:.3f}")
    print()

    # Cross-signer por sinal
    print("[4] Métricas por sinal:")
    for sinal, metricas in relatorio.cross_signer_metrics.items():
        print(f"    {sinal}:")
        print(f"      - Acurácia média: {metricas.acurácia_media:.1%}")
        print(f"      - Min/Max: {metricas.acurácia_minima:.1%} / {metricas.acurácia_maxima:.1%}")
        print(f"      - Variância cross-signer: {metricas.variancia_cross_signer:.4f}")
        if metricas.sinalizantes_problematicos:
            print(f"      - Sinalizantes problemáticos: {', '.join(metricas.sinalizantes_problematicos)}")
    print()

    # Matriz de confusão
    print("[5] Matriz de Confusão:")
    print(f"    Sinais: {relatorio.matriz_confusao.sinais}")
    print(f"    F1-score por sinal:")
    for sinal, f1 in relatorio.matriz_confusao.f1_por_sinal.items():
        print(f"      - {sinal}: {f1:.3f}")
    print()

    # Sinais problemáticos
    if relatorio.sinais_problematicos:
        print(f"[6] Sinais Problemáticos:")
        for sinal in relatorio.sinais_problematicos:
            metricas = relatorio.cross_signer_metrics[sinal]
            print(f"    - {sinal}: {metricas.acurácia_media:.1%} acurácia")
        print()

    # Sinalizantes problemáticos
    if relatorio.sinalizantes_problematicos:
        print(f"[7] Sinalizantes Problemáticos:")
        for sinalizante, taxa_erro in sorted(
            relatorio.sinalizantes_problematicos.items(),
            key=lambda x: -x[1]
        ):
            print(f"    - {sinalizante}: {taxa_erro:.1%} erro")
        print()

    # Recomendações
    if relatorio.recomendacoes:
        print(f"[8] Recomendações:")
        for rec in relatorio.recomendacoes:
            print(f"    • {rec}")
        print()

    print("=== Teste concluído ===")
    print("\n✓ Avaliação completa funcional:")
    print("  1. Métricas gerais (acurácia, F1)")
    print("  2. Análise cross-signer por sinal")
    print("  3. Detecção de sinalizantes problemáticos")
    print("  4. Recomendações automáticas")


if __name__ == "__main__":
    main()
