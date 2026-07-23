"""Teste do LSAE Engine — Etapa 10.

Roda com: python tests/test_lsae_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_engine import TreinadorModelo, TipoModelo
from core.types import Amostra
from lsae import ReconhecedorSinais, ModoRecognition


def criar_dataset_teste() -> list[Amostra]:
    """Cria um dataset para treinamento."""
    amostras = []

    for sinal_idx, sinal in enumerate(["CASA", "MESA"]):
        for art_idx, sinalizante in enumerate(["Art1", "Art2"]):
            for amostra_idx in range(8):
                landmarks = np.random.rand(30, 21, 3) * 0.5 + 0.25
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
    print("=== Etapa 10 — LSAE Engine (Reconhecimento) ===\n")

    # 1. Treinar modelo
    print("[1] Treinando modelo...")
    amostras = criar_dataset_teste()
    treinador = TreinadorModelo()
    resultado = treinador.treinar(
        amostras,
        tipo_modelo=TipoModelo.RANDOM_FOREST,
        test_size=0.2,
        val_size=0.1,
    )
    print(f"    ✓ Acurácia teste: {resultado.metricas_teste.acuracia:.1%}")
    print()

    # 2. Criar reconhecedor
    print("[2] Inicializando reconhecedor...")
    reconhecedor = ReconhecedorSinais(treinador)
    print(f"    ✓ Reconhecedor pronto")
    print(f"    ✓ Classes: {list(reconhecedor.classes)}")
    print()

    # 3. Testar reconhecimento de frame único
    print("[3] Reconhecendo frame único...")
    teste_landmarks = np.random.rand(30, 21, 3) * 0.5 + 0.25
    teste_landmarks[:, :, 0] += 0.15  # Padrão para CASA

    predicao = reconhecedor.reconhecer_landmarks(teste_landmarks)
    print(f"    ✓ Sinal predito: {predicao.sinal}")
    print(f"    ✓ Confiança: {predicao.confianca:.1%}")
    print(f"    ✓ Ranking top 3:")
    for i, (sinal, prob) in enumerate(predicao.ranking[:3]):
        print(f"       {i+1}. {sinal}: {prob:.1%}")
    print()

    # 4. Testar reconhecimento de sessão
    print("[4] Reconhecendo sessão com múltiplos frames...")
    from mediapipe_engine.types import LandmarksFrame, Ponto3D

    frames = []
    for frame_idx in range(5):
        pontos = []
        for _ in range(21):
            ponto = Ponto3D(
                x=np.random.rand() * 0.5 + 0.25,
                y=np.random.rand() * 0.5 + 0.25,
                z=np.random.rand() * 0.1,
                confianca=0.9,
            )
            pontos.append(ponto)

        # Padrão MESA (sinal_idx=1)
        for ponto in pontos:
            ponto.x += 0.15

        lm_frame = LandmarksFrame(
            numero_frame=frame_idx,
            timestamp_ms=frame_idx * 33.33,
            mao_direita=pontos,
        )
        frames.append(lm_frame)

    resultado_sessao = reconhecedor.reconhecer_sessao(
        "teste_001",
        frames,
        modo=ModoRecognition.VIDEO_COMPLETO,
    )

    print(f"    ✓ Frames processados: {resultado_sessao.n_frames_processados}")
    print(f"    ✓ Sinal dominante: {resultado_sessao.sinal_dominante}")
    print(f"    ✓ Confiança média: {resultado_sessao.taxa_confianca_media:.1%}")
    print(f"    ✓ Taxa de confiança geral (>70%): {resultado_sessao.taxa_confianca_geral:.1%}")
    print(f"    ✓ Tempo processamento: {resultado_sessao.tempo_processamento_s*1000:.1f}ms")
    print()

    # 5. Estatísticas
    print("[5] Estatísticas de reconhecimento:")
    print(f"    Predições totais: {len(resultado_sessao.predicoes)}")
    print(f"    Confiáveis (>70%): {resultado_sessao.acertos_confiaveis}")
    if resultado_sessao.predicoes:
        confiancas = [p.confianca for p in resultado_sessao.predicoes]
        print(f"    Confiança: min={min(confiancas):.1%}, max={max(confiancas):.1%}")
    print()

    print("=== Teste concluído ===")
    print("\n✓ Pipeline completo funcional:")
    print("  1. Treinamento (AI Engine)")
    print("  2. Reconhecimento tempo-real (LSAE Engine)")
    print("  3. Pronto para integração com frontend")


if __name__ == "__main__":
    main()
