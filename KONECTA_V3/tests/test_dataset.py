"""Test dataset discovery and loading."""

from pathlib import Path

import pytest

from vision_lab.dataset import DatasetLoader


def test_dataset_loader_init():
    """Test DatasetLoader initialization."""
    loader = DatasetLoader()
    assert loader.datasets == {}


def test_supported_formats():
    """Test supported video formats."""
    loader = DatasetLoader()
    assert ".mp4" in loader.SUPPORTED_FORMATS
    assert ".avi" in loader.SUPPORTED_FORMATS


def test_extract_metadata():
    """Test metadata extraction from paths."""
    # Pattern: .../CLASS/SIGNER/video.mp4
    path = Path("data/CASA/signer_01/video.mp4")
    cls, signer = DatasetLoader._extract_metadata(path)
    assert cls == "CASA"
    assert signer == "signer_01"

    # Pattern: .../CLASS/video.mp4
    path = Path("data/CARRO/video.mp4")
    cls, signer = DatasetLoader._extract_metadata(path)
    assert cls == "CARRO"
    assert signer == "CARRO"
