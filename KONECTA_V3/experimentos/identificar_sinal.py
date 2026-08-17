"""Identifica um vídeo contra o vocabulário inteiro do V-Librasil (1.364 sinais).

O modelo treinado no SIGNLAB só conhece os sinais que a pessoa gravou. Quando o
vídeo é de outro sinal, ele responde o mais parecido entre os poucos que tem —
resposta confiante e errada. Aqui comparamos com o dataset público completo.

Método: extrai landmarks no MESMO formato do V-Librasil (126 features, 2 mãos
normalizadas pelo punho), reamostra e compara por DTW contra cada sinal, com
filtro grosseiro antes do reranking fino.

**Confiabilidade medida** (experimentos/dtw_prototipos.py, mesmo método):
cross-signer, 1.364 classes → 1,5% de acerto em 1º lugar. Ou seja: o ranking
serve para *sugerir* candidatos, não para afirmar. Por isso imprimimos o top-10.

Só leitura: nada é modificado.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

RAIZ_V1 = Path("C:/KONECTA/archive/OCR")
DADOS = RAIZ_V1 / "dados_libras" / "dinamicos"
CSV_MAPA = RAIZ_V1 / "vlibrasil_converter_20260630_184206.csv"

COMPRIMENTO = 30
PONTOS_RESUMO = 8
CANDIDATOS = 120
FEATURES_POR_MAO = 63
TOTAL_FEATURES = 126


# ------------------------------------------------------- extração do vídeo


def _normalizar_mao(pts: np.ndarray) -> np.ndarray:
    """Punho na origem, escala pela distância punho→MCP do médio.

    Réplica exata de ``GerenciadorVisao._normalizar_mao`` do KONECTA V1 — é o
    que gerou os vetores do dataset, e qualquer divergência aqui inviabiliza a
    comparação.
    """
    pts = pts.astype(np.float32).copy()
    pts -= pts[0].copy()
    ref = float(np.linalg.norm(pts[9] - pts[0]))
    if ref < 1e-6:
        ref = float(np.max(np.abs(pts)))
    if ref < 1e-6:
        ref = 1.0
    return pts / ref


def extrair_sequencia(caminho_video: str) -> np.ndarray:
    """Vídeo → (N, 126), no formato do V-Librasil."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import vision as mp_vision
    from mediapipe.tasks.python.core.base_options import BaseOptions

    asset = None
    for candidato in (
        Path("C:/KONECTA/SIGNLAB/vision/models/hand_landmarker.task"),
        Path("C:/KONECTA/OCR/modelos/hand_landmarker.task"),
        Path("C:/KONECTA/archive/OCR/modelos/hand_landmarker.task"),
    ):
        if candidato.is_file():
            asset = candidato
            break
    if asset is None:
        raise SystemExit("hand_landmarker.task não encontrado")

    detector = mp_vision.HandLandmarker.create_from_options(
        mp_vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(asset)),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_hands=2,
            min_hand_detection_confidence=0.5,
        )
    )

    captura = cv2.VideoCapture(caminho_video)
    frames = []
    while True:
        ok, frame = captura.read()
        if not ok:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        imagem = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        resultado = detector.detect(imagem)

        vetor = np.zeros(TOTAL_FEATURES, dtype=np.float32)
        for indice, marcas in enumerate(resultado.hand_landmarks[:2]):
            pontos = np.array([[p.x, p.y, p.z] for p in marcas], dtype=np.float32)
            inicio = indice * FEATURES_POR_MAO
            vetor[inicio : inicio + FEATURES_POR_MAO] = _normalizar_mao(pontos).flatten()
        if resultado.hand_landmarks:
            frames.append(vetor)
    captura.release()

    if not frames:
        raise SystemExit("nenhuma mão detectada no vídeo")
    return np.stack(frames)


# ------------------------------------------------------- dataset e busca


def reamostrar(sequencia: np.ndarray, n: int) -> np.ndarray:
    if len(sequencia) == n:
        return sequencia
    origem = np.linspace(0.0, 1.0, len(sequencia))
    destino = np.linspace(0.0, 1.0, n)
    return np.stack(
        [np.interp(destino, origem, sequencia[:, c]) for c in range(sequencia.shape[1])],
        axis=1,
    )


def dtw(a: np.ndarray, b: np.ndarray, banda: int = 10) -> float:
    n, m = len(a), len(b)
    custo = np.full((n + 1, m + 1), np.inf, dtype=np.float32)
    custo[0, 0] = 0.0
    for i in range(1, n + 1):
        inicio = max(1, i - banda)
        fim = min(m, i + banda)
        dif = b[inicio - 1 : fim] - a[i - 1]
        distancias = np.sqrt((dif * dif).sum(axis=1))
        for desloc, j in enumerate(range(inicio, fim + 1)):
            custo[i, j] = distancias[desloc] + min(
                custo[i - 1, j], custo[i, j - 1], custo[i - 1, j - 1]
            )
    return float(custo[n, m] / (n + m))


def carregar_referencias(limite_classes=None):
    """Cada amostra do dataset vira uma referência (kNN bate a média)."""
    validos = set()
    with open(CSV_MAPA, "r", encoding="utf-8", errors="replace") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha.get("status") == "ok":
                validos.add(Path(*Path(linha["destino"]).parts[-5:]))

    rotulos, refs, resumos = [], [], []
    classes = sorted(p.name for p in DADOS.iterdir() if p.is_dir())
    if limite_classes:
        classes = classes[:limite_classes]

    for rotulo in classes:
        pasta = DADOS / rotulo / "public"
        if not pasta.is_dir():
            continue
        for caminho in sorted(pasta.glob("*.npy")):
            if Path(*caminho.parts[-5:]) not in validos:
                continue
            try:
                seq = np.load(caminho).astype(np.float32)
            except Exception:
                continue
            if seq.ndim != 2 or seq.shape[1] != TOTAL_FEATURES:
                continue
            seq = reamostrar(seq, COMPRIMENTO)
            rotulos.append(rotulo)
            refs.append(seq)
            resumos.append(reamostrar(seq, PONTOS_RESUMO).reshape(-1))
    return rotulos, refs, np.stack(resumos)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("--classes", type=int, default=None)
    p.add_argument("--top", type=int, default=10)
    args = p.parse_args()

    print("extraindo landmarks do vídeo…", flush=True)
    consulta = extrair_sequencia(args.video)
    print(f"  {len(consulta)} frames com mãos", flush=True)
    consulta = reamostrar(consulta, COMPRIMENTO)
    resumo = reamostrar(consulta, PONTOS_RESUMO).reshape(-1)

    print("carregando o vocabulário do V-Librasil…", flush=True)
    rotulos, refs, resumos = carregar_referencias(args.classes)
    print(f"  {len(set(rotulos))} sinais, {len(rotulos)} amostras", flush=True)

    distancias = np.linalg.norm(resumos - resumo, axis=1)
    k = min(CANDIDATOS, len(rotulos))
    finalistas = np.argpartition(distancias, k - 1)[:k]

    print("comparando por DTW…", flush=True)
    melhor_por_sinal = defaultdict(lambda: np.inf)
    for indice in finalistas:
        d = dtw(consulta, refs[indice])
        if d < melhor_por_sinal[rotulos[indice]]:
            melhor_por_sinal[rotulos[indice]] = d

    ranking = sorted(melhor_por_sinal.items(), key=lambda item: item[1])
    print()
    print("=" * 54)
    print(f"CANDIDATOS para {Path(args.video).name}")
    print("=" * 54)
    for posicao, (nome, distancia) in enumerate(ranking[: args.top], 1):
        print(f"  {posicao:>2}. {nome:<28} distância {distancia:.4f}")
    print("=" * 54)
    print("Ranking sugere, não afirma: este método acerta ~1,5% em 1º lugar")
    print("no teste cross-signer com 1.364 classes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
