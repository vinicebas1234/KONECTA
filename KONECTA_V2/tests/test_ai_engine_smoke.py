"""Teste do AI Engine — Etapa 9.

Roda com: python tests/test_ai_engine_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_engine import TreinadorModelo, TipoModelo
from core.types import Amostra


def criar_dataset_teste() -> list[Amostra]:
    """Cria um dataset sintético para teste."""
    amostras = []

    sinais = ["CASA", "MESA", "PORTA"]
    sinalizantes = ["Art1", "Art2"]

    # Gerar amostras por sinal
    for sinal_idx, sinal in enumerate(sinais):
        for art_idx, sinalizante in enumerate(sinalizantes):
            for amostra_idx in range(5):  # 5 amostras por sinal/sinalizante
                # Criar landmarks com padrão específico por sinal
                landmarks = np.random.rand(30, 21, 3) * 0.5 + 0.25

                # Adicionar padrão identificador do sinal
                landmarks[:, :, 0] += sinal_idx * 0.15
                landmarks[:, :, 1] += art_idx * 0.1

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
    print("=== Etapa 9 — AI Engine ===\n")

    # Criar dataset
    print("[1] Criando dataset de teste...")
    amostras = criar_dataset_teste()
    print(f"    ✓ {len(amostras)} amostras criadas")
    print(f"    ✓ Sinais: {set(a.sinal for a in amostras)}")
    print(f"    ✓ Sinalizantes: {set(a.sinalizante for a in amostras)}")
    print()

    # Treinar modelo
    print("[2] Treinando modelo...")
    treinador = TreinadorModelo()
    resultado = treinador.treinar(
        amostras,
        tipo_modelo=TipoModelo.RANDOM_FOREST,
        test_size=0.2,
        val_size=0.1,
    )

    print(f"    ✓ Modelo treinado em {resultado.tempo_treinamento_s:.2f}s")
    print(f"    ✓ Amostras: treino={resultado.n_amostras_treino}, val={resultado.n_amostras_validacao}, teste={resultado.n_amostras_teste}")
    print()

    # Métricas de treino
    print("[3] Métricas de desempenho:")
    print(f"    Treino:")
    print(f"      - Acurácia: {resultado.metricas_treino.acuracia:.3f}")
    print(f"      - Precisão: {resultado.metricas_treino.precisao:.3f}")
    print(f"      - Recall: {resultado.metricas_treino.recall:.3f}")
    print(f"      - F1-Score: {resultado.metricas_treino.f1_score:.3f}")
    print()

    print(f"    Validação:")
    print(f"      - Acurácia: {resultado.metricas_validacao.acuracia:.3f}")
    print(f"      - Precisão: {resultado.metricas_validacao.precisao:.3f}")
    print(f"      - Recall: {resultado.metricas_validacao.recall:.3f}")
    print(f"      - F1-Score: {resultado.metricas_validacao.f1_score:.3f}")
    print()

    print(f"    Teste:")
    print(f"      - Acurácia: {resultado.metricas_teste.acuracia:.3f}")
    print(f"      - Precisão: {resultado.metricas_teste.precisao:.3f}")
    print(f"      - Recall: {resultado.metricas_teste.recall:.3f}")
    print(f"      - F1-Score: {resultado.metricas_teste.f1_score:.3f}")
    print()

    # Analisar erros
    print("[4] Análise de erros...")
    matriz, erros = treinador.analisar_erros(amostras)

    print(f"    Matriz de confusão:")
    print(f"      - Acertos: {matriz.acertos_diagonais}")
    print(f"      - Erros: {matriz.erros_totais}")
    print(f"      - Taxa de acerto: {matriz.taxa_acerto:.1%}")
    print()

    if erros.sinais_problematicos:
        print(f"    Sinais problemáticos:")
        for sinal, taxa_erro in erros.sinais_problematicos.items():
            print(f"      - {sinal}: {taxa_erro:.1%} erro")
        print()

    if erros.confusoes_principais:
        print(f"    Confusões principais:")
        for real, pred, count in erros.confusoes_principais[:3]:
            print(f"      - {real} confundido com {pred}: {count} vezes")
        print()

    if erros.recomendacoes:
        print(f"    Recomendações:")
        for rec in erros.recomendacoes[:3]:
            print(f"      - {rec}")
    print()

    print("=== Teste concluído ===")


if __name__ == "__main__":
    main()
