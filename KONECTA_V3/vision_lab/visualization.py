"""Landmark visualization and quality analysis."""

import cv2
import numpy as np
from typing import Tuple, List

from vision_lab.core import Frame


class LandmarkVisualizer:
    """Visualizes landmarks on frames."""

    # Colors for different body parts
    HAND_COLOR = (0, 255, 0)  # Green
    POSE_COLOR = (255, 0, 0)  # Red
    FACE_COLOR = (0, 0, 255)  # Blue
    CONNECTION_COLOR = (200, 200, 200)  # Gray

    # MediaPipe structure
    HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),      # Thumb
        (0, 5), (5, 6), (6, 7), (7, 8),      # Index
        (0, 9), (9, 10), (10, 11), (11, 12), # Middle
        (0, 13), (13, 14), (14, 15), (15, 16), # Ring
        (0, 17), (17, 18), (18, 19), (19, 20),  # Pinky
    ]

    POSE_CONNECTIONS = [
        (11, 13), (13, 15),  # Right arm
        (12, 14), (14, 16),  # Left arm
        (11, 12),  # Shoulders
        (11, 23), (12, 24),  # Torso top
        (23, 24),  # Hips
        (23, 25), (25, 27),  # Right leg
        (24, 26), (26, 28),  # Left leg
    ]

    @staticmethod
    def draw_landmarks(frame: Frame, landmarks: np.ndarray) -> np.ndarray:
        """Draw landmarks on frame.

        Args:
            frame: Frame with image
            landmarks: Array of shape (228,) containing normalized [0,1] coordinates

        Returns:
            Image with drawn landmarks
        """
        image = frame.image.copy()
        h, w, _ = image.shape

        # Reshape landmarks to (76 points, 3 coords)
        try:
            points = landmarks.reshape(76, 3)
        except ValueError:
            return image

        # Split into hands, pose, face
        hands = points[:42]  # 2 hands × 21 points
        pose = points[42:75]  # 33 points
        # face = points[75]  # 1 face point (placeholder)

        # Draw hands
        LandmarkVisualizer._draw_hand_landmarks(
            image, hands, h, w, LandmarkVisualizer.HAND_COLOR
        )

        # Draw pose
        LandmarkVisualizer._draw_pose_landmarks(
            image, pose, h, w, LandmarkVisualizer.POSE_COLOR
        )

        return image

    @staticmethod
    def _draw_hand_landmarks(
        image: np.ndarray, hands: np.ndarray, h: int, w: int, color: Tuple
    ):
        """Draw hand landmarks."""
        for hand_idx in range(2):
            hand_points = hands[hand_idx * 21 : (hand_idx + 1) * 21]

            # Draw connections
            for start, end in LandmarkVisualizer.HAND_CONNECTIONS:
                if start < len(hand_points) and end < len(hand_points):
                    x1, y1, z1 = hand_points[start]
                    x2, y2, z2 = hand_points[end]

                    if x1 > 0 and y1 > 0 and x2 > 0 and y2 > 0:
                        pt1 = (int(x1 * w), int(y1 * h))
                        pt2 = (int(x2 * w), int(y2 * h))
                        cv2.line(image, pt1, pt2, LandmarkVisualizer.CONNECTION_COLOR, 1)

            # Draw points
            for x, y, z in hand_points:
                if x > 0 and y > 0:
                    pt = (int(x * w), int(y * h))
                    cv2.circle(image, pt, 3, color, -1)

    @staticmethod
    def _draw_pose_landmarks(
        image: np.ndarray, pose: np.ndarray, h: int, w: int, color: Tuple
    ):
        """Draw pose landmarks."""
        # Draw connections
        for start, end in LandmarkVisualizer.POSE_CONNECTIONS:
            if start < len(pose) and end < len(pose):
                x1, y1, z1 = pose[start]
                x2, y2, z2 = pose[end]

                if x1 > 0 and y1 > 0 and x2 > 0 and y2 > 0:
                    pt1 = (int(x1 * w), int(y1 * h))
                    pt2 = (int(x2 * w), int(y2 * h))
                    cv2.line(image, pt1, pt2, LandmarkVisualizer.CONNECTION_COLOR, 2)

        # Draw points
        for x, y, z in pose:
            if x > 0 and y > 0:
                pt = (int(x * w), int(y * h))
                cv2.circle(image, pt, 4, color, -1)


class QualityAnalyzer:
    """Analyzes quality of landmarks."""

    def __init__(self, confidence_threshold: float = 0.5):
        self.confidence_threshold = confidence_threshold

    def analyze_frame(self, frame: Frame) -> dict:
        """Analyze quality of landmarks in a frame.

        Returns:
            {
                'score': 0-100,
                'status': 'GOOD' | 'WARNING' | 'BAD',
                'issues': [...],
                'detection_rate': 0-1,
                'confidence_avg': 0-1,
                'stability': 0-1,
            }
        """
        if frame.landmarks is None:
            return {
                "score": 0,
                "status": "BAD",
                "issues": ["No landmarks detected"],
                "detection_rate": 0.0,
                "confidence_avg": 0.0,
                "stability": 0.0,
            }

        issues = []
        scores = []

        # Confidence check
        if frame.confidence is not None:
            confidence = frame.confidence
            scores.append(confidence * 100)
            if confidence < self.confidence_threshold:
                issues.append(f"Low confidence: {confidence:.2f}")
            elif confidence < 0.7:
                issues.append(f"Moderate confidence: {confidence:.2f}")
        else:
            confidence = 0.0

        # Missing landmarks check
        missing_ratio = self._check_missing_landmarks(frame.landmarks)
        if missing_ratio > 0.1:
            issues.append(f"Missing landmarks: {missing_ratio*100:.1f}%")
            scores.append((1 - missing_ratio) * 100)
        else:
            scores.append(100)

        # Velocity check (stability)
        stability = self._check_stability(frame.landmarks)
        scores.append(stability * 100)

        # Combined score
        avg_score = np.mean(scores) if scores else 0
        score = int(avg_score)

        # Determine status
        if score >= 80:
            status = "GOOD"
        elif score >= 50:
            status = "WARNING"
        else:
            status = "BAD"

        return {
            "score": score,
            "status": status,
            "issues": issues,
            "detection_rate": 1.0 - missing_ratio,
            "confidence_avg": confidence,
            "stability": stability,
        }

    @staticmethod
    def _check_missing_landmarks(landmarks: np.ndarray) -> float:
        """Check ratio of missing landmarks (zeros or NaNs)."""
        # Reshape to (76, 3)
        try:
            points = landmarks.reshape(76, 3)
        except ValueError:
            return 1.0

        # Count points with all zeros (missing)
        missing = np.sum(np.all(points == 0, axis=1))
        return missing / len(points)

    @staticmethod
    def _check_stability(landmarks: np.ndarray) -> float:
        """Check stability (penalize very high velocities/accelerations).

        Assumes landmarks are relatively stable in a single frame.
        Returns 0-1 score.
        """
        try:
            points = landmarks.reshape(76, 3)
        except ValueError:
            return 0.0

        # Check for extreme outliers
        x_vals = points[:, 0]
        y_vals = points[:, 1]

        # Valid range should be [0, 1]
        out_of_range = np.sum((x_vals < 0) | (x_vals > 1) | (y_vals < 0) | (y_vals > 1))

        if out_of_range > 0:
            return 0.5

        # Check spread (shouldn't be all in tiny area)
        x_spread = np.max(x_vals) - np.min(x_vals)
        y_spread = np.max(y_vals) - np.min(y_vals)

        # If spread is too small, probably noise
        if x_spread < 0.05 and y_spread < 0.05:
            return 0.3

        return 0.9
