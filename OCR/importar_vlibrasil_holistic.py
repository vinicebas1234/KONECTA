#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔════════════════════════════════════════════════════════════════════════════╗
║  IMPORTADOR V-LIBRASIL → LANDMARKS (MEDIAPIPE HOLISTIC)                   ║
║  Mãos + corpo + expressão facial, com rastreio de sinalizante             ║
╚════════════════════════════════════════════════════════════════════════════╝

Complementa `importar_dataset_libras.py` (que usa só HandLandmarker). Aqui a
extração é feita com HolisticLandmarker, o que traz três ganhos concretos:

  1. MÃO ESQUERDA E DIREITA SÃO EXPLÍCITAS.
     O HandLandmarker devolve as mãos por ordem de detecção, então a mesma mão
     cai no slot 0 num vídeo e no slot 1 em outro — o vetor de features fica
     inconsistente entre amostras da MESMA classe. O Holistic entrega
     `left_hand_landmarks` e `right_hand_landmarks` separados, então o slot é
     estável por construção.

  2. CORPO E ROSTO ENTRAM NO VETOR.
     Em Libras, expressão facial e ponto de articulação no corpo são
     gramaticais, não decorativos ("QUERER" x "NÃO-QUERER" muda pela face).
     Só as mãos jogam essa informação fora.

  3. O SINALIZANTE (`user_id`) É PRESERVADO NO MANIFESTO.
     Sem isso não dá para fazer split por pessoa, que é a única avaliação
     honesta em reconhecimento de sinais — e a primeira coisa que uma banca
     pergunta. Ver `manifest.csv` na saída.

Dois formatos de saída (`--formato`):

  compativel  (N, 126)  2 mãos x 21 x 3
              → dados_libras/dinamicos/<sinal>/public/NNN.npy
              Mesmo contrato de libras_recognizer.py: consumido direto pelos
              modelos que já existem, sem tocar em nada.

  holistic    (N, 606)  126 (mãos) + 132 (pose 33x4) + 348 (face 116x3)
              → dados_libras/holistic/<sinal>/public/NNN.npy
              Pasta separada de propósito: não contamina o dataset atual.

  ambos       grava os dois numa passada só (recomendado — o custo caro é
              decodificar o vídeo, não montar o vetor).

Instalação:
  pip install opencv-python mediapipe numpy pandas

Uso:
  python importar_vlibrasil_holistic.py --annotations anotacoes.csv --videos-dir data/
  python importar_vlibrasil_holistic.py --formato ambos --max-videos-per-signal 3
  python importar_vlibrasil_holistic.py --signal "Abacaxi" --formato holistic
"""

import argparse
import csv
import io
import json
import logging
import os
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# ════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ════════════════════════════════════════════════════════════════════════════


def _stdout_utf8_stream():
    """Stream stdout em UTF-8 (o console do Windows não assume isso sozinho)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        return sys.stdout
    except Exception:
        pass
    try:
        return io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        return sys.stdout


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("importar_vlibrasil_holistic.log", encoding="utf-8"),
        logging.StreamHandler(_stdout_utf8_stream()),
    ],
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
#  CONFIGURAÇÕES
# ════════════════════════════════════════════════════════════════════════════

BASE_DIR = Path(os.environ.get("LIBRAS_BASE_DIR", Path(__file__).resolve().parent)).resolve()
DIR_MODELOS = BASE_DIR / "modelos"
HOLISTIC_MODEL = DIR_MODELOS / "holistic_landmarker.task"

HOLISTIC_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/holistic_landmarker/"
    "holistic_landmarker/float16/latest/holistic_landmarker.task"
)

# --- Formato compatível com libras_recognizer.py (não mexer) ---------------
FEATURES_PER_HAND = 21 * 3          # 63
TOTAL_FEATURES = FEATURES_PER_HAND * 2   # 126

# --- Formato holistic ------------------------------------------------------
POSE_LANDMARKS = 33
POSE_FEATURES = POSE_LANDMARKS * 4       # x, y, z, visibility

# Confianças alinhadas com libras_recognizer.py / importar_dataset_libras.py
MP_DET_CONF = 0.7
MP_TRK_CONF = 0.5

# libras_recognizer.py descarta sequências com menos que isto
MIN_DYNAMIC_FRAMES = 8

# Fração mínima de frames com pelo menos uma mão visível para o vídeo valer
MIN_FRACAO_COM_MAO = 0.30

MAX_FRAMES_PADRAO = 300
DATA_FORMAT_VERSION = "3.0-holistic"


def _indices_face_expressivos() -> list[int]:
    """Índices faciais relevantes para Libras, derivados da própria MediaPipe.

    Preferimos derivar da biblioteca a cravar uma lista mágica no código: se a
    MediaPipe mudar a topologia, isto acompanha, e no TCC a escolha fica
    justificável ("boca, olhos, sobrancelhas e nariz") em vez de arbitrária.
    São as regiões que carregam marcação gramatical em Libras — as 478 do
    FaceMesh inteiro só inflariam o vetor com contorno de rosto e íris.
    """
    grupos = (
        "FACE_LANDMARKS_LIPS",
        "FACE_LANDMARKS_LEFT_EYE",
        "FACE_LANDMARKS_RIGHT_EYE",
        "FACE_LANDMARKS_LEFT_EYEBROW",
        "FACE_LANDMARKS_RIGHT_EYEBROW",
        "FACE_LANDMARKS_NOSE",
    )
    conexoes = vision.FaceLandmarksConnections
    indices: set[int] = set()
    for nome in grupos:
        for conexao in getattr(conexoes, nome):
            indices.add(conexao.start)
            indices.add(conexao.end)
    return sorted(indices)


FACE_INDICES = _indices_face_expressivos()
FACE_FEATURES = len(FACE_INDICES) * 3

TOTAL_FEATURES_HOLISTIC = TOTAL_FEATURES + POSE_FEATURES + FACE_FEATURES

# ════════════════════════════════════════════════════════════════════════════
#  UTILIDADES
# ════════════════════════════════════════════════════════════════════════════


def normalizar_sinal(sinal: str) -> str:
    """Idêntico ao de importar_dataset_libras.py — as pastas têm que bater."""
    return sinal.strip().lower().replace(" ", "_").replace("(", "").replace(")", "")


def baixar_modelo_holistic(destino: Path = HOLISTIC_MODEL) -> Path:
    """Baixa holistic_landmarker.task na primeira execução (~13 MB)."""
    if destino.exists() and destino.stat().st_size > 0:
        return destino

    destino.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Baixando modelo Holistic (~13 MB) para {destino}...")
    temporario = destino.with_suffix(".task.parcial")
    try:
        urllib.request.urlretrieve(HOLISTIC_MODEL_URL, temporario)
        temporario.replace(destino)
    except Exception as erro:
        temporario.unlink(missing_ok=True)
        raise RuntimeError(
            f"Falha ao baixar o modelo Holistic de {HOLISTIC_MODEL_URL}: {erro}\n"
            f"Baixe manualmente e salve em: {destino}"
        ) from erro

    logger.info(f"OK: modelo salvo ({destino.stat().st_size / 1_048_576:.1f} MB)")
    return destino


# ════════════════════════════════════════════════════════════════════════════
#  EXTRAÇÃO
# ════════════════════════════════════════════════════════════════════════════


def _normalizar_mao(pontos: np.ndarray) -> np.ndarray:
    """Centra no pulso e escala pelo maior desvio.

    Exatamente a normalização de libras_recognizer.py — mudar aqui invalida
    os modelos já treinados.
    """
    pontos = pontos - pontos[0]
    maximo = np.max(np.abs(pontos))
    if maximo > 0:
        pontos = pontos / maximo
    return pontos


class ExtratorHolistic:
    """Envolve o HolisticLandmarker e monta os vetores de features."""

    def __init__(self, model_path: Path | None = None):
        caminho = Path(model_path) if model_path else baixar_modelo_holistic()
        if not caminho.exists():
            raise FileNotFoundError(f"Modelo Holistic não encontrado: {caminho}")

        opcoes = vision.HolisticLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(caminho)),
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=MP_DET_CONF,
            min_pose_landmarks_confidence=MP_TRK_CONF,
            min_hand_landmarks_confidence=MP_TRK_CONF,
        )
        self.detector = vision.HolisticLandmarker.create_from_options(opcoes)

    def processar(self, frame_bgr: np.ndarray, timestamp_ms: int):
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        imagem = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        return self.detector.detect_for_video(imagem, timestamp_ms)

    # -- vetor compatível (126) --------------------------------------------

    @staticmethod
    def features_maos(resultado, slots_por_lado: bool = True) -> tuple[np.ndarray, bool]:
        """Vetor de 126 features. Devolve (features, alguma_mao_detectada).

        Com `slots_por_lado`, o slot 0 é SEMPRE a mão esquerda e o slot 1 a
        direita. É a correção do problema que o HandLandmarker tem: lá o slot
        depende da ordem em que as mãos foram detectadas, então a mesma classe
        gera vetores com as mãos trocadas entre uma amostra e outra.
        """
        features = np.zeros(TOTAL_FEATURES, dtype=np.float32)
        esquerda = getattr(resultado, "left_hand_landmarks", None)
        direita = getattr(resultado, "right_hand_landmarks", None)

        if slots_por_lado:
            maos = [esquerda, direita]
        else:
            # Modo legado: preenche na ordem em que aparecem (compatível com
            # datasets já importados pelo script antigo).
            maos = [m for m in (esquerda, direita) if m]
            maos += [None] * (2 - len(maos))

        detectou = False
        for slot, mao in enumerate(maos[:2]):
            if not mao:
                continue
            detectou = True
            pontos = np.array([[lm.x, lm.y, lm.z] for lm in mao], dtype=np.float32)
            inicio = slot * FEATURES_PER_HAND
            features[inicio : inicio + FEATURES_PER_HAND] = _normalizar_mao(pontos).flatten()

        return features, detectou

    # -- vetor holistic (606) ----------------------------------------------

    @staticmethod
    def features_pose(resultado) -> np.ndarray:
        """33 landmarks x (x, y, z, visibility), centrados no meio dos ombros.

        A escala é a distância entre os ombros, o que torna o vetor
        aproximadamente invariante ao tamanho da pessoa e à distância dela
        para a câmera — importante porque o V-LIBRASIL tem intérpretes
        diferentes, gravados em enquadramentos diferentes.
        """
        features = np.zeros(POSE_FEATURES, dtype=np.float32)
        pose = getattr(resultado, "pose_landmarks", None)
        if not pose:
            return features

        pontos = np.array([[lm.x, lm.y, lm.z] for lm in pose], dtype=np.float32)
        visibilidade = np.array(
            [getattr(lm, "visibility", 0.0) or 0.0 for lm in pose], dtype=np.float32
        )

        # 11 e 12 são os ombros no esquema de 33 pontos da MediaPipe.
        if len(pontos) > 12:
            centro = (pontos[11] + pontos[12]) / 2.0
            escala = float(np.linalg.norm(pontos[11] - pontos[12]))
        else:
            centro = pontos.mean(axis=0)
            escala = 0.0

        pontos = pontos - centro
        if escala > 1e-6:
            pontos = pontos / escala

        features[: POSE_LANDMARKS * 3] = pontos[:POSE_LANDMARKS].flatten()
        features[POSE_LANDMARKS * 3 :] = visibilidade[:POSE_LANDMARKS]
        return features

    @staticmethod
    def features_face(resultado) -> np.ndarray:
        """Subconjunto expressivo do rosto, centrado e escalado pela face."""
        features = np.zeros(FACE_FEATURES, dtype=np.float32)
        face = getattr(resultado, "face_landmarks", None)
        if not face:
            return features

        pontos_todos = np.array([[lm.x, lm.y, lm.z] for lm in face], dtype=np.float32)
        if len(pontos_todos) <= max(FACE_INDICES):
            return features

        pontos = pontos_todos[FACE_INDICES]
        centro = pontos.mean(axis=0)
        pontos = pontos - centro
        escala = float(np.max(np.abs(pontos)))
        if escala > 1e-6:
            pontos = pontos / escala

        features[:] = pontos.flatten()
        return features

    def features_holistic(self, resultado, slots_por_lado: bool = True) -> np.ndarray:
        maos, _ = self.features_maos(resultado, slots_por_lado)
        return np.concatenate(
            [maos, self.features_pose(resultado), self.features_face(resultado)]
        ).astype(np.float32)

    def liberar(self) -> None:
        try:
            self.detector.close()
        except Exception:
            pass


def _recortar_trecho_ativo(
    sequencias: dict[str, list], mao_por_frame: list[bool]
) -> tuple[dict[str, list], int, int]:
    """Corta frames sem mão no começo e no fim do vídeo.

    Vídeos do V-LIBRASIL costumam abrir e fechar com o intérprete parado. Esses
    frames mortos não só poluem a sequência como interagem mal com o
    `_pad_or_crop_sequence` do libras_recognizer.py, que fica com os ÚLTIMOS 30
    frames quando a sequência é maior — ou seja, sem o recorte ele pode acabar
    treinando na pose de descanso em vez de no sinal.
    """
    if not any(mao_por_frame):
        return sequencias, 0, 0

    primeiro = mao_por_frame.index(True)
    ultimo = len(mao_por_frame) - 1 - mao_por_frame[::-1].index(True)
    recortadas = {k: v[primeiro : ultimo + 1] for k, v in sequencias.items()}
    return recortadas, primeiro, len(mao_por_frame) - 1 - ultimo


def _reamostrar(sequencia: np.ndarray, alvo: int) -> np.ndarray:
    """Reamostra a sequência para `alvo` frames por interpolação linear."""
    n = len(sequencia)
    if n == alvo or n == 0:
        return sequencia
    origem = np.linspace(0.0, 1.0, num=n)
    destino = np.linspace(0.0, 1.0, num=alvo)
    saida = np.empty((alvo, sequencia.shape[1]), dtype=np.float32)
    for coluna in range(sequencia.shape[1]):
        saida[:, coluna] = np.interp(destino, origem, sequencia[:, coluna])
    return saida


def extrair_de_video(
    video_path: str,
    extrator: ExtratorHolistic,
    formatos: set[str],
    max_frames: int = MAX_FRAMES_PADRAO,
    slots_por_lado: bool = True,
    recortar_ativo: bool = True,
    reamostrar_para: int = 0,
) -> tuple[dict[str, np.ndarray] | None, dict]:
    """Extrai as sequências de um vídeo.

    Returns:
        (sequencias, qualidade) — `sequencias` mapeia formato → array
        (n_frames, n_features), ou None se o vídeo for inaproveitável.
    """
    qualidade = {
        "frames_lidos": 0,
        "frames_com_mao": 0,
        "fracao_bruta_com_mao": 0.0,
        "fracao_com_mao": 0.0,
        "frames_cortados_inicio": 0,
        "frames_cortados_fim": 0,
        "motivo_descarte": None,
    }

    captura = None
    try:
        captura = cv2.VideoCapture(video_path)
        if not captura.isOpened():
            qualidade["motivo_descarte"] = "não foi possível abrir o vídeo"
            return None, qualidade

        fps = captura.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(captura.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if max_frames:
            total = min(total, max_frames) if total else max_frames

        sequencias: dict[str, list] = {formato: [] for formato in formatos}
        mao_por_frame: list[bool] = []
        indice = 0
        timestamp_ms = -1

        while captura.isOpened() and indice < total:
            ok, frame = captura.read()
            if not ok:
                break

            # O RunningMode.VIDEO rejeita timestamp repetido com ValueError, o
            # que derrubaria o vídeo inteiro. Com fps alto (ou fps inválido no
            # cabeçalho, que acontece) o arredondamento para ms repete, então
            # forçamos o avanço em vez de confiar na conta.
            timestamp_ms = max(int(indice * 1000 / fps), timestamp_ms + 1)
            resultado = extrator.processar(frame, timestamp_ms)

            maos, detectou = extrator.features_maos(resultado, slots_por_lado)
            mao_por_frame.append(detectou)

            if "compativel" in sequencias:
                sequencias["compativel"].append(maos)
            if "holistic" in sequencias:
                sequencias["holistic"].append(
                    np.concatenate(
                        [
                            maos,
                            extrator.features_pose(resultado),
                            extrator.features_face(resultado),
                        ]
                    ).astype(np.float32)
                )

            indice += 1

        qualidade["frames_lidos"] = indice
        qualidade["frames_com_mao"] = sum(mao_por_frame)

        if indice == 0:
            qualidade["motivo_descarte"] = "nenhum frame lido"
            return None, qualidade

        qualidade["fracao_bruta_com_mao"] = round(qualidade["frames_com_mao"] / indice, 4)

        if not any(mao_por_frame):
            qualidade["fracao_com_mao"] = 0.0
            qualidade["motivo_descarte"] = "nenhuma mão detectada no vídeo"
            return None, qualidade

        # Recortamos ANTES de julgar a qualidade: quase todo vídeo do
        # V-LIBRASIL abre e fecha com o intérprete parado, e contar esses
        # frames mortos reprovaria vídeos perfeitamente bons só por causa do
        # tamanho da abertura.
        if recortar_ativo:
            sequencias, cortou_inicio, cortou_fim = _recortar_trecho_ativo(
                sequencias, mao_por_frame
            )
            qualidade["frames_cortados_inicio"] = cortou_inicio
            qualidade["frames_cortados_fim"] = cortou_fim
            fim = len(mao_por_frame) - cortou_fim
            mao_por_frame = mao_por_frame[cortou_inicio:fim]

        fracao = sum(mao_por_frame) / len(mao_por_frame)
        qualidade["fracao_com_mao"] = round(fracao, 4)

        if fracao < MIN_FRACAO_COM_MAO:
            qualidade["motivo_descarte"] = (
                f"mão visível em apenas {fracao:.0%} do trecho ativo "
                f"(mínimo {MIN_FRACAO_COM_MAO:.0%})"
            )
            return None, qualidade

        arrays = {
            formato: np.array(valores, dtype=np.float32)
            for formato, valores in sequencias.items()
        }

        restantes = len(next(iter(arrays.values())))
        if restantes < MIN_DYNAMIC_FRAMES:
            qualidade["motivo_descarte"] = (
                f"{restantes} frames úteis (mínimo {MIN_DYNAMIC_FRAMES})"
            )
            return None, qualidade

        if reamostrar_para:
            arrays = {k: _reamostrar(v, reamostrar_para) for k, v in arrays.items()}

        return arrays, qualidade

    except Exception as erro:
        qualidade["motivo_descarte"] = f"erro: {erro}"
        logger.error(f"Erro ao processar {video_path}: {erro}")
        return None, qualidade
    finally:
        if captura is not None:
            captura.release()


# ════════════════════════════════════════════════════════════════════════════
#  ANOTAÇÕES
# ════════════════════════════════════════════════════════════════════════════

COLUNAS_VLIBRASIL = [
    "video_id", "video_name", "class", "user_id",
    "width", "height", "fps", "url_page", "url_download",
]


def _detectar_dialeto_csv(caminho: str) -> tuple[str, bool]:
    with open(caminho, "r", encoding="utf-8-sig", errors="replace", newline="") as arquivo:
        amostra = arquivo.read(8192)
    try:
        sniffer = csv.Sniffer()
        return sniffer.sniff(amostra, delimiters=",;\t|").delimiter, sniffer.has_header(amostra)
    except Exception:
        logger.warning("Formato do CSV não detectado; assumindo ',' com cabeçalho.")
        return ",", True


def carregar_anotacoes(caminho: str) -> pd.DataFrame:
    """Carrega o CSV/Excel de anotações do V-LIBRASIL.

    Mantém `user_id` (o sinalizante) — é ele que permite o split por pessoa
    mais adiante.
    """
    if caminho.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(caminho)
    else:
        separador, tem_cabecalho = _detectar_dialeto_csv(caminho)
        df = pd.read_csv(
            caminho,
            encoding="utf-8-sig",
            sep=separador,
            engine="python",
            header=0 if tem_cabecalho else None,
        )
        if not tem_cabecalho and df.shape[1] == len(COLUNAS_VLIBRASIL):
            df.columns = COLUNAS_VLIBRASIL

    df.columns = [str(c).strip().lstrip("﻿") for c in df.columns]
    df = df.dropna(how="all")

    colunas = {str(c).strip().lower(): c for c in df.columns}
    faltando = [c for c in ("video_name", "class") if c not in colunas]
    if faltando:
        raise ValueError(
            f"Colunas obrigatórias ausentes: {faltando}. Encontradas: {list(df.columns)}"
        )

    renomear = {colunas["video_name"]: "video_name", colunas["class"]: "class"}
    if "user_id" in colunas:
        renomear[colunas["user_id"]] = "user_id"
    df = df.rename(columns=renomear)

    if "user_id" not in df.columns:
        logger.warning(
            "Coluna 'user_id' ausente: o manifesto sairá sem sinalizante e o "
            "split por pessoa não será possível."
        )
        df["user_id"] = "desconhecido"

    df = df[df["video_name"].notna() & df["class"].notna()]
    for coluna in ("video_name", "class", "user_id"):
        df[coluna] = df[coluna].astype(str).str.strip()

    return df[df["video_name"].ne("") & df["class"].ne("")].reset_index(drop=True)


# ════════════════════════════════════════════════════════════════════════════
#  GRAVAÇÃO
# ════════════════════════════════════════════════════════════════════════════

SUBPASTA_POR_FORMATO = {"compativel": "dinamicos", "holistic": "holistic"}


def caminho_saida(output_dir: Path, formato: str, sinal: str, indice: int) -> Path:
    """dados_libras/<dinamicos|holistic>/<sinal>/public/NNN.npy

    A pasta `public` não é decorativa: o `_detectar_origem_arquivo` do
    libras_recognizer.py usa o nome dela para marcar a amostra como pública
    (em oposição às gravadas na webcam, que vão para `local`).
    """
    pasta = output_dir / SUBPASTA_POR_FORMATO[formato] / normalizar_sinal(sinal) / "public"
    return pasta / f"{indice:03d}.npy"


def salvar(sequencia: np.ndarray, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(destino), sequencia)


def escrever_manifesto(registros: list[dict], output_dir: Path) -> Path:
    """Grava o manifesto que liga cada .npy ao seu sinalizante.

    É o artefato que viabiliza `GroupShuffleSplit(groups=user_id)` no treino.
    Sem ele, o mesmo intérprete aparece no treino e no teste e a acurácia sobe
    sem significar nada.
    """
    destino = output_dir / "manifest.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    campos = [
        "arquivo", "formato", "sinal", "sinal_normalizado", "user_id",
        "video_name", "n_frames", "n_features", "fracao_com_mao",
    ]
    with open(destino, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        for registro in registros:
            escritor.writerow({campo: registro.get(campo, "") for campo in campos})
    return destino


# ════════════════════════════════════════════════════════════════════════════
#  PIPELINE
# ════════════════════════════════════════════════════════════════════════════


def processar_dataset(
    annotations_file: str,
    videos_dir: str,
    output_dir: str,
    formatos: set[str],
    skip_existing: bool = True,
    max_videos_per_signal: int | None = None,
    target_signals: list[str] | None = None,
    limite_sinais: int | None = None,
    max_frames: int = MAX_FRAMES_PADRAO,
    slots_por_lado: bool = True,
    recortar_ativo: bool = True,
    reamostrar_para: int = 0,
    isolar_por_video: bool = True,
    model_path: Path | None = None,
) -> dict | None:
    inicio = time.time()

    logger.info("=" * 78)
    logger.info("IMPORTADOR V-LIBRASIL → HOLISTIC")
    logger.info("=" * 78)
    logger.info(f"Formatos: {', '.join(sorted(formatos))}")
    logger.info(f"Features: compativel={TOTAL_FEATURES} | holistic={TOTAL_FEATURES_HOLISTIC}")
    logger.info(f"  (mãos {TOTAL_FEATURES} + pose {POSE_FEATURES} + face {FACE_FEATURES})")

    caminho_anotacoes = Path(annotations_file)
    if not caminho_anotacoes.is_absolute() and not caminho_anotacoes.exists():
        candidato = Path(videos_dir) / caminho_anotacoes
        if candidato.exists():
            caminho_anotacoes = candidato

    if not caminho_anotacoes.exists():
        logger.error(f"ERRO: anotações não encontradas: {caminho_anotacoes}")
        return None
    if not Path(videos_dir).exists():
        logger.error(f"ERRO: pasta de vídeos não encontrada: {videos_dir}")
        return None

    try:
        df = carregar_anotacoes(str(caminho_anotacoes))
    except Exception as erro:
        logger.error(f"ERRO ao carregar anotações: {erro}")
        return None

    logger.info(f"OK: {len(df)} anotações | {df['class'].nunique()} sinais únicos")
    logger.info(f"OK: {df['user_id'].nunique()} sinalizantes distintos")

    por_sinal: dict[str, list[dict]] = defaultdict(list)
    for _, linha in df.iterrows():
        por_sinal[linha["class"]].append(
            {"video_name": linha["video_name"], "user_id": linha["user_id"]}
        )

    if target_signals:
        alvos = {s.strip().lower() for s in target_signals}
        por_sinal = {k: v for k, v in por_sinal.items() if k.strip().lower() in alvos}
        logger.info(f"FILTRO: {len(por_sinal)} sinais após filtro por nome")

    if limite_sinais:
        por_sinal = dict(sorted(por_sinal.items())[:limite_sinais])
        logger.info(f"FILTRO: limitado a {len(por_sinal)} sinais")

    if not por_sinal:
        logger.error("ERRO: nenhuma amostra após os filtros.")
        return None

    saida = Path(output_dir)
    saida.mkdir(parents=True, exist_ok=True)

    caminho_modelo = Path(model_path) if model_path else baixar_modelo_holistic()

    # O RunningMode.VIDEO mantém estado de tracking entre frames. Isso é bom
    # DENTRO de um vídeo (suaviza e acelera), mas entre vídeos diferentes o
    # estado do último frame do vídeo A enviesa os primeiros frames do vídeo B.
    # Por padrão isolamos cada vídeo num detector próprio: custa ~1,8s por
    # vídeo contra ~0,27s por frame, ou seja ~10% num vídeo típico, e em troca
    # a extração fica determinística e independente da ordem de importação.
    extrator_persistente = None
    if not isolar_por_video:
        logger.info("Carregando HolisticLandmarker (reusado entre vídeos)...")
        extrator_persistente = ExtratorHolistic(caminho_modelo)
    else:
        logger.info("Detector isolado por vídeo (sem vazamento de tracking)")
    logger.info("")

    estatisticas = {
        "versao_formato": DATA_FORMAT_VERSION,
        "data": datetime.now().isoformat(timespec="seconds"),
        "formatos": sorted(formatos),
        "total_sinais": len(por_sinal),
        "total_videos": sum(len(v) for v in por_sinal.values()),
        "videos_processados": 0,
        "videos_falhados": 0,
        "videos_pulados": 0,
        "sinalizantes": sorted({v["user_id"] for vs in por_sinal.values() for v in vs}),
        "descartes": [],
        "features": {
            "compativel": TOTAL_FEATURES,
            "holistic": TOTAL_FEATURES_HOLISTIC,
            "pose": POSE_FEATURES,
            "face": FACE_FEATURES,
            "face_indices": FACE_INDICES,
        },
        "parametros": {
            "slots_por_lado": slots_por_lado,
            "recortar_ativo": recortar_ativo,
            "reamostrar_para": reamostrar_para,
            "max_frames": max_frames,
            "min_fracao_com_mao": MIN_FRACAO_COM_MAO,
            "isolar_por_video": isolar_por_video,
        },
    }
    manifesto: list[dict] = []

    try:
        for posicao, (sinal, videos) in enumerate(sorted(por_sinal.items()), start=1):
            if max_videos_per_signal:
                videos = videos[:max_videos_per_signal]

            logger.info(f"[{posicao}/{len(por_sinal)}] {sinal} ({len(videos)} vídeos)")

            for indice, info in enumerate(videos):
                nome = info["video_name"]
                caminho_video = Path(videos_dir) / nome

                destinos = {
                    formato: caminho_saida(saida, formato, sinal, indice)
                    for formato in formatos
                }

                if skip_existing and all(d.exists() for d in destinos.values()):
                    estatisticas["videos_pulados"] += 1
                    continue

                if not caminho_video.exists():
                    logger.warning(f"  AUSENTE: {nome}")
                    estatisticas["videos_falhados"] += 1
                    estatisticas["descartes"].append(
                        {"video": nome, "sinal": sinal, "motivo": "arquivo não encontrado"}
                    )
                    continue

                extrator = extrator_persistente or ExtratorHolistic(caminho_modelo)
                try:
                    sequencias, qualidade = extrair_de_video(
                        str(caminho_video),
                        extrator,
                        formatos,
                        max_frames=max_frames,
                        slots_por_lado=slots_por_lado,
                        recortar_ativo=recortar_ativo,
                        reamostrar_para=reamostrar_para,
                    )
                finally:
                    if extrator_persistente is None:
                        extrator.liberar()

                if sequencias is None:
                    logger.warning(f"  DESCARTADO: {nome} — {qualidade['motivo_descarte']}")
                    estatisticas["videos_falhados"] += 1
                    estatisticas["descartes"].append(
                        {"video": nome, "sinal": sinal, "motivo": qualidade["motivo_descarte"]}
                    )
                    continue

                for formato, sequencia in sequencias.items():
                    destino = destinos[formato]
                    salvar(sequencia, destino)
                    manifesto.append(
                        {
                            "arquivo": str(destino.relative_to(saida)),
                            "formato": formato,
                            "sinal": sinal,
                            "sinal_normalizado": normalizar_sinal(sinal),
                            "user_id": info["user_id"],
                            "video_name": nome,
                            "n_frames": len(sequencia),
                            "n_features": sequencia.shape[1],
                            "fracao_com_mao": qualidade["fracao_com_mao"],
                        }
                    )

                estatisticas["videos_processados"] += 1
                logger.info(
                    f"  OK: {nome} → {len(next(iter(sequencias.values())))} frames "
                    f"(mão em {qualidade['fracao_com_mao']:.0%})"
                )
    finally:
        if extrator_persistente is not None:
            extrator_persistente.liberar()

    estatisticas["tempo_total_s"] = round(time.time() - inicio, 2)

    caminho_manifesto = escrever_manifesto(manifesto, saida)
    caminho_stats = saida / "importacao_holistic_stats.json"
    with open(caminho_stats, "w", encoding="utf-8") as arquivo:
        json.dump(estatisticas, arquivo, ensure_ascii=False, indent=2)

    logger.info("\n" + "=" * 78)
    logger.info("RESUMO")
    logger.info("=" * 78)
    logger.info(f"Processados: {estatisticas['videos_processados']}")
    logger.info(f"Falhados:    {estatisticas['videos_falhados']}")
    logger.info(f"Pulados:     {estatisticas['videos_pulados']}")
    logger.info(f"Sinalizantes:{len(estatisticas['sinalizantes'])}")
    logger.info(f"Tempo:       {estatisticas['tempo_total_s']}s")
    logger.info(f"Manifesto:   {caminho_manifesto}")
    logger.info(f"Estatísticas:{caminho_stats}")
    logger.info("=" * 78)

    return estatisticas


# ════════════════════════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════════════════════════


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Importa o V-LIBRASIL extraindo landmarks com MediaPipe Holistic.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--annotations", default="annotations.csv", help="CSV/Excel de anotações")
    parser.add_argument("--videos-dir", default="data", help="Pasta com os vídeos")
    parser.add_argument("--output-dir", default=str(BASE_DIR / "dados_libras"), help="Pasta de saída")
    parser.add_argument(
        "--formato",
        choices=["compativel", "holistic", "ambos"],
        default="ambos",
        help="compativel=126 features (libras_recognizer.py); holistic=vetor completo; ambos=os dois (padrão)",
    )
    parser.add_argument("--signal", action="append", help="Processar apenas este sinal (repetível)")
    parser.add_argument("--limite-sinais", type=int, help="Processar só os N primeiros sinais")
    parser.add_argument("--max-videos-per-signal", type=int, help="Máximo de vídeos por sinal")
    parser.add_argument("--max-frames", type=int, default=MAX_FRAMES_PADRAO, help="Frames por vídeo")
    parser.add_argument(
        "--reamostrar", type=int, default=0,
        help="Reamostrar para N frames (0 = manter duração real, recomendado)",
    )
    parser.add_argument(
        "--slots", choices=["por-lado", "ordem-deteccao"], default="por-lado",
        help="por-lado: slot 0=esquerda, 1=direita (estável). ordem-deteccao: legado",
    )
    parser.add_argument("--sem-recorte-ativo", action="store_true", help="Não cortar frames sem mão")
    parser.add_argument(
        "--reusar-detector", action="store_true",
        help="Reusar um detector entre vídeos (~10%% mais rápido, mas o tracking vaza entre vídeos)",
    )
    parser.add_argument("--no-skip-existing", action="store_true", help="Reprocessar já existentes")
    parser.add_argument("--model", help="Caminho para holistic_landmarker.task")
    args = parser.parse_args()

    formatos = {"compativel", "holistic"} if args.formato == "ambos" else {args.formato}

    resultado = processar_dataset(
        annotations_file=args.annotations,
        videos_dir=args.videos_dir,
        output_dir=args.output_dir,
        formatos=formatos,
        skip_existing=not args.no_skip_existing,
        max_videos_per_signal=args.max_videos_per_signal,
        target_signals=args.signal,
        limite_sinais=args.limite_sinais,
        max_frames=args.max_frames,
        slots_por_lado=args.slots == "por-lado",
        recortar_ativo=not args.sem_recorte_ativo,
        reamostrar_para=args.reamostrar,
        isolar_por_video=not args.reusar_detector,
        model_path=Path(args.model) if args.model else None,
    )
    return 0 if resultado else 1


if __name__ == "__main__":
    sys.exit(main())
