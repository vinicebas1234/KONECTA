"""Extração REAL de landmarks de mão via MediaPipe Tasks (`HandLandmarker`).

Ciclo 1 do Libras Learning Agent. Existe porque `KONECTA_V3/vision_lab/landmarks.py`
nunca chamou o MediaPipe de verdade (`extract` devolvia `np.random.randn(228)` —
ver `KONECTA_V3/ANALISE_E_PLANO_GAUNTLET.md`, seção 5.10). Este módulo é a prova
de que dá pra fazer diferente: `test_vision_hand_landmarks.py` tem um teste de
determinismo desenhado especificamente para pegar essa regressão de novo.

API usada: `mediapipe.tasks.python.vision` (`HandLandmarker`), não
`mp.solutions.hands` — essa não existe mais no mediapipe instalado neste
ambiente (confirmado: `hasattr(mediapipe, 'solutions')` é `False`). O padrão
de uso (`RunningMode.VIDEO`, timestamps crescentes) segue o mesmo já usado em
`app_central/providers/signlab_sinais.py`, só que reimplementado aqui — nada é
importado de lá, por isolamento.

Escopo deliberado: só mãos (esquerda + direita), só o essencial pra provar que
o motor roda de verdade. Pose e face ficam para um ciclo futuro.
"""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple, Union
from urllib.error import URLError

import cv2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modelo MediaPipe: download automático com cache local (fora do git)
# ---------------------------------------------------------------------------

# URL oficial (documentação MediaPipe Tasks — Hand Landmarker, variante
# float16, a única listada na página de modelos). Confirmado por HTTP HEAD
# nesta máquina: 7.819.105 bytes, idêntico byte a byte à versão pinada
# ".../float16/1/hand_landmarker.task" (mesmo md5 FTGEMOo4UWcP6ZFBFqnPrQ==).
HAND_LANDMARKER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
HAND_LANDMARKER_MODEL_PATH = ASSETS_DIR / "hand_landmarker.task"


def ensure_hand_landmarker_model(
    dest: Path = HAND_LANDMARKER_MODEL_PATH, url: str = HAND_LANDMARKER_MODEL_URL
) -> Path:
    """Garante que o `.task` do HandLandmarker existe em `dest`, baixando se preciso.

    Cache local simples: se o arquivo já existe e não está vazio, não baixa de
    novo. Nunca falha silenciosamente — sem internet ou URL fora do ar levanta
    `RuntimeError` explicando o que fazer.
    """
    if dest.is_file() and dest.stat().st_size > 0:
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Baixando modelo MediaPipe HandLandmarker de %s para %s", url, dest)
    try:
        urllib.request.urlretrieve(url, dest)
    except (URLError, OSError) as erro:
        if dest.exists():
            dest.unlink()  # não deixa arquivo parcial/corrompido para trás
        raise RuntimeError(
            f"Falha ao baixar o modelo MediaPipe HandLandmarker de {url}: {erro}. "
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
class HandDetection:
    """Uma mão detectada num frame: 21 pontos (x, y, z) + handedness."""

    label: str  # "Left" ou "Right", conforme o MediaPipe devolve
    score: float  # confiança do handedness, 0..1
    points: Tuple[Point3D, ...]  # 21 pontos normalizados (x, y, z)


@dataclass(frozen=True)
class HandFrameLandmarks:
    """Landmarks de mão de um frame do vídeo."""

    frame_id: int
    timestamp_ms: int
    hands: Tuple[HandDetection, ...]

    @property
    def detected(self) -> bool:
        """Verdadeiro se pelo menos uma mão foi detectada neste frame."""
        return len(self.hands) > 0


@dataclass(frozen=True)
class HandExtractionResult:
    """Resultado da extração de um vídeo inteiro."""

    frames: Tuple[HandFrameLandmarks, ...]
    fps: float
    frame_count: int
    detection_rate: float  # fração de frames com >=1 mão detectada


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------


def _build_detector(model_path: Path):
    import mediapipe as mp
    from mediapipe.tasks.python import vision as mp_vision
    from mediapipe.tasks.python.core.base_options import BaseOptions

    detector = mp_vision.HandLandmarker.create_from_options(
        mp_vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.5,
        )
    )
    return mp, detector


def extract_hand_landmarks(
    video_path: Union[str, Path],
    model_path: Optional[Union[str, Path]] = None,
) -> HandExtractionResult:
    """Abre `video_path` via OpenCV e roda o HandLandmarker frame a frame.

    Modo `VIDEO`: timestamp em ms calculado a partir do FPS real do vídeo,
    estritamente crescente (exigência da própria API — ver
    `HandLandmarker.detect_for_video`). Levanta erro claro se o vídeo não
    existir ou não abrir; nunca falha em silêncio.
    """
    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(f"Vídeo não encontrado: {path}")

    resolved_model_path = Path(model_path) if model_path else ensure_hand_landmarker_model()

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Não foi possível abrir o vídeo (codec/arquivo inválido?): {path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 30.0  # fallback conservador: alguns containers não reportam FPS

    mp, detector = _build_detector(resolved_model_path)

    frames: list[HandFrameLandmarks] = []
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

            hands = tuple(
                HandDetection(
                    label=handedness[0].category_name,
                    score=float(handedness[0].score),
                    points=tuple((float(p.x), float(p.y), float(p.z)) for p in landmarks),
                )
                for landmarks, handedness in zip(result.hand_landmarks, result.handedness)
            )
            frames.append(
                HandFrameLandmarks(frame_id=frame_id, timestamp_ms=timestamp_ms, hands=hands)
            )
            frame_id += 1
    finally:
        cap.release()
        detector.close()

    frame_count = len(frames)
    detected = sum(1 for f in frames if f.detected)
    detection_rate = (detected / frame_count) if frame_count else 0.0

    logger.info(
        "Extração concluída: %s (%d frames, %.1f fps, detection_rate=%.3f)",
        path.name,
        frame_count,
        fps,
        detection_rate,
    )
    return HandExtractionResult(
        frames=tuple(frames), fps=fps, frame_count=frame_count, detection_rate=detection_rate
    )
