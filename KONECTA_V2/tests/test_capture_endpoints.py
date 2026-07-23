"""Teste dos endpoints de captura da API."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.main import app


def criar_video_teste() -> Path:
    """Cria um vídeo sintético para teste."""
    caminho = Path("/tmp/teste_api_capture.mp4")
    caminho.parent.mkdir(exist_ok=True)

    fps = 30
    largura, altura = 640, 480
    n_frames = 30

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(caminho), fourcc, fps, (largura, altura))

    for i in range(n_frames):
        frame = np.ones((altura, largura, 3), dtype=np.uint8) * 200
        cv2.putText(
            frame,
            f"Frame {i}",
            (50, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 0),
            1,
        )
        out.write(frame)

    out.release()
    return caminho


def main() -> None:
    print("=== Teste de Endpoints de Captura ===\n")

    client = TestClient(app)

    # 1. Criar sessão
    print("[1] Criando sessão de captura...")
    resp = client.post(
        "/api/captura/sessao",
        params={
            "id_sessao": "teste_001",
            "sinal": "CASA",
            "sinalizante": "Articulador1",
        },
    )
    assert resp.status_code == 200, f"Erro ao criar sessão: {resp.text}"
    dados = resp.json()
    print(f"    ✓ Sessão criada: {dados['id']}")
    print()

    # 2. Obter metadados (deve estar vazia porque não capturamos ainda)
    print("[2] Obtendo metadados da sessão...")
    resp = client.get("/api/captura/sessao/teste_001")
    assert resp.status_code == 200, f"Erro ao obter metadados: {resp.text}"
    dados = resp.json()
    print(f"    ✓ Frames: {dados['n_frames']}")
    print(f"    ✓ Sinal: {dados['sinal']}")
    print(f"    ✓ Sinalizante: {dados['sinalizante']}")
    print()

    # 3. Testar validação (sem frames ainda)
    print("[3] Validando sessão vazia...")
    resp = client.post("/api/captura/sessao/teste_001/validar")
    assert resp.status_code == 200, f"Erro ao validar: {resp.text}"
    dados = resp.json()
    print(f"    ✓ Válida: {dados['valida']}")
    print(f"    ✓ Pontuação: {dados['pontuacao']:.2f}")
    if dados["problemas"]:
        print(f"    Problemas:")
        for p in dados["problemas"]:
            print(f"      - {p}")
    print()

    # 4. Extrair landmarks (sem frames)
    print("[4] Extraindo landmarks (sessão vazia)...")
    resp = client.post("/api/captura/sessao/teste_001/landmarks")
    assert resp.status_code == 200, f"Erro ao extrair landmarks: {resp.text}"
    dados = resp.json()
    print(f"    ✓ ID sessão: {dados['id_sessao']}")
    print(f"    ✓ Frames processados: {dados['n_frames']}")
    print()

    # 5. Testar com sessão inválida
    print("[5] Testando erro com sessão inexistente...")
    resp = client.post("/api/captura/sessao/inexistente/validar")
    assert resp.status_code == 404, "Deveria retornar 404"
    print(f"    ✓ Erro retornado corretamente (404)")
    print()

    print("=== Todos os testes passaram ===")


if __name__ == "__main__":
    main()
