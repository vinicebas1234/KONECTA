"""Test visualization and quality analysis."""

import numpy as np
import pytest

from vision_lab.core import Frame
from vision_lab.visualization import LandmarkVisualizer, QualityAnalyzer
from vision_lab.temporal import TemporalAnalyzer


def test_landmark_visualizer_init():
    """Test LandmarkVisualizer initialization."""
    viz = LandmarkVisualizer()
    assert viz.HAND_COLOR == (0, 255, 0)
    assert viz.POSE_COLOR == (255, 0, 0)
    assert len(viz.HAND_CONNECTIONS) == 20
    assert len(viz.POSE_CONNECTIONS) == 12  # 12 connections


def test_quality_analyzer_init():
    """Test QualityAnalyzer initialization."""
    analyzer = QualityAnalyzer(confidence_threshold=0.5)
    assert analyzer.confidence_threshold == 0.5


def test_quality_analyzer_no_landmarks():
    """Test quality analysis with missing landmarks."""
    analyzer = QualityAnalyzer()
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    frame = Frame(frame_id=0, timestamp=0.0, image=image, landmarks=None)

    result = analyzer.analyze_frame(frame)
    assert result["score"] == 0
    assert result["status"] == "BAD"
    assert len(result["issues"]) > 0


def test_quality_analyzer_good_landmarks():
    """Test quality analysis with good landmarks."""
    analyzer = QualityAnalyzer()
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    # Create valid landmarks (76 points, 3 coords)
    landmarks = np.random.rand(228).astype(np.float32) * 0.8 + 0.1

    frame = Frame(frame_id=0, timestamp=0.0, image=image, landmarks=landmarks, confidence=0.9)

    result = analyzer.analyze_frame(frame)
    assert result["status"] in ["GOOD", "WARNING"]
    assert result["score"] > 0


def test_quality_analyzer_missing_landmarks_detection():
    """Test detection of missing landmarks."""
    analyzer = QualityAnalyzer()

    # 50% missing landmarks (every other point is zero)
    landmarks = np.zeros(228, dtype=np.float32)
    # Set alternating XYZ to make alternating points non-zero
    for i in range(0, 228, 6):  # Every other point (skip 3 coords)
        if i + 3 <= 228:
            landmarks[i:i+3] = np.random.rand(3)

    missing_ratio = analyzer._check_missing_landmarks(landmarks)
    # Should be around 50% missing
    assert 0.3 < missing_ratio < 0.7


def test_temporal_analyzer_init():
    """Test TemporalAnalyzer initialization."""
    analyzer = TemporalAnalyzer(window_size=5)
    assert analyzer.window_size == 5
    assert len(analyzer.history) == 0


def test_temporal_analyzer_detect_gaps():
    """Test gap detection."""
    analyzer = TemporalAnalyzer(window_size=5)

    # Add frames, some with missing landmarks
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    for i in range(5):
        if i == 2:
            landmarks = None  # Gap
        else:
            landmarks = np.random.rand(228).astype(np.float32)

        frame = Frame(frame_id=i, timestamp=float(i), image=image, landmarks=landmarks)
        analyzer.add_frame(frame)

    gaps = analyzer.detect_gaps()
    assert 2 in gaps


def test_temporal_analyzer_consistency_score():
    """Test temporal consistency scoring."""
    analyzer = TemporalAnalyzer(window_size=3)
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    # Good frames (small differences)
    base_landmarks = np.random.rand(228).astype(np.float32) * 0.5 + 0.25
    for i in range(3):
        landmarks = base_landmarks + np.random.randn(228).astype(np.float32) * 0.01
        frame = Frame(frame_id=i, timestamp=float(i), image=image, landmarks=landmarks)
        analyzer.add_frame(frame)

    score = analyzer.get_consistency_score()
    assert 0 <= score <= 1
