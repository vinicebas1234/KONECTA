"""Persistência dos landmarks extraídos por `vision/hand_landmarks.py`.

Duas partes, sempre juntas: o arquivo em disco (o dado em si) e a linha em
`landmark_samples` (o índice pesquisável — ver `database/models.py`, Ciclo 0).

Formato de arquivo escolhido: **JSON**, não `.npy`. Motivo: o número de mãos
detectadas varia por frame (0, 1 ou 2) — é uma estrutura "ragged". Um array
`.npy` retangular exigiria preencher com zeros os frames sem mão(s) ou sem a
segunda mão, disfarçando "não detectei" de "detectei zero", que são coisas
diferentes. JSON preserva a forma real do resultado e continua inspecionável
a olho nu — não há necessidade de performance que justifique binário aqui
(um sample é no máximo alguns milhares de frames, muito longe de gargalo).

Isolamento: os arquivos vão sempre para `libras_learning_agent/data/landmarks/`
(via `Settings.data_dir`, mesmo default do Ciclo 0) — nunca para
`KONECTA_V3/data/` nem `KONECTA_V3/models/`.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional, Union

from sqlalchemy.orm import Session

from libras_learning_agent.core.config import Settings, get_settings
from libras_learning_agent.database.models import LandmarkSample
from libras_learning_agent.vision.hand_landmarks import HandExtractionResult, HandFrameLandmarks


def landmarks_dir(settings: Optional[Settings] = None) -> Path:
    settings = settings or get_settings()
    return Path(settings.data_dir) / "landmarks"


def _frame_to_dict(frame: HandFrameLandmarks) -> dict:
    return {
        "frame_id": frame.frame_id,
        "timestamp_ms": frame.timestamp_ms,
        "hands": [
            {"label": h.label, "score": h.score, "points": [list(p) for p in h.points]}
            for h in frame.hands
        ],
    }


def save_landmarks_file(
    result: HandExtractionResult, sample_id: str, settings: Optional[Settings] = None
) -> Path:
    """Escreve o resultado da extração em `<landmarks_dir>/<sample_id>.json`."""
    out_dir = landmarks_dir(settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"{sample_id}.json"

    payload = {
        "fps": result.fps,
        "frame_count": result.frame_count,
        "detection_rate": result.detection_rate,
        "frames": [_frame_to_dict(f) for f in result.frames],
    }
    file_path.write_text(json.dumps(payload), encoding="utf-8")
    return file_path


def load_landmarks_file(file_path: Union[str, Path]) -> dict:
    """Lê de volta o JSON gravado por `save_landmarks_file` (uso em testes/depuração)."""
    return json.loads(Path(file_path).read_text(encoding="utf-8"))


def save_hand_extraction(
    result: HandExtractionResult,
    signal_id: str,
    session: Session,
    *,
    sample_id: Optional[str] = None,
    variant_id: Optional[str] = None,
    video_id: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> LandmarkSample:
    """Persiste a extração inteira: arquivo em disco + linha em `landmark_samples`.

    `signal_id` é obrigatório porque `LandmarkSample.signal_id` é FK não-nula
    (ver `database/models.py`) — quem chamar precisa ter um `Signal` já criado.
    """
    sample_id = sample_id or str(uuid.uuid4())
    file_path = save_landmarks_file(result, sample_id, settings=settings)

    sample = LandmarkSample(
        id=sample_id,
        signal_id=signal_id,
        variant_id=variant_id,
        video_id=video_id,
        file_path=str(file_path),
        frame_count=result.frame_count,
        fps=result.fps,
        quality_score=result.detection_rate,
    )
    session.add(sample)
    session.commit()
    return sample
