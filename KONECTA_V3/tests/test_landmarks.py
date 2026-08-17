"""Test landmark extraction."""

import numpy as np

from vision_lab.core import LandmarkConfig, LandmarkSource
from vision_lab.landmarks import LandmarkExtractor


def test_landmark_config_init():
    """Test LandmarkConfig initialization."""
    config = LandmarkConfig()
    assert config.sources == LandmarkSource.HANDS_POSE
    assert config.confidence_threshold == 0.5


def test_landmark_extractor_init():
    """Test LandmarkExtractor initialization."""
    config = LandmarkConfig(sources=LandmarkSource.HANDS)
    extractor = LandmarkExtractor(config)
    assert extractor.config.sources == LandmarkSource.HANDS
    # MediaPipe may or may not be available, just check initialization works
    assert extractor is not None


def test_combine_landmarks():
    """Test combining landmarks into fixed size."""
    lms = [np.random.randn(63), np.random.randn(99)]
    combined = LandmarkExtractor._combine_landmarks(lms)
    assert combined.shape == (228,)
    assert combined.dtype == np.float32
