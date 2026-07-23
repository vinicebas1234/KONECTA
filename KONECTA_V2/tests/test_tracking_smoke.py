"""Teste do Tracking Engine — Etapa 6.

Roda com: python tests/test_tracking_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capture import CaptorVideo, ConfigCaptura
from mediapipe_engine import ExtratormediaPipeHands
from tracking import AnalisadorTrajetoria


def criar_video_teste() -> Path:
    """Cria um vídeo sintético para teste."""
    caminho = Path("/tmp/teste_tracking.mp4")
    caminho.parent.mkdir(exist_ok=True)

    fps = 30
    largura, altura = 640, 480
    n_frames = 60  # 2 segundos

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(caminho), fourcc, fps, (largura, altura))

    for i in range(n_frames):
        frame = np.ones((altura, largura, 3), dtype=np.uint8) * 240

        # Desenhar simulação de movimento circular
        progresso = i / n_frames
        x = int(320 + 100 * np.cos(2 * np.pi * progresso))
        y = int(240 + 100 * np.sin(2 * np.pi * progresso))

        cv2.circle(frame, (x, y), 20, (0, 255, 0), -1)
        cv2.putText(
            frame,
            f"Frame {i}",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 0),
            1,
        )

        out.write(frame)

    out.release()
    return caminho


def main() -> None:
    print("=== Etapa 6 — Tracking Engine ===\n")

    # Criar vídeo
    caminho_temp = criar_video_teste()
    print(f"✓ Vídeo sintético criado: {caminho_temp}\n")

    # Capturar
    config = ConfigCaptura(fps=30, resolucao=(640, 480))
    captor = CaptorVideo(config=config)
    sessao = captor.iniciar_sessao("TESTE_TRACKING", "TestArtist")
    sessao = captor.capturar_do_arquivo(caminho_temp)
    print(f"✓ {sessao.n_frames} frames capturados\n")

    # Extrair landmarks
    print("[ETAPA 1] Extração de landmarks...")
    extrator_maos = ExtratormediaPipeHands()
    landmarks_maos = extrator_maos.extrair_da_sessao(sessao)
    extrator_maos.limpar()

    frames_com_maos = sum(
        1 for lm in landmarks_maos
        if lm.mao_direita or lm.mao_esquerda
    )
    print(f"  Frames com detecção de mãos: {frames_com_maos}\n")

    # Analisar trajetórias
    print("[ETAPA 2] Análise de trajetórias...")
    analisador = AnalisadorTrajetoria()
    analise = analisador.analisar_landmarks(
        id_sessao="teste_001",
        landmarks_maos=landmarks_maos,
    )

    print(f"  Dominância: {analise.dominancia.value}")
    print(f"  Local principal: {analise.local_principal.value}")
    print(f"  Complexidade: {analise.complexidade_estimada:.2f}")
    print(f"  Duração (frames): {analise.duracao_movimento_frames}")
    print(f"  Velocidade média: {analise.velocidade_media_geral:.3f} px/frame")
    print()

    # Detalhar mãos
    if analise.maos:
        print("[ETAPA 3] Análise de mãos...")
        for lado, mao in analise.maos.items():
            print(f"  {lado.upper()}:")
            print(f"    - Ativa em {mao.ativa_em_frames} frames")
            print(f"    - Velocidade média: {mao.velocidade_media:.3f} px/frame")
            print(f"    - Amplitude total: {mao.amplitude_total:.1f} px")
            print(f"    - Estabilidade: {mao.estabilidade:.2f}")
            print(f"    - Trajetórias: {len(mao.trajetorias)} pontos")

    caminho_temp.unlink()
    print("\n=== Teste concluído ===")


if __name__ == "__main__":
    main()
