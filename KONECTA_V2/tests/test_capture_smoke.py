"""Teste do módulo de Captura — Etapa 4.

Roda com: python tests/test_capture_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capture import CaptorVideo, ConfigCaptura, ValidadorCaptura


def criar_video_sintetico(caminho: Path, duracao: float = 2.0) -> None:
    """Cria um vídeo sintético para testes."""
    fps = 30
    largura, altura = 640, 480
    n_frames = int(duracao * fps)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(caminho), fourcc, fps, (largura, altura))

    for i in range(n_frames):
        frame = np.ones((altura, largura, 3), dtype=np.uint8) * 150
        cv2.putText(
            frame,
            f"Frame {i}",
            (50, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            2,
            (255, 0, 0),
            2,
        )
        cv2.circle(frame, (320, 240), 50 + i % 20, (0, 255, 0), -1)
        out.write(frame)

    out.release()


def main() -> None:
    print("=== Etapa 4 — Captura de Vídeo ===\n")

    # Criar vídeo sintético
    caminho_temp = Path("/tmp/teste_capture.mp4")
    caminho_temp.parent.mkdir(exist_ok=True)
    criar_video_sintetico(caminho_temp)
    print(f"✓ Vídeo sintético criado: {caminho_temp}\n")

    # Testar captura do arquivo
    config = ConfigCaptura(fps=30, resolucao=(640, 480))
    captor = CaptorVideo(config=config)

    print("[TESTANDO] Captura de arquivo")
    sessao = captor.iniciar_sessao("TESTE", "TestArtist")
    sessao = captor.capturar_do_arquivo(caminho_temp)

    print(f"  Frames capturados: {sessao.n_frames}")
    print(f"  FPS realizado: {sessao.fps_realizado:.1f}")
    print(f"  Duração: {sessao.duracao_segundos:.2f}s")
    print(f"  Iluminação média: {sessao.qualidade_media_luz:.2f}")
    print()

    # Validar captura
    print("[TESTANDO] Validação de captura")
    validador = ValidadorCaptura()
    resultado = validador.validar_sessao(sessao)

    print(f"  Válida: {resultado.valida}")
    print(f"  Pontuação: {resultado.pontuacao_geral:.2f}")

    if resultado.problemas:
        print(f"  Problemas:")
        for problema in resultado.problemas:
            print(f"    - {problema}")

    if resultado.avisos:
        print(f"  Avisos:")
        for aviso in resultado.avisos:
            print(f"    - {aviso}")

    print()

    # Limpeza
    caminho_temp.unlink()
    print("=== Teste concluído ===")


if __name__ == "__main__":
    main()
