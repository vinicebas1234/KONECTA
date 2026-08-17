"""Feature engineering for landmarks."""

import numpy as np
from typing import List, Dict, Tuple
from enum import Enum

from vision_lab.core import Frame


class FeatureType(Enum):
    """Available feature types."""

    RAW_XYZ = "raw_xyz"  # Raw coordinates
    VELOCITY = "velocity"  # First derivative
    ACCELERATION = "acceleration"  # Second derivative
    DISTANCES = "distances"  # Euclidean distances between points
    ANGLES = "angles"  # Angles between connections
    HANDCRAFTED = "handcrafted"  # Custom engineered features


class FeatureExtractor:
    """Extract features from landmarks."""

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
        (11, 23), (12, 24),  # Torso
        (23, 24),  # Hips
        (23, 25), (25, 27),  # Right leg
        (24, 26), (26, 28),  # Left leg
    ]

    def __init__(self, feature_types: List[FeatureType] = None):
        """Initialize with feature types to extract.

        Args:
            feature_types: List of FeatureType to extract.
                          Defaults to RAW_XYZ only.
        """
        self.feature_types = feature_types or [FeatureType.RAW_XYZ]
        self.prev_landmarks = None
        self.prev_velocity = None

    def extract_single_frame(self, frame: Frame) -> np.ndarray:
        """Extract features from single frame (no temporal).

        Args:
            frame: Frame with landmarks

        Returns:
            Feature vector
        """
        if frame.landmarks is None:
            return np.zeros(self._get_feature_dim_single(), dtype=np.float32)

        features = []

        # Raw XYZ always included
        if FeatureType.RAW_XYZ in self.feature_types:
            features.append(frame.landmarks)

        # Distances between key points
        if FeatureType.DISTANCES in self.feature_types:
            distances = self._extract_distances(frame.landmarks)
            features.append(distances)

        # Angles between connections
        if FeatureType.ANGLES in self.feature_types:
            angles = self._extract_angles(frame.landmarks)
            features.append(angles)

        if len(features) == 0:
            return np.zeros(self._get_feature_dim_single(), dtype=np.float32)

        return np.concatenate(features).astype(np.float32)

    def extract_temporal(self, frame: Frame) -> np.ndarray:
        """Extract features including temporal derivatives.

        Args:
            frame: Current frame

        Returns:
            Feature vector with velocity and acceleration
        """
        base_features = self.extract_single_frame(frame)
        features = [base_features]

        # Velocity (first derivative)
        if FeatureType.VELOCITY in self.feature_types:
            if self.prev_landmarks is not None and frame.landmarks is not None:
                velocity = frame.landmarks - self.prev_landmarks
                # Velocity for other extracted features too
                if FeatureType.DISTANCES in self.feature_types:
                    dist_curr = self._extract_distances(frame.landmarks)
                    if self.prev_distances is not None:
                        dist_vel = dist_curr - self.prev_distances
                        features.append(dist_vel)
            else:
                features.append(np.zeros_like(base_features))

        # Acceleration (second derivative)
        if FeatureType.ACCELERATION in self.feature_types:
            if self.prev_velocity is not None and frame.landmarks is not None:
                velocity = frame.landmarks - self.prev_landmarks
                acceleration = velocity - self.prev_velocity
                features.append(acceleration)
            else:
                features.append(np.zeros_like(base_features))

        # Update history
        if frame.landmarks is not None:
            self.prev_landmarks = frame.landmarks.copy()
            if FeatureType.DISTANCES in self.feature_types:
                self.prev_distances = self._extract_distances(frame.landmarks)
            if FeatureType.VELOCITY in self.feature_types:
                velocity = frame.landmarks - self.prev_landmarks if self.prev_landmarks is not None else np.zeros_like(frame.landmarks)
                self.prev_velocity = velocity

        return np.concatenate(features).astype(np.float32)

    def extract_sequence(self, frames: List[Frame], temporal: bool = False) -> np.ndarray:
        """Extract features from sequence of frames.

        Args:
            frames: List of frames
            temporal: If True, include velocity/acceleration

        Returns:
            Array of shape (num_frames, num_features)
        """
        features_list = []

        for frame in frames:
            if temporal:
                feat = self.extract_temporal(frame)
            else:
                feat = self.extract_single_frame(frame)
            features_list.append(feat)

        return np.array(features_list, dtype=np.float32)

    @staticmethod
    def _extract_distances(landmarks: np.ndarray) -> np.ndarray:
        """Extract Euclidean distances between key points."""
        points = landmarks.reshape(76, 3)
        distances = []

        # Hand distances (within each hand)
        for hand_idx in range(2):
            hand_points = points[hand_idx * 21 : (hand_idx + 1) * 21]
            # Distance from thumb to each other point
            for i in range(1, 21):
                dist = np.linalg.norm(hand_points[i][:2] - hand_points[0][:2])
                distances.append(dist)

        # Pose distances (shoulder-to-shoulder, etc)
        pose_points = points[42:75]
        if len(pose_points) > 12:
            # Shoulder distance
            shoulder_dist = np.linalg.norm(pose_points[11][:2] - pose_points[12][:2])
            distances.append(shoulder_dist)

            # Hip distance
            hip_dist = np.linalg.norm(pose_points[23][:2] - pose_points[24][:2])
            distances.append(hip_dist)

        return np.array(distances, dtype=np.float32)

    @staticmethod
    def _extract_angles(landmarks: np.ndarray) -> np.ndarray:
        """Extract angles between connected points."""
        points = landmarks.reshape(76, 3)
        angles = []

        # Hand angles
        for hand_idx in range(2):
            hand_points = points[hand_idx * 21 : (hand_idx + 1) * 21]

            # Angle at each joint
            for start, end in FeatureExtractor.HAND_CONNECTIONS:
                if start > 0 and end < 21:
                    # Angle between (start-1 to start) and (start to end)
                    if start > 0:
                        v1 = hand_points[start][:2] - hand_points[start - 1][:2]
                        v2 = hand_points[end][:2] - hand_points[start][:2]
                        angle = np.arccos(
                            np.clip(
                                np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6),
                                -1,
                                1,
                            )
                        )
                        angles.append(angle)

        # Pose angles
        pose_points = points[42:75]
        for start, end in FeatureExtractor.POSE_CONNECTIONS:
            if start < len(pose_points) and end < len(pose_points):
                if start > 0:
                    v1 = pose_points[start][:2] - pose_points[start - 1][:2]
                    v2 = pose_points[end][:2] - pose_points[start][:2]
                    angle = np.arccos(
                        np.clip(
                            np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6),
                            -1,
                            1,
                        )
                    )
                    angles.append(angle)

        return np.array(angles, dtype=np.float32)

    def _get_feature_dim_single(self) -> int:
        """Get feature dimension for single frame."""
        dim = 0
        if FeatureType.RAW_XYZ in self.feature_types:
            dim += 228  # 76 points * 3 coords

        if FeatureType.DISTANCES in self.feature_types:
            dim += 2 * 20 + 2  # 20 distances per hand + 2 pose distances

        if FeatureType.ANGLES in self.feature_types:
            dim += 2 * 20 + 11  # ~20 angles per hand + 11 pose angles

        return dim

    def get_feature_dim(self) -> int:
        """Get total feature dimension."""
        dim = self._get_feature_dim_single()

        if FeatureType.VELOCITY in self.feature_types:
            dim += self._get_feature_dim_single()

        if FeatureType.ACCELERATION in self.feature_types:
            dim += self._get_feature_dim_single()

        return dim


class FeatureSet:
    """Pre-defined feature sets for experiments."""

    @staticmethod
    def get_preset(name: str) -> List[FeatureType]:
        """Get preset feature set."""
        presets = {
            "baseline": [FeatureType.RAW_XYZ],
            "with_velocity": [FeatureType.RAW_XYZ, FeatureType.VELOCITY],
            "with_acceleration": [FeatureType.RAW_XYZ, FeatureType.VELOCITY, FeatureType.ACCELERATION],
            "geometric": [FeatureType.RAW_XYZ, FeatureType.DISTANCES, FeatureType.ANGLES],
            "full": [
                FeatureType.RAW_XYZ,
                FeatureType.VELOCITY,
                FeatureType.ACCELERATION,
                FeatureType.DISTANCES,
                FeatureType.ANGLES,
            ],
        }

        if name not in presets:
            raise ValueError(f"Unknown preset: {name}. Available: {list(presets.keys())}")

        return presets[name]

    @staticmethod
    def list_presets() -> Dict[str, str]:
        """List available presets."""
        return {
            "baseline": "Raw XYZ coordinates only",
            "with_velocity": "XYZ + velocity",
            "with_acceleration": "XYZ + velocity + acceleration",
            "geometric": "XYZ + distances + angles",
            "full": "All features (XYZ + velocity + accel + distances + angles)",
        }
