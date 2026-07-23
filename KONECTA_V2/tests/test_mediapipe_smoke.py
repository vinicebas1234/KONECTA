"""Teste do MediaPipe Engine — Etapa 5.

Roda com: python tests/test_mediapipe_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capture import CaptorVideo, ConfigCaptura
from mediapipe_engine import ExtratormediaPipeHands, ExtratormediaPipePose


def criar_video_sintetico_com_maos(caminho: Path, duracao: float = 1.0) -> None:
    """Cria um vídeo sintético com simulação de mãos para teste."""
    fps = 30
    largura, altura = 640, 480
    n_frames = int(duracao * fps)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(caminho), fourcc, fps, (largura, altura))

    for i in range(n_frames):
        # Fundo branco para melhor detecção
        frame = np.ones((altura, largura, 3), dtype=np.uint8) * 240

        # Desenhar círculos simulando mãos
        progresso = i / n_frames
        x_esq = int(150 + 100 * np.sin(progresso * 2 * np.pi))
        x_dir = int(490 + 100 * np.sin(progresso * 2 * np.pi + np.pi))
        y = 240

        cv2.circle(frame, (x_esq, y), 30, (0, 0, 255), -1)
        cv2.circle(frame, (x_dir, y), 30, (255, 0, 0), -1)

        # Texto
        cv2.putText(
            frame,
            f"Frame {i} - MediaPipe Test",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 0),
            1,
        )

        out.write(frame)

    out.release()


def main() -> None:
    print("=== Etapa 5 — MediaPipe Engine ===\n")

    # Criar vídeo sintético
    caminho_temp = Path("/tmp/teste_mediapipe.mp4")
    caminho_temp.parent.mkdir(exist_ok=True)
    criar_video_sintetico_com_maos(caminho_temp)
    print(f"✓ Vídeo sintético criado: {caminho_temp}\n")

    # Capturar vídeo
    config = ConfigCaptura(fps=30, resolucao=(640, 480))
    captor = CaptorVideo(config=config)
    sessao = captor.iniciar_sessao("TESTE_MEDIAPIPE", "TestArtist")
    sessao = captor.capturar_do_arquivo(caminho_temp)
    print(f"✓ {sessao.n_frames} frames capturados\n")

    # Testar extração de landmarks de mãos
    print("[TESTANDO] Extração de landmarks — Mãos")
    extrator_maos = ExtratormediaPipeHands()
    landmarks_maos = extrator_maos.extrair_da_sessao(sessao)

    frames_com_maos = sum(
        1
        for lm in landmarks_maos
        if lm.mao_direita or lm.mao_esquerda
    )
    print(f"  Frames com landmarks de mãos: {frames_com_maos}/{len(landmarks_maos)}")
    if frames_com_maos > 0:
        media_confianca = np.mean(
            [lm.confianca_media for lm in landmarks_maos if lm.confianca_media > 0]
        )
        print(f"  Confiança média: {media_confianca:.3f}")
    print()

    # Testar extração de landmarks do corpo
    print("[TESTANDO] Extração de landmarks — Corpo (Pose)")
    extrator_corpo = ExtratormediaPipePose()
    landmarks_corpo = extrator_corpo.extrair_da_sessao(sessao)

    frames_com_corpo = sum(1 for lm in landmarks_corpo if lm.corpo)
    print(f"  Frames com landmarks do corpo: {frames_com_corpo}/{len(landmarks_corpo)}")
    if frames_com_corpo > 0:
        media_confianca = np.mean(
            [lm.confianca_media for lm in landmarks_corpo if lm.confianca_media > 0]
        )
        print(f"  Confiança média: {media_confianca:.3f}")
    print()

    # Estatísticas gerais
    print("[RESULTADO] Estatísticas")
    total_pontos_maos = sum(
        len(lm.mao_direita) + len(lm.mao_esquerda)
        for lm in landmarks_maos
    )
    total_pontos_corpo = sum(len(lm.corpo) for lm in landmarks_corpo)
    print(f"  Total de pontos extraídos (mãos): {total_pontos_maos}")
    print(f"  Total de pontos extraídos (corpo): {total_pontos_corpo}")

    extrator_maos.limpar()
    extrator_corpo.limpar()

    # Limpeza
    caminho_temp.unlink()
    print("\n=== Teste concluído ===")


if __name__ == "__main__":
    main()
