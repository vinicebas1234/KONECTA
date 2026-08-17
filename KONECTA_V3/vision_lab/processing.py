"""Landmark processing: cleaning, interpolation, smoothing, normalization."""

import numpy as np
from typing import List, Optional, Tuple
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d
from scipy.signal import savgol_filter

from vision_lab.core import Frame


class LandmarkCleaner:
    """Clean noisy and invalid landmarks."""

    def __init__(self, quality_threshold: float = 0.5):
        self.quality_threshold = quality_threshold

    def clean_frame(self, frame: Frame) -> Frame:
        """Clean landmarks in a frame."""
        if frame.landmarks is None:
            return frame

        landmarks = frame.landmarks.copy()

        # Remove points outside [0, 1] range
        landmarks = np.clip(landmarks, 0, 1)

        # Remove points with all zeros
        points = landmarks.reshape(76, 3)
        for i in range(len(points)):
            if np.all(points[i] == 0):
                points[i] = 0  # Keep as zeros (mark as missing)

        frame.landmarks = points.flatten()
        return frame

    def clean_sequence(self, frames: List[Frame]) -> List[Frame]:
        """Clean a sequence of frames."""
        # Mark frames with low quality score as missing
        cleaned = []
        for frame in frames:
            if frame.quality_score is not None and frame.quality_score < self.quality_threshold:
                frame.landmarks = None
            cleaned.append(self.clean_frame(frame))
        return cleaned


class LandmarkInterpolator:
    """Interpolate missing landmarks."""

    def __init__(self, max_gap_size: int = 5):
        self.max_gap_size = max_gap_size

    def interpolate_sequence(self, frames: List[Frame], method: str = "linear") -> List[Frame]:
        """Interpolate missing landmarks in a sequence.

        Args:
            frames: List of frames
            method: 'linear' or 'cubic'

        Returns:
            Frames with interpolated landmarks
        """
        # Extract landmarks as matrix (num_frames × 228)
        landmarks_list = []
        valid_indices = []

        for i, frame in enumerate(frames):
            if frame.landmarks is not None and np.any(frame.landmarks != 0):
                landmarks_list.append(frame.landmarks)
                valid_indices.append(i)

        if len(valid_indices) < 2:
            return frames  # Not enough points to interpolate

        # Interpolate each coordinate
        interpolated = self._interpolate_array(
            np.array(landmarks_list), valid_indices, len(frames), method
        )

        # Assign back to frames
        for i, frame in enumerate(frames):
            if interpolated[i] is not None:
                frame.landmarks = interpolated[i]

        return frames

    @staticmethod
    def _interpolate_array(
        values: np.ndarray,
        valid_indices: List[int],
        total_frames: int,
        method: str = "linear",
    ) -> List[np.ndarray]:
        """Interpolate array using scipy."""
        results = [None] * total_frames

        # Handle each coordinate independently
        for coord_idx in range(values.shape[1]):
            coords = values[:, coord_idx]

            try:
                if method == "linear":
                    f = interp1d(
                        valid_indices, coords, kind="linear", fill_value="extrapolate"
                    )
                elif method == "cubic":
                    f = interp1d(
                        valid_indices, coords, kind="cubic", fill_value="extrapolate"
                    )
                else:
                    continue

                all_indices = np.arange(total_frames)
                interpolated_coords = f(all_indices)

                # Assign to result
                for i, idx in enumerate(all_indices):
                    if results[i] is None:
                        results[i] = interpolated_coords[i:i+1]
                    else:
                        results[i] = np.append(results[i], interpolated_coords[i])

            except Exception:
                pass

        # Convert to proper format
        final_results = []
        for r in results:
            if r is not None and len(r) == values.shape[1]:
                final_results.append(r.astype(np.float32))
            else:
                final_results.append(None)

        return final_results


class LandmarkSmoother:
    """Smooth jittery landmarks."""

    def __init__(self, window_size: int = 5):
        self.window_size = window_size

    def smooth_sequence(self, frames: List[Frame], method: str = "gaussian") -> List[Frame]:
        """Smooth landmarks across sequence.

        Args:
            frames: List of frames
            method: 'gaussian', 'movavg', or 'savgol'

        Returns:
            Smoothed frames
        """
        landmarks_list = []
        for frame in frames:
            if frame.landmarks is not None:
                landmarks_list.append(frame.landmarks)
            else:
                landmarks_list.append(np.zeros(228, dtype=np.float32))

        if len(landmarks_list) < 2:
            return frames

        landmarks_array = np.array(landmarks_list)

        # Smooth each coordinate
        smoothed = np.zeros_like(landmarks_array)

        for coord_idx in range(landmarks_array.shape[1]):
            coords = landmarks_array[:, coord_idx]

            if method == "gaussian":
                smoothed[:, coord_idx] = gaussian_filter1d(coords, sigma=1)
            elif method == "movavg":
                smoothed[:, coord_idx] = self._moving_average(coords)
            elif method == "savgol":
                try:
                    window = min(self.window_size, len(coords) if len(coords) % 2 == 1 else len(coords) - 1)
                    if window < 3:
                        smoothed[:, coord_idx] = coords
                    else:
                        smoothed[:, coord_idx] = savgol_filter(coords, window, 2)
                except Exception:
                    smoothed[:, coord_idx] = coords

        # Assign back to frames
        for i, frame in enumerate(frames):
            if frame.landmarks is not None:
                frame.landmarks = smoothed[i]

        return frames

    @staticmethod
    def _moving_average(values: np.ndarray, window: int = 5) -> np.ndarray:
        """Compute moving average."""
        result = np.zeros_like(values)
        for i in range(len(values)):
            start = max(0, i - window // 2)
            end = min(len(values), i + window // 2 + 1)
            result[i] = np.mean(values[start:end])
        return result


class LandmarkNormalizer:
    """Normalize landmarks to reduce variance."""

    @staticmethod
    def normalize_body_centered(landmarks: np.ndarray) -> np.ndarray:
        """Normalize relative to body center (torso/shoulders).

        Assumes landmarks structure: hands (42 points) + pose (33 points)
        Center is computed from pose keypoints 11, 12 (shoulders)
        """
        points = landmarks.reshape(76, 3)
        pose_points = points[42:75]

        # Get shoulder center (indices 11, 12 in pose = 0, 1 in pose_points)
        if len(pose_points) > 1:
            center_x = (pose_points[0, 0] + pose_points[1, 0]) / 2
            center_y = (pose_points[0, 1] + pose_points[1, 1]) / 2
        else:
            center_x = 0.5
            center_y = 0.5

        # Subtract center
        normalized = points.copy()
        normalized[:, 0] -= center_x
        normalized[:, 1] -= center_y

        return normalized.flatten().astype(np.float32)

    @staticmethod
    def normalize_scale(landmarks: np.ndarray, target_scale: float = 0.5) -> np.ndarray:
        """Normalize scale based on bounding box."""
        points = landmarks.reshape(76, 3)

        # Get bounding box
        valid_points = points[np.any(points != 0, axis=1)]
        if len(valid_points) == 0:
            return landmarks

        x_min, x_max = np.min(valid_points[:, 0]), np.max(valid_points[:, 0])
        y_min, y_max = np.min(valid_points[:, 1]), np.max(valid_points[:, 1])

        scale_x = x_max - x_min
        scale_y = y_max - y_min
        scale = max(scale_x, scale_y)

        if scale > 0:
            scale_factor = target_scale / scale
            normalized = points.copy()
            normalized[:, 0] *= scale_factor
            normalized[:, 1] *= scale_factor
            return normalized.flatten().astype(np.float32)

        return landmarks

    @staticmethod
    def normalize_rotation(landmarks: np.ndarray) -> np.ndarray:
        """Normalize rotation (align shoulders horizontally).

        Note: This is a simplified version. Full 3D rotation would be more complex.
        """
        points = landmarks.reshape(76, 3)
        pose_points = points[42:75]

        if len(pose_points) > 1:
            # Angle between shoulders
            shoulder_y_diff = pose_points[1, 1] - pose_points[0, 1]
            shoulder_x_diff = pose_points[1, 0] - pose_points[0, 0]

            if abs(shoulder_x_diff) > 0.01:
                angle = np.arctan2(shoulder_y_diff, shoulder_x_diff)

                # Rotation matrix (simplified 2D)
                cos_a = np.cos(-angle)
                sin_a = np.sin(-angle)

                normalized = points.copy()
                for i in range(len(normalized)):
                    x, y = normalized[i, 0], normalized[i, 1]
                    normalized[i, 0] = x * cos_a - y * sin_a
                    normalized[i, 1] = x * sin_a + y * cos_a

                return normalized.flatten().astype(np.float32)

        return landmarks
