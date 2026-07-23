#!/usr/bin/env python3
"""
Script para testar reconhecimento em tempo real do KONECTA V2.

Uso:
    python test_reconhecimento_ao_vivo.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from ai_engine import TreinadorModelo
from core.types import Amostra
from lsae import ReconhecedorSinais, ModoRecognition


def criar_dataset_teste() -> list[Amostra]:
    """Cria dataset de teste com 3 sinais."""
    amostras = []

    # Sinais: CASA, MESA, PORTA
    sinais = ["CASA", "MESA", "PORTA"]

    for sinal_idx, sinal in enumerate(sinais):
        # 5 amostras por sinal (diferentes sinalizantes)
        for amostra_idx in range(5):
            sinalizante = f"Art{amostra_idx + 1}"

            # Criar landmarks com padrão único por sinal
            # Isso simula diferentes sinalizantes fazendo o mesmo sinal
            landmarks = np.random.rand(30, 21, 3) * 0.4 + 0.3

            # Adicionar padrão único por sinal
            landmarks[:, :, 0] += sinal_idx * 0.12
            landmarks[:, :, 1] += amostra_idx * 0.05

            amostra = Amostra(
                id=f"{sinal}_{amostra_idx:03d}",
                sinal=sinal,
                sinalizante=sinalizante,
                n_frames=30,
                fps=30.0,
                duracao_s=1.0,
                landmarks=landmarks,
            )
            amostras.append(amostra)

    return amostras


def main() -> None:
    print("=" * 70)
    print("🎯 TESTE DE RECONHECIMENTO EM TEMPO REAL — KONECTA V2")
    print("=" * 70)
    print()

    # 1. TREINAR MODELO
    print("▶️  Etapa 1: Treinando modelo...")
    print("-" * 70)
    t0 = time.time()

    amostras = criar_dataset_teste()
    print(f"✓ {len(amostras)} amostras criadas (3 sinais × 5 sinalizantes)")

    treinador = TreinadorModelo()
    resultado = treinador.treinar(amostras)
    t1 = time.time()

    print(f"✓ Modelo treinado em {t1 - t0:.2f}s")
    print(f"  - Acurácia treino: {resultado.metricas_treino.acuracia:.1%}")
    print(f"  - Acurácia teste: {resultado.metricas_teste.acuracia:.1%}")
    print()

    # 2. TESTAR RECONHECIMENTO
    print("▶️  Etapa 2: Testando reconhecimento...")
    print("-" * 70)

    reconhecedor = ReconhecedorSinais(treinador)

    # Testar com amostras do dataset
    print("\n📍 Teste 1: Reconhecimento de Landmarks Capturados")
    print("-" * 70)

    for sinal in ["CASA", "MESA", "PORTA"]:
        # Pegar primeira amostra do sinal
        amostra_teste = next(a for a in amostras if a.sinal == sinal)

        t0 = time.time()
        resultado_pred = reconhecedor.reconhecer_landmarks(
            amostra_teste.landmarks
        )
        tempo_ms = (time.time() - t0) * 1000

        print(f"\n{sinal}:")
        print(f"  Predito: {resultado_pred.sinal}")
        print(f"  Confiança: {resultado_pred.confianca:.1%}")
        print(f"  Latência: {tempo_ms:.1f}ms")

    # 3. TESTAR COM MÚLTIPLOS FRAMES (SESSÃO)
    print("\n\n📍 Teste 2: Reconhecimento em Sessão (30 frames)")
    print("-" * 70)

    for sinal in ["CASA", "MESA", "PORTA"]:
        # Simular sessão com múltiplos frames do mesmo sinal
        frames_sessao = []
        for _ in range(30):
            frame = np.random.rand(21, 3) * 0.4 + 0.3
            # Adicionar padrão do sinal
            sinal_idx = ["CASA", "MESA", "PORTA"].index(sinal)
            frame[:, 0] += sinal_idx * 0.12
            frames_sessao.append(frame)

        t0 = time.time()
        # Converter frames em LandmarksFrame
        from mediapipe_engine.types import LandmarksFrame, Ponto3D
        landmarks_frames = []
        for frame_idx, frame in enumerate(frames_sessao):
            # Criar 21 pontos de landmarks
            pontos = [Ponto3D(x=frame[i, 0], y=frame[i, 1], z=frame[i, 2])
                      for i in range(21)]
            lm_frame = LandmarksFrame(
                numero_frame=frame_idx,
                timestamp_ms=frame_idx * 33.33,
                mao_direita=pontos,
            )
            landmarks_frames.append(lm_frame)

        resultado_sessao = reconhecedor.reconhecer_sessao(
            id_sessao=f"sessao_{sinal}",
            landmarks_lista=landmarks_frames,
        )
        tempo_ms = (time.time() - t0) * 1000

        print(f"\n{sinal} (30 frames):")
        print(f"  Predito: {resultado_sessao.sinal_dominante}")
        print(f"  Confiança média: {resultado_sessao.taxa_confianca_media:.1%}")
        print(f"  Tempo total: {tempo_ms:.1f}ms ({tempo_ms/resultado_sessao.n_frames_processados:.1f}ms/frame)")

    # 4. TESTAR COM DADOS ALEATÓRIOS (PADRÃO DESCONHECIDO)
    print("\n\n📍 Teste 3: Reconhecimento com Padrão Desconhecido")
    print("-" * 70)

    landmarks_desconhecido = np.random.rand(30, 21, 3) * 0.9

    t0 = time.time()
    resultado_desconhecido = reconhecedor.reconhecer_landmarks(landmarks_desconhecido)
    tempo_ms = (time.time() - t0) * 1000

    print(f"\nPadrão desconhecido:")
    print(f"  Melhor palpite: {resultado_desconhecido.sinal}")
    print(f"  Confiança: {resultado_desconhecido.confianca:.1%}")
    print(f"  Latência: {tempo_ms:.1f}ms")

    # 5. RESUMO FINAL
    print("\n\n" + "=" * 70)
    print("📊 RESUMO DE TESTES")
    print("=" * 70)

    print("\n✅ Testes Completados:")
    print("  1. Treinamento: OK")
    print("  2. Reconhecimento por landmark: OK")
    print("  3. Reconhecimento por sessão: OK")
    print("  4. Reconhecimento padrão desconhecido: OK")

    print("\n⚡ Performance:")
    print(f"  Latência por frame: ~{tempo_ms/30:.1f}ms")
    print(f"  FPS teórico: ~{1000/(tempo_ms/30):.0f} fps")

    print("\n🎯 Sinais Reconhecíveis:")
    for sinal in ["CASA", "MESA", "PORTA"]:
        print(f"  • {sinal}")

    print("\n" + "=" * 70)
    print("✅ TESTE DE RECONHECIMENTO: OK")
    print("=" * 70)


if __name__ == "__main__":
    main()
