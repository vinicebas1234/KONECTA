"""Temporal analysis of landmarks across frames."""

import numpy as np
from collections import deque
from typing import Optional, List

from vision_lab.core import Frame


class TemporalAnalyzer:
    """Analyzes temporal consistency and trends."""

    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.history = deque(maxlen=window_size)

    def add_frame(self, frame: Frame):
        """Add frame to temporal history."""
        self.history.append(frame)

    def detect_gaps(self) -> List[int]:
        """Detect frames with missing landmarks."""
        gaps = []
        for i, frame in enumerate(self.history):
            if frame.landmarks is None or np.all(frame.landmarks == 0):
                gaps.append(i)
        return gaps

    def compute_velocity(self) -> Optional[np.ndarray]:
        """Compute velocity between consecutive frames.

        Returns average velocity across valid frames.
        """
        if len(self.history) < 2:
            return None

        velocities = []
        for i in range(len(self.history) - 1):
            curr = self.history[i].landmarks
            next_ = self.history[i + 1].landmarks

            if curr is None or next_ is None:
                continue

            # Euclidean distance
            diff = next_ - curr
            vel = np.linalg.norm(diff)
            velocities.append(vel)

        return np.mean(velocities) if velocities else None

    def compute_acceleration(self) -> Optional[np.ndarray]:
        """Compute acceleration between consecutive frames."""
        if len(self.history) < 3:
            return None

        accelerations = []
        for i in range(len(self.history) - 2):
            curr = self.history[i].landmarks
            next1 = self.history[i + 1].landmarks
            next2 = self.history[i + 2].landmarks

            if curr is None or next1 is None or next2 is None:
                continue

            vel1 = np.linalg.norm(next1 - curr)
            vel2 = np.linalg.norm(next2 - next1)
            acc = abs(vel2 - vel1)
            accelerations.append(acc)

        return np.mean(accelerations) if accelerations else None

    def get_consistency_score(self) -> float:
        """Get temporal consistency score 0-1."""
        if len(self.history) == 0:
            return 0.0

        # Check for gaps
        gaps = self.detect_gaps()
        if len(gaps) > len(self.history) * 0.3:  # More than 30% gaps
            return 0.2

        # Check velocity smoothness
        vel = self.compute_velocity()
        if vel is None:
            return 0.0

        # Very high velocity = probably jittery/bad
        if vel > 0.5:
            return 0.3
        elif vel > 0.2:
            return 0.6
        else:
            return 0.9

    def get_report(self) -> dict:
        """Generate temporal analysis report."""
        gaps = self.detect_gaps()
        vel = self.compute_velocity()
        acc = self.compute_acceleration()

        return {
            "frames_in_buffer": len(self.history),
            "frames_with_gaps": len(gaps),
            "gap_positions": gaps,
            "avg_velocity": vel if vel is not None else 0.0,
            "avg_acceleration": acc if acc is not None else 0.0,
            "consistency_score": self.get_consistency_score(),
        }
