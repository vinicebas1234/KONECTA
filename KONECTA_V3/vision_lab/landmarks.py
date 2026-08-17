"""MediaPipe landmark extraction."""

import logging
from typing import Optional

import cv2
import numpy as np

try:
    from mediapipe.tasks import vision
    from mediapipe.framework.formats import landmark_pb2
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False

from vision_lab.core import Frame, LandmarkConfig, LandmarkSource

logger = logging.getLogger(__name__)


class LandmarkExtractor:
    """Extracts landmarks from frames using MediaPipe."""

    def __init__(self, config: LandmarkConfig = None):
        self.config = config or LandmarkConfig()
        self.hands = None
        self.pose = None
        self.results_buffer = {}
        self.available = MEDIAPIPE_AVAILABLE

        if MEDIAPIPE_AVAILABLE:
            self._init_detectors()
        else:
            logger.warning("MediaPipe not available, using fallback mode")

    def _init_detectors(self):
        """Initialize MediaPipe detectors based on config."""
        if not MEDIAPIPE_AVAILABLE:
            return

        # For now, use a fallback that generates dummy landmarks
        # Real implementation would use MediaPipe Vision API
        self.hands = True
        self.pose = True

    def extract(self, frame: Frame) -> Frame:
        """Extract landmarks from frame."""
        if not self.available:
            # Fallback: return zero vector
            frame.landmarks = np.zeros(228, dtype=np.float32)
            frame.confidence = 0.0
            return frame

        # For now, generate dummy landmarks for testing
        # Real implementation would process with MediaPipe
        frame.landmarks = np.random.randn(228).astype(np.float32)
        frame.confidence = np.random.rand()

        return frame

    @staticmethod
    def _landmarks_to_array(landmarks) -> np.ndarray:
        """Convert MediaPipe landmarks to numpy array (x, y, z)."""
        array = []
        for lm in landmarks.landmark:
            array.extend([lm.x, lm.y, lm.z if hasattr(lm, "z") else 0.0])
        return np.array(array)

    @staticmethod
    def _combine_landmarks(landmarks_list: list[np.ndarray]) -> np.ndarray:
        """Combine multiple landmark arrays into fixed-size array."""
        # Fixed size: 2 hands (21 points each) + pose (33 points) = 76 points * 3 = 228 values
        fixed_size = 228
        combined = np.zeros(fixed_size, dtype=np.float32)

        offset = 0
        for lms in landmarks_list:
            size = min(len(lms), fixed_size - offset)
            combined[offset : offset + size] = lms[:size]
            offset += size

        return combined

    def draw_landmarks(self, frame: Frame) -> np.ndarray:
        """Draw landmarks on frame for visualization."""
        # For now, return the original frame
        # Real implementation would draw actual landmark points
        return frame.image

    def __del__(self):
        """Cleanup."""
        if self.hands:
            self.hands.close()
        if self.pose:
            self.pose.close()
