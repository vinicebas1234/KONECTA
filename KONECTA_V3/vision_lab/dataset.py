"""Dataset discovery and loading."""

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from vision_lab.core import Dataset, Video

logger = logging.getLogger(__name__)


class DatasetLoader:
    """Discovers and loads datasets from filesystem."""

    SUPPORTED_FORMATS = {".mp4", ".avi", ".mov", ".mkv"}

    def __init__(self):
        self.datasets = {}

    def discover_dataset(self, path: Path, name: Optional[str] = None) -> Dataset:
        """Auto-discover dataset structure from path.

        Supports structures:
        - train/CLASS/SIGNER/video.mp4
        - train/CLASS/video.mp4
        - data/CLASS/video.mp4
        - data/SIGNAL_NAME/video.mp4
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Dataset path not found: {path}")

        name = name or path.name
        dataset = Dataset(name=name, path=path)

        videos_found = self._discover_videos(path)

        for video_path in videos_found:
            try:
                video = self._analyze_video(video_path)
                dataset.videos.append(video)
            except Exception as e:
                logger.warning(f"Failed to analyze {video_path}: {e}")

        logger.info(
            f"Dataset '{name}' loaded: {len(dataset.videos)} videos, "
            f"{len(dataset.classes)} classes, {len(dataset.signers)} signers"
        )

        self.datasets[name] = dataset
        return dataset

    def _discover_videos(self, root_path: Path) -> list[Path]:
        """Recursively find all video files."""
        videos = []
        for ext in self.SUPPORTED_FORMATS:
            videos.extend(root_path.rglob(f"*{ext}"))
        return sorted(videos)

    def _analyze_video(self, video_path: Path) -> Video:
        """Analyze video file and extract metadata."""
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            raise RuntimeError(f"Failed to open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        cap.release()

        # Extract class and signer from path
        class_name, signer_id = self._extract_metadata(video_path)

        duration_s = total_frames / max(fps, 1.0)

        return Video(
            path=video_path,
            class_name=class_name,
            signer_id=signer_id,
            fps=int(fps),
            total_frames=total_frames,
            width=width,
            height=height,
            duration_s=duration_s,
        )

    @staticmethod
    def _extract_metadata(video_path: Path) -> tuple[str, str]:
        """Extract class and signer from file path.

        Heuristics:
        - If path contains SIGNER/video: class from parent, signer explicit
        - If path contains CLASS/SIGNER: use both
        - If path contains CLASS/video: class explicit, signer=class
        """
        parts = video_path.parts

        # Check for common patterns
        if len(parts) >= 3:
            # Pattern: .../CLASS/SIGNER/video.mp4
            potential_signer = parts[-2]
            potential_class = parts[-3]

            if potential_signer.startswith("signer") or potential_signer.startswith(
                "Sign"
            ):
                return potential_class, potential_signer

            # Pattern: .../CLASS/video.mp4
            if potential_class not in {"train", "test", "data", "videos UFPE (V-LIBRASIL)"}:
                return potential_class, potential_class

        if len(parts) >= 2:
            # Pattern: .../CLASS/video.mp4
            class_name = parts[-2]
            return class_name, class_name

        # Fallback: use video filename
        return "unknown", "signer_unknown"


class VideoLoader:
    """Loads frames from video file."""

    def __init__(self, video: Video, max_frames: Optional[int] = None):
        self.video = video
        self.max_frames = max_frames or video.total_frames
        self._cap = None

    def __enter__(self):
        self._cap = cv2.VideoCapture(str(self.video.path))
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open video: {self.video.path}")
        return self

    def __exit__(self, *args):
        if self._cap:
            self._cap.release()

    def get_frame(self, frame_id: int) -> Optional[np.ndarray]:
        """Get frame by ID."""
        if not self._cap:
            raise RuntimeError("VideoLoader not opened")

        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ret, frame = self._cap.read()
        return frame if ret else None

    def iter_frames(self):
        """Iterate over frames."""
        if not self._cap:
            raise RuntimeError("VideoLoader not opened")

        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        frame_id = 0

        while frame_id < self.max_frames:
            ret, frame = self._cap.read()
            if not ret:
                break

            from vision_lab.core import Frame

            yield Frame(
                frame_id=frame_id,
                timestamp=frame_id / max(self.video.fps, 1.0),
                image=frame,
            )

            frame_id += 1
