"""Extração REAL de landmarks de POSE via MediaPipe Tasks (`PoseLandmarker`).

Ciclo 13 do Libras Learning Agent. Mesmo padrão do Ciclo 1 (`hand_landmarks.py`)
mas para o corpo inteiro (ombros, cotovelos, punhos, tronco, cabeça) em vez de
mãos: prova que a extração de pose funciona de verdade, como capacidade nova e
isolada — não integrada ao pipeline de treino/DTW existente (`ml/features.py`,
`ml/dtw.py`, `ml/training.py`, `ml/predict.py` continuam exatamente como
estão). Combinar pose com o vetor de 128 features de mão é decisão de um ciclo
futuro, que exige reprocessar o dataset e recalibrar — fora do escopo daqui.

API usada: `mediapipe.tasks.python.vision` (`PoseLandmarker`), mesma família
usada no Ciclo 1 para mãos — já confirmada disponível nesta instalação
(`dir(vision)` lista `PoseLandmarker`, `PoseLandmarkerOptions`,
`PoseLandmarkerResult`, `PoseLandmark`). `RunningMode.VIDEO` com timestamps
crescentes, mesmo padrão de `hand_landmarks.py`.

Escopo deliberado: só pose (33 pontos por pessoa, normalmente 1 pessoa no
vídeo). Face e mãos detalhadas ficam fora — mãos já tem `hand_landmarks.py`.
"""

from __future__ import annotations

import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union
from urllib.error import URLError

import cv2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modelo MediaPipe: download automático com cache local (fora do git)
# ---------------------------------------------------------------------------

# URL oficial (documentação MediaPipe Tasks — Pose Landmarker, confirmada em
# https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker, que
# lista 3 variantes: lite/full/heavy, todas em
# storage.googleapis.com/mediapipe-models/pose_landmarker/<variante>/float16/latest/.
# Testadas as 3 de verdade (baixadas e rodadas) contra um vídeo real do
# V-LIBRASIL (Abacaxi_Articulador1.mp4, 172 frames, pessoa de corpo visível):
# as 3 deram detection_rate=1.000 (nenhuma diferença de detecção nesse vídeo),
# só tempo de inferência mudou — lite 15.9ms/frame, full 20.9ms/frame, heavy
# 51.5ms/frame (2.5x mais lenta que full sem ganho de detecção observado).
# Escolhida "full": meio-termo padrão da própria nomeação da MediaPipe (mais
# capaz que lite, sem pagar o custo de heavy), adequada para extração em lote
# (não é tempo real) onde precisão importa mas heavy não se justificou aqui.
POSE_LANDMARKER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
)

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
POSE_LANDMARKER_MODEL_PATH = ASSETS_DIR / "pose_landmarker_full.task"


def ensure_pose_landmarker_model(
    dest: Path = POSE_LANDMARKER_MODEL_PATH, url: str = POSE_LANDMARKER_MODEL_URL
) -> Path:
    """Garante que o `.task` do PoseLandmarker existe em `dest`, baixando se preciso.

    Mesmo cache local simples do Ciclo 1 (`ensure_hand_landmarker_model`): se o
    arquivo já existe e não está vazio, não baixa de novo. Nunca falha em
    silêncio — sem internet ou URL fora do ar levanta `RuntimeError` explicando
    o que fazer.
    """
    if dest.is_file() and dest.stat().st_size > 0:
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Baixando modelo MediaPipe PoseLandmarker de %s para %s", url, dest)
    try:
        urllib.request.urlretrieve(url, dest)
    except (URLError, OSError) as erro:
        if dest.exists():
            dest.unlink()  # não deixa arquivo parcial/corrompido para trás
        raise RuntimeError(
            f"Falha ao baixar o modelo MediaPipe PoseLandmarker de {url}: {erro}. "
            f"Verifique sua conexão com a internet, ou baixe o arquivo manualmente "
            f"e salve em {dest}."
        ) from erro

    if not dest.is_file() or dest.stat().st_size == 0:
        raise RuntimeError(
            f"Download do modelo terminou sem erro mas o arquivo em {dest} está "
            f"ausente ou vazio — algo baixou uma resposta inválida de {url}."
        )
    return dest


# ---------------------------------------------------------------------------
# Estruturas de dados
# ---------------------------------------------------------------------------

Point3D = Tuple[float, float, float]


@dataclass(frozen=True)
class PoseDetection:
    """Uma pose detectada num frame: 33 pontos (x, y, z, visibility, presence)."""

    landmark_index: Tuple[int, ...]  # 0..32, ordem do PoseLandmark do MediaPipe
    points: Tuple[Point3D, ...]  # 33 pontos normalizados (x, y, z)
    visibility: Tuple[float, ...]  # 33 scores: visível vs. ocluído/fora do quadro
    presence: Tuple[float, ...]  # 33 scores: presente na cena ou não


@dataclass(frozen=True)
class PoseFrameLandmarks:
    """Landmarks de pose de um frame do vídeo."""

    frame_id: int
    timestamp_ms: int
    poses: Tuple[PoseDetection, ...]  # normalmente 0 ou 1 pessoa

    @property
    def detected(self) -> bool:
        """Verdadeiro se pelo menos uma pose foi detectada neste frame."""
        return len(self.poses) > 0


@dataclass(frozen=True)
class PoseExtractionResult:
    """Resultado da extração de um vídeo inteiro."""

    frames: Tuple[PoseFrameLandmarks, ...]
    fps: float
    frame_count: int
    detection_rate: float  # fração de frames com >=1 pose detectada


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------


def _build_detector(model_path: Path):
    import mediapipe as mp
    from mediapipe.tasks.python import vision as mp_vision
    from mediapipe.tasks.python.core.base_options import BaseOptions

    detector = mp_vision.PoseLandmarker.create_from_options(
        mp_vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_poses=1,
        )
    )
    return mp, detector


def extract_pose_landmarks(
    video_path: Union[str, Path],
    model_path: Optional[Union[str, Path]] = None,
) -> PoseExtractionResult:
    """Abre `video_path` via OpenCV e roda o PoseLandmarker frame a frame.

    Modo `VIDEO`: timestamp em ms calculado a partir do FPS real do vídeo,
    estritamente crescente (mesma exigência do `HandLandmarker` no Ciclo 1).
    Levanta erro claro se o vídeo não existir ou não abrir; nunca falha em
    silêncio.
    """
    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(f"Vídeo não encontrado: {path}")

    resolved_model_path = Path(model_path) if model_path else ensure_pose_landmarker_model()

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Não foi possível abrir o vídeo (codec/arquivo inválido?): {path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 30.0  # fallback conservador: alguns containers não reportam FPS

    mp, detector = _build_detector(resolved_model_path)

    frames: list[PoseFrameLandmarks] = []
    last_timestamp_ms = -1
    try:
        frame_id = 0
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break

            timestamp_ms = int(round(frame_id * 1000.0 / fps))
            if timestamp_ms <= last_timestamp_ms:
                # FPS alto o bastante para arredondar para o mesmo ms do
                # frame anterior: a API exige estritamente crescente.
                timestamp_ms = last_timestamp_ms + 1
            last_timestamp_ms = timestamp_ms

            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = detector.detect_for_video(mp_image, timestamp_ms)

            poses = tuple(
                PoseDetection(
                    landmark_index=tuple(range(len(landmarks))),
                    points=tuple((float(p.x), float(p.y), float(p.z)) for p in landmarks),
                    visibility=tuple(float(p.visibility) for p in landmarks),
                    presence=tuple(float(p.presence) for p in landmarks),
                )
                for landmarks in result.pose_landmarks
            )
            frames.append(
                PoseFrameLandmarks(frame_id=frame_id, timestamp_ms=timestamp_ms, poses=poses)
            )
            frame_id += 1
    finally:
        cap.release()
        detector.close()

    frame_count = len(frames)
    detected = sum(1 for f in frames if f.detected)
    detection_rate = (detected / frame_count) if frame_count else 0.0

    logger.info(
        "Extração de pose concluída: %s (%d frames, %.1f fps, detection_rate=%.3f)",
        path.name,
        frame_count,
        fps,
        detection_rate,
    )
    return PoseExtractionResult(
        frames=tuple(frames), fps=fps, frame_count=frame_count, detection_rate=detection_rate
    )
