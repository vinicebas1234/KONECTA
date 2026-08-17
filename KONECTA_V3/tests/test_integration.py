"""Integration tests for complete pipeline."""

import numpy as np
from pathlib import Path

from vision_lab.core import Frame, Video, Dataset, LandmarkConfig
from vision_lab.visualization import LandmarkVisualizer, QualityAnalyzer
from vision_lab.temporal import TemporalAnalyzer
from vision_lab.landmarks import LandmarkExtractor


def test_end_to_end_frame_processing():
    """Test processing a frame end-to-end."""
    # Create dummy image and video
    image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Create frame
    frame = Frame(
        frame_id=0,
        timestamp=0.0,
        image=image,
    )

    # Extract landmarks
    config = LandmarkConfig()
    extractor = LandmarkExtractor(config)
    frame = extractor.extract(frame)

    # Analyze quality
    quality_analyzer = QualityAnalyzer()
    quality = quality_analyzer.analyze_frame(frame)

    assert "score" in quality
    assert "status" in quality
    assert quality["status"] in ["GOOD", "WARNING", "BAD"]


def test_temporal_consistency_across_frames():
    """Test temporal consistency across multiple frames."""
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    temporal_analyzer = TemporalAnalyzer(window_size=10)

    # Create sequence of frames
    base_landmarks = np.random.rand(228).astype(np.float32) * 0.5 + 0.25

    for i in range(10):
        # Small variations to simulate smooth motion
        landmarks = base_landmarks + np.random.randn(228).astype(np.float32) * 0.02
        frame = Frame(frame_id=i, timestamp=float(i) / 30.0, image=image, landmarks=landmarks)
        temporal_analyzer.add_frame(frame)

    report = temporal_analyzer.get_report()
    assert report["frames_in_buffer"] == 10
    assert "consistency_score" in report
    assert 0 <= report["consistency_score"] <= 1


def test_quality_visualization_pipeline():
    """Test complete quality and visualization pipeline."""
    image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Create frame with landmarks
    landmarks = np.random.rand(228).astype(np.float32) * 0.8 + 0.1
    frame = Frame(
        frame_id=0,
        timestamp=0.0,
        image=image,
        landmarks=landmarks,
        confidence=0.85,
    )

    # Analyze quality
    quality_analyzer = QualityAnalyzer()
    quality = quality_analyzer.analyze_frame(frame)
    assert quality["score"] > 0

    # Visualize landmarks
    visualized = LandmarkVisualizer.draw_landmarks(frame, landmarks)
    assert visualized.shape == image.shape
    assert visualized.dtype == np.uint8
