"""Motor KONECTA V3 - reconhecimento de sinais com baixa latência.

Os artefatos de modelo continuam sendo produzidos pelo SIGNLAB.  Este módulo
somente os consome e foi pensado para o caminho quente de vídeo (CPU primeiro).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import cv2
import joblib
import numpy as np

logger = logging.getLogger(__name__)

# Nomes das etapas do perfil de latência (mantidos estáveis para compatibilidade)
STAGE_MODEL_LOAD = "model_load"
STAGE_CACHE_LOOKUP = "cache_lookup"
STAGE_LANDMARKS = "landmarks"
STAGE_INFERENCE = "inference"
PROFILE_STAGES = (STAGE_MODEL_LOAD, STAGE_CACHE_LOOKUP, STAGE_LANDMARKS, STAGE_INFERENCE)

# Features por mão (21 landmarks x {x, y, z})
FEATURE_COUNT = 63


@dataclass
class RecognitionResult:
    """Resultado de reconhecimento de um frame."""

    signal: str
    confidence: float
    latency_ms: float
    landmarks: Optional[list] = None
    model_version: str = "v1"
    status: str = "success"
    error: Optional[str] = None


class MotorBase:
    """Contrato mínimo de um motor de reconhecimento."""

    async def process(self, frame: np.ndarray) -> RecognitionResult:
        """Processa um frame BGR e retorna o resultado de reconhecimento."""
        raise NotImplementedError


class MotorKonectaV3(MotorBase):
    """Classificador primário compatível com modelos MediaPipe/SIGNLAB.

    Modelos e o detector MediaPipe são inicializados apenas quando necessários.
    O detector permanece vivo entre frames, permitindo que o tracking interno do
    MediaPipe substitua detecções completas na maior parte de um vídeo.
    """

    def __init__(self, model_path: str = "models/v1", landmark_cache_size: int = 32):
        self.model_path = Path(model_path)
        self.classifier: Any = None
        self.sequence_model: Any = None  # reservado para o fluxo de sequência
        self.metadata: Dict[str, Any] = {}
        self._models_loaded = False
        self._hands: Any = None
        self._mediapipe_unavailable = False
        self._landmark_cache: "OrderedDict[Optional[tuple], Optional[np.ndarray]]" = OrderedDict()
        self._landmark_cache_size = max(0, int(landmark_cache_size))
        self._label_map: Dict[str, str] = {}
        self._last_profile: Dict[str, float] = {}
        self.performance_stats: Dict[str, Any] = {
            "total_processed": 0,
            "total_time_ms": 0.0,
            "errors": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "stage_time_ms": {stage: 0.0 for stage in PROFILE_STAGES},
        }

    def _load_models(self) -> None:
        """Carrega apenas o classificador e metadata; não importa TensorFlow."""
        if self._models_loaded:
            return
        self._models_loaded = True
        classifier_path = self.model_path / "classifier.joblib"
        metadata_path = self.model_path / "metadata.json"
        try:
            if classifier_path.exists():
                self.classifier = joblib.load(classifier_path)
                logger.info("Classifier carregado: %s", classifier_path)
            else:
                logger.error("Classifier não encontrado: %s", classifier_path)

            if metadata_path.exists():
                with metadata_path.open("r", encoding="utf-8") as file:
                    self.metadata = json.load(file)
                logger.info(
                    "Metadata carregado: %d sinais",
                    len(self.metadata.get("labels", {})),
                )
            else:
                logger.warning("Metadata não encontrado: %s", metadata_path)
            self._label_map = {
                str(key): value for key, value in self.metadata.get("labels", {}).items()
            }
        except Exception:
            self._models_loaded = False  # permite nova tentativa após falha transitória
            logger.exception("Erro ao carregar modelos")

    def _load_sequence_model(self) -> Any:
        """Carregamento opcional e tardio para consumidores de sequências."""
        if self.sequence_model is not None:
            return self.sequence_model
        sequence_path = self.model_path / "sequence_model.keras"
        if not sequence_path.exists():
            return None
        try:
            from tensorflow import keras  # import pesado fora do caminho de frames estáticos

            self.sequence_model = keras.models.load_model(sequence_path)
        except Exception:
            logger.warning("Não foi possível carregar sequence model", exc_info=True)
        return self.sequence_model

    def _get_hands(self) -> Any:
        """Obtém (e inicializa se preciso) o detector de mãos MediaPipe."""
        if self._hands is not None or self._mediapipe_unavailable:
            return self._hands
        try:
            import mediapipe as mp

            self._hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        except ImportError:
            self._mediapipe_unavailable = True
            logger.error("MediaPipe não instalado")
        except Exception:
            logger.exception("Erro ao inicializar MediaPipe")
        return self._hands

    @staticmethod
    def _cache_key(frame: np.ndarray) -> Optional[tuple]:
        """Chave determinística; digest completo impede devolver landmarks errados."""
        if not frame.flags.c_contiguous:
            return None
        digest = hashlib.blake2b(frame.tobytes(), digest_size=16).digest()
        return frame.shape, frame.dtype.str, digest

    def _cache_get(self, key: Optional[tuple]) -> Tuple[bool, Optional[np.ndarray]]:
        """Retorna ``(acertou, landmarks)``; devolve cópia para evitar aliasing."""
        if key is None or key not in self._landmark_cache:
            return False, None
        self._landmark_cache.move_to_end(key)
        cached = self._landmark_cache[key]
        return True, None if cached is None else cached.copy()

    def _cache_put(self, key: Optional[tuple], landmarks: Optional[np.ndarray]) -> None:
        """Insere landmarks no cache LRU, expulsando o item mais antigo se preciso."""
        if key is None or self._landmark_cache_size == 0:
            return
        self._landmark_cache[key] = None if landmarks is None else landmarks.copy()
        self._landmark_cache.move_to_end(key)
        while len(self._landmark_cache) > self._landmark_cache_size:
            self._landmark_cache.popitem(last=False)

    def _extract_landmarks(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Extrai 63 features em ``float32`` sem listas/loops Python intermediários."""
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("frame deve ser um ndarray BGR com três canais")
        hands = self._get_hands()
        if hands is None:
            return None
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame_rgb)
        if not results.multi_hand_landmarks:
            return None
        points = results.multi_hand_landmarks[0].landmark
        return np.fromiter(
            (coordinate for point in points for coordinate in (point.x, point.y, point.z)),
            dtype=np.float32,
            count=FEATURE_COUNT,
        )

    def _predict(self, landmarks: np.ndarray) -> Tuple[Any, float]:
        """Obtém classe e confiança com uma única chamada ao modelo quando possível."""
        features = landmarks.reshape(1, -1)
        if hasattr(self.classifier, "predict_proba") and hasattr(self.classifier, "classes_"):
            probabilities = np.asarray(self.classifier.predict_proba(features)[0])
            index = int(np.argmax(probabilities))
            return self.classifier.classes_[index], float(probabilities[index])
        prediction = self.classifier.predict(features)[0]
        return prediction, 1.0

    async def process(self, frame: np.ndarray) -> RecognitionResult:
        """Processa um frame BGR sem alterar a API pública original."""
        started = time.perf_counter()
        profile: Dict[str, float] = {stage: 0.0 for stage in PROFILE_STAGES}
        try:
            self._time_stage(profile, STAGE_MODEL_LOAD, self._load_models)
            if self.classifier is None:
                return self._result_error(started, "Modelo não carregado", profile)

            key = self._cache_key(frame) if self._landmark_cache_size else None
            hit, landmarks = self._time_stage(profile, STAGE_CACHE_LOOKUP, self._cache_get, key)
            if hit:
                self.performance_stats["cache_hits"] += 1
            else:
                self.performance_stats["cache_misses"] += 1
                landmarks = self._time_stage(
                    profile, STAGE_LANDMARKS, self._extract_landmarks, frame
                )
                self._cache_put(key, landmarks)
            if landmarks is None:
                latency = (time.perf_counter() - started) * 1000
                self._record(latency, profile)
                return RecognitionResult(
                    "NO_HANDS",
                    0.0,
                    latency,
                    status="no_input",
                    error="Mãos não detectadas",
                )

            prediction, confidence = self._time_stage(
                profile, STAGE_INFERENCE, self._predict, landmarks
            )
            signal = self._label_map.get(str(prediction), f"UNKNOWN_{prediction}")
            latency = (time.perf_counter() - started) * 1000
            self._record(latency, profile)
            return RecognitionResult(signal, confidence, latency, landmarks.tolist())
        except Exception as error:
            logger.exception("Erro ao processar frame")
            self.performance_stats["errors"] += 1
            latency = (time.perf_counter() - started) * 1000
            self._record(latency, profile)
            return RecognitionResult("ERROR", 0.0, latency, status="error", error=str(error))

    @staticmethod
    def _time_stage(profile: Dict[str, float], stage: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Executa ``func`` cronometrando a etapa e acumulando no perfil."""
        step = time.perf_counter()
        result = func(*args, **kwargs)
        profile[stage] = (time.perf_counter() - step) * 1000
        return result

    def _result_error(self, started: float, error: str, profile: Dict[str, float]) -> RecognitionResult:
        """Constrói resultado de erro registrando estatísticas."""
        latency = (time.perf_counter() - started) * 1000
        self.performance_stats["errors"] += 1
        self._record(latency, profile)
        return RecognitionResult("ERROR", 0.0, latency, status="error", error=error)

    def _record(self, latency: float, profile: Dict[str, float]) -> None:
        """Acumula latência e tempo por etapa nas estatísticas do motor."""
        self._last_profile = profile.copy()
        self.performance_stats["total_processed"] += 1
        self.performance_stats["total_time_ms"] += latency
        stages = self.performance_stats["stage_time_ms"]
        for stage in stages:
            stages[stage] += profile.get(stage, 0.0)

    async def process_batch(self, frames: Iterable[np.ndarray]) -> list[RecognitionResult]:
        """Processa lotes sem recriar modelos/detector; conserva a ordem dos frames."""
        return [await self.process(frame) for frame in frames]

    async def benchmark_performance(self, frames: Iterable[np.ndarray], warmup_frames: int = 5) -> Dict:
        """Mede latência e etapas do pipeline. Use 100 frames para o relatório padrão."""
        frame_list = list(frames)
        if not frame_list:
            raise ValueError("benchmark requer ao menos um frame")
        for frame in frame_list[: min(warmup_frames, len(frame_list))]:
            await self.process(frame)
        latencies, statuses, profiles = [], [], []
        for result in await self.process_batch(frame_list):
            latencies.append(result.latency_ms)
            statuses.append(result.status)
            profiles.append(self._last_profile.copy())
        return self._build_benchmark_report(frame_list, latencies, statuses, profiles)

    def _build_benchmark_report(
        self,
        frame_list: list[np.ndarray],
        latencies: list[float],
        statuses: list[str],
        profiles: list[Dict[str, float]],
    ) -> Dict[str, Any]:
        """Consolida as medições do benchmark em um relatório."""
        values = np.asarray(latencies, dtype=np.float64)
        stage_profile = {
            name: float(np.mean([item.get(name, 0.0) for item in profiles]))
            for name in profiles[0]
        }
        mean_latency = float(values.mean()) if len(values) else 0.0
        return {
            "frames": len(frame_list),
            "avg_latency_ms": mean_latency,
            "p50_latency_ms": float(np.percentile(values, 50)) if len(values) else 0.0,
            "p95_latency_ms": float(np.percentile(values, 95)) if len(values) else 0.0,
            "p99_latency_ms": float(np.percentile(values, 99)) if len(values) else 0.0,
            "fps": float(1000.0 / mean_latency) if mean_latency else 0.0,
            "status_counts": {
                status: statuses.count(status) for status in sorted(set(statuses))
            },
            "avg_stage_ms": stage_profile,
            "cache": {
                "hits": self.performance_stats["cache_hits"],
                "misses": self.performance_stats["cache_misses"],
            },
        }

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas acumuladas do motor."""
        stats = self.performance_stats.copy()
        stats["stage_time_ms"] = self.performance_stats["stage_time_ms"].copy()
        if stats["total_processed"]:
            count = stats["total_processed"]
            stats["avg_latency_ms"] = stats["total_time_ms"] / count
            stats["error_rate"] = stats["errors"] / count
            stats["avg_stage_ms"] = {
                key: value / count for key, value in stats["stage_time_ms"].items()
            }
        return stats

    def clear_stats(self) -> None:
        """Zera estatísticas de performance."""
        self.performance_stats.update(
            {
                "total_processed": 0,
                "total_time_ms": 0.0,
                "errors": 0,
                "cache_hits": 0,
                "cache_misses": 0,
            }
        )
        self.performance_stats["stage_time_ms"] = {stage: 0.0 for stage in PROFILE_STAGES}

    def close(self) -> None:
        """Libera o recurso nativo do MediaPipe quando o motor for desligado."""
        if self._hands is not None:
            self._hands.close()
            self._hands = None
        self._landmark_cache.clear()


if __name__ == "__main__":
    async def _test() -> None:
        motor = MotorKonectaV3()
        try:
            result = await motor.process(np.zeros((480, 640, 3), dtype=np.uint8))
            print(f"Resultado: {result}")
            print(f"Stats: {motor.get_stats()}")
        finally:
            motor.close()

    asyncio.run(_test())
