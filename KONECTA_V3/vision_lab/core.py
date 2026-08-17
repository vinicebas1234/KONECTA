"""Core types and contracts for Vision Lab."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np


class LandmarkSource(Enum):
    HANDS = "hands"
    POSE = "pose"
    FACE = "face"
    HANDS_POSE = "hands_pose"
    HANDS_POSE_FACE = "hands_pose_face"


@dataclass
class LandmarkConfig:
    """Configuration for landmark extraction."""

    sources: LandmarkSource = LandmarkSource.HANDS_POSE
    confidence_threshold: float = 0.5
    smoothing_enabled: bool = False
    interpolate_missing: bool = False


@dataclass
class Frame:
    """Single frame from video."""

    frame_id: int
    timestamp: float
    image: np.ndarray
    landmarks: Optional[np.ndarray] = None
    confidence: Optional[float] = None
    quality_score: Optional[float] = None
    issues: list[str] = field(default_factory=list)


@dataclass
class Video:
    """Video file with metadata."""

    path: Path
    class_name: str
    signer_id: str
    fps: int = 30
    total_frames: int = 0
    width: int = 0
    height: int = 0
    duration_s: float = 0.0
    frames: list[Frame] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.class_name}_{self.signer_id}_{self.path.stem}"


@dataclass
class Dataset:
    """Dataset containing multiple videos."""

    name: str
    path: Path
    videos: list[Video] = field(default_factory=list)

    @property
    def classes(self) -> list[str]:
        return sorted(set(v.class_name for v in self.videos))

    @property
    def signers(self) -> list[str]:
        return sorted(set(v.signer_id for v in self.videos))

    def get_videos_by_class(self, class_name: str) -> list[Video]:
        return [v for v in self.videos if v.class_name == class_name]

    def get_videos_by_signer(self, signer_id: str) -> list[Video]:
        return [v for v in self.videos if v.signer_id == signer_id]
