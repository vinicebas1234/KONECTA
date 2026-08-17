"""Test landmark processing: cleaning, interpolation, smoothing."""

import numpy as np
import pytest

from vision_lab.core import Frame
from vision_lab.processing import (
    LandmarkCleaner,
    LandmarkInterpolator,
    LandmarkSmoother,
    LandmarkNormalizer,
)


def test_cleaner_init():
    """Test LandmarkCleaner initialization."""
    cleaner = LandmarkCleaner(quality_threshold=0.6)
    assert cleaner.quality_threshold == 0.6


def test_cleaner_removes_outliers():
    """Test that cleaner clips outliers."""
    cleaner = LandmarkCleaner()
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    # Create landmarks with values outside [0, 1]
    landmarks = np.array([-0.5] + [0.5] * 227, dtype=np.float32)
    frame = Frame(frame_id=0, timestamp=0.0, image=image, landmarks=landmarks)

    cleaned = cleaner.clean_frame(frame)
    assert np.all(cleaned.landmarks >= 0)
    assert np.all(cleaned.landmarks <= 1)


def test_cleaner_sequence():
    """Test cleaning a sequence of frames."""
    cleaner = LandmarkCleaner(quality_threshold=0.7)
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    frames = []
    for i in range(5):
        landmarks = np.random.rand(228).astype(np.float32)
        frame = Frame(
            frame_id=i,
            timestamp=float(i) / 30,
            image=image,
            landmarks=landmarks,
            quality_score=0.9 if i % 2 == 0 else 0.5,  # Alternate good/bad
        )
        frames.append(frame)

    cleaned = cleaner.clean_sequence(frames)
    assert len(cleaned) == 5
    # Bad quality frames should have None landmarks
    assert cleaned[1].landmarks is None
    assert cleaned[3].landmarks is None


def test_interpolator_init():
    """Test LandmarkInterpolator initialization."""
    interp = LandmarkInterpolator(max_gap_size=3)
    assert interp.max_gap_size == 3


def test_interpolator_linear():
    """Test linear interpolation."""
    interp = LandmarkInterpolator()
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    # Create sequence with gap
    frames = []
    base_landmarks = np.ones(228, dtype=np.float32) * 0.3

    for i in range(5):
        if i == 2:
            landmarks = None  # Gap
        else:
            landmarks = base_landmarks + np.random.randn(228).astype(np.float32) * 0.01

        frame = Frame(frame_id=i, timestamp=float(i), image=image, landmarks=landmarks)
        frames.append(frame)

    interpolated = interp.interpolate_sequence(frames, method="linear")
    assert len(interpolated) == 5
    # Gap should be filled
    assert interpolated[2].landmarks is not None


def test_smoother_gaussian():
    """Test Gaussian smoothing."""
    smoother = LandmarkSmoother(window_size=5)
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    # Create noisy sequence
    frames = []
    for i in range(10):
        landmarks = np.sin(np.arange(228) / 50.0 + i * 0.1).astype(np.float32)
        landmarks += np.random.randn(228).astype(np.float32) * 0.1  # Add noise
        frame = Frame(frame_id=i, timestamp=float(i), image=image, landmarks=landmarks)
        frames.append(frame)

    smoothed = smoother.smooth_sequence(frames, method="gaussian")
    assert len(smoothed) == 10
    # Smoothed should have less variance than original
    original_var = np.var(np.array([f.landmarks for f in frames if f.landmarks is not None]))
    smoothed_var = np.var(np.array([f.landmarks for f in smoothed if f.landmarks is not None]))
    assert smoothed_var <= original_var


def test_smoother_moving_avg():
    """Test moving average smoothing."""
    smoother = LandmarkSmoother()
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    frames = []
    for i in range(5):
        landmarks = np.full(228, float(i), dtype=np.float32)
        frame = Frame(frame_id=i, timestamp=float(i), image=image, landmarks=landmarks)
        frames.append(frame)

    smoothed = smoother.smooth_sequence(frames, method="movavg")
    assert len(smoothed) == 5
    # Should still be in valid range
    assert np.all(smoothed[2].landmarks >= -1)
    assert np.all(smoothed[2].landmarks <= 5)


def test_normalizer_body_centered():
    """Test body-centered normalization."""
    landmarks = np.random.rand(228).astype(np.float32) * 0.5 + 0.25
    normalized = LandmarkNormalizer.normalize_body_centered(landmarks)

    assert normalized.shape == landmarks.shape
    assert normalized.dtype == np.float32
    # Normalized values should be different from original
    assert not np.allclose(normalized, landmarks)


def test_normalizer_scale():
    """Test scale normalization."""
    landmarks = np.random.rand(228).astype(np.float32) * 0.8 + 0.1
    normalized = LandmarkNormalizer.normalize_scale(landmarks, target_scale=0.5)

    assert normalized.shape == landmarks.shape
    assert normalized.dtype == np.float32


def test_normalizer_rotation():
    """Test rotation normalization."""
    landmarks = np.random.rand(228).astype(np.float32) * 0.5 + 0.25
    normalized = LandmarkNormalizer.normalize_rotation(landmarks)

    assert normalized.shape == landmarks.shape
    assert normalized.dtype == np.float32
