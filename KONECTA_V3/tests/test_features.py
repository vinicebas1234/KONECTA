"""Test feature extraction."""

import numpy as np
import pytest

from vision_lab.core import Frame
from vision_lab.features import FeatureExtractor, FeatureType, FeatureSet


def test_feature_extractor_init():
    """Test FeatureExtractor initialization."""
    extractor = FeatureExtractor()
    assert extractor.feature_types == [FeatureType.RAW_XYZ]


def test_feature_extractor_init_with_types():
    """Test initialization with multiple types."""
    types = [FeatureType.RAW_XYZ, FeatureType.VELOCITY]
    extractor = FeatureExtractor(types)
    assert extractor.feature_types == types


def test_extract_single_frame():
    """Test single frame feature extraction."""
    extractor = FeatureExtractor([FeatureType.RAW_XYZ])
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    landmarks = np.random.rand(228).astype(np.float32)
    frame = Frame(frame_id=0, timestamp=0.0, image=image, landmarks=landmarks)

    features = extractor.extract_single_frame(frame)
    assert features.shape[0] == 228  # Raw XYZ only
    assert features.dtype == np.float32


def test_extract_distances():
    """Test distance extraction."""
    landmarks = np.random.rand(228).astype(np.float32) * 0.5 + 0.25
    distances = FeatureExtractor._extract_distances(landmarks)

    assert len(distances) > 0
    assert np.all(distances >= 0)  # Distances are non-negative


def test_extract_angles():
    """Test angle extraction."""
    landmarks = np.random.rand(228).astype(np.float32) * 0.5 + 0.25
    angles = FeatureExtractor._extract_angles(landmarks)

    assert len(angles) > 0
    assert np.all(angles >= 0)  # Angles are non-negative


def test_extract_with_distances():
    """Test extraction with distance features."""
    extractor = FeatureExtractor([FeatureType.RAW_XYZ, FeatureType.DISTANCES])
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    landmarks = np.random.rand(228).astype(np.float32) * 0.5 + 0.25
    frame = Frame(frame_id=0, timestamp=0.0, image=image, landmarks=landmarks)

    features = extractor.extract_single_frame(frame)
    assert features.shape[0] > 228  # Should include distances


def test_extract_sequence():
    """Test sequence extraction."""
    extractor = FeatureExtractor([FeatureType.RAW_XYZ])
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    frames = []
    for i in range(10):
        landmarks = np.random.rand(228).astype(np.float32)
        frame = Frame(frame_id=i, timestamp=float(i), image=image, landmarks=landmarks)
        frames.append(frame)

    features = extractor.extract_sequence(frames, temporal=False)
    assert features.shape == (10, 228)


def test_feature_dim():
    """Test feature dimension calculation."""
    extractor1 = FeatureExtractor([FeatureType.RAW_XYZ])
    dim1 = extractor1.get_feature_dim()
    assert dim1 == 228

    extractor2 = FeatureExtractor([FeatureType.RAW_XYZ, FeatureType.VELOCITY])
    dim2 = extractor2.get_feature_dim()
    assert dim2 > dim1


def test_feature_set_presets():
    """Test preset feature sets."""
    presets = FeatureSet.list_presets()
    assert "baseline" in presets
    assert "full" in presets


def test_feature_set_baseline():
    """Test baseline preset."""
    features = FeatureSet.get_preset("baseline")
    assert features == [FeatureType.RAW_XYZ]


def test_feature_set_full():
    """Test full preset."""
    features = FeatureSet.get_preset("full")
    assert len(features) == 5  # All feature types


def test_feature_set_invalid():
    """Test invalid preset."""
    with pytest.raises(ValueError):
        FeatureSet.get_preset("invalid")


def test_temporal_extraction():
    """Test temporal feature extraction."""
    extractor = FeatureExtractor([FeatureType.RAW_XYZ])
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    # First frame
    landmarks1 = np.random.rand(228).astype(np.float32) * 0.5 + 0.25
    frame1 = Frame(frame_id=0, timestamp=0.0, image=image, landmarks=landmarks1)
    features1 = extractor.extract_temporal(frame1)

    # Second frame
    landmarks2 = landmarks1 + np.random.randn(228).astype(np.float32) * 0.01
    frame2 = Frame(frame_id=1, timestamp=1.0, image=image, landmarks=landmarks2)
    features2 = extractor.extract_temporal(frame2)

    # Should both have same dimension (raw XYZ only)
    assert features1.shape[0] == 228
    assert features2.shape[0] == 228
