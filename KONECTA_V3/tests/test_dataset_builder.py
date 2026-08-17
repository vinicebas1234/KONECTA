"""Test dataset builder."""

import numpy as np
import pytest
from pathlib import Path

from vision_lab.dataset_builder import DatasetBuilder


def test_dataset_builder_init(tmp_path):
    """Test DatasetBuilder initialization."""
    builder = DatasetBuilder(output_dir=tmp_path)
    assert builder.output_dir == tmp_path
    assert (tmp_path / "raw").exists()
    assert (tmp_path / "processed").exists()
    assert (tmp_path / "features").exists()
    assert (tmp_path / "metadata").exists()


def test_load_dataset(tmp_path):
    """Test loading dataset."""
    features = np.random.rand(100, 228).astype(np.float32)
    labels = np.array(["CASA"] * 50 + ["CARRO"] * 50, dtype=str)

    # Save
    features_path = tmp_path / "features.npy"
    labels_path = tmp_path / "labels.npy"
    np.save(features_path, features)
    np.save(labels_path, labels)

    # Load
    loaded_features, loaded_labels = DatasetBuilder.load_dataset(features_path, labels_path)
    assert np.allclose(loaded_features, features)
    assert np.array_equal(loaded_labels, labels)


def test_create_splits():
    """Test creating train/val/test splits."""
    builder = DatasetBuilder()

    features = np.random.rand(100, 228).astype(np.float32)
    labels = np.array(["CASA"] * 50 + ["CARRO"] * 50, dtype=str)

    splits = builder.create_splits(
        features, labels, train_ratio=0.7, val_ratio=0.1, test_ratio=0.2
    )

    assert "train" in splits
    assert "val" in splits
    assert "test" in splits

    assert splits["train"]["count"] == 70
    assert splits["val"]["count"] == 10
    assert splits["test"]["count"] == 20

    # Check no overlap
    all_indices = np.concatenate([
        splits["train"]["indices"],
        splits["val"]["indices"],
        splits["test"]["indices"],
    ])
    assert len(np.unique(all_indices)) == len(all_indices)


def test_create_splits_ratios():
    """Test splits with different ratios."""
    builder = DatasetBuilder()

    features = np.random.rand(1000, 228).astype(np.float32)
    labels = np.array(["A", "B"] * 500, dtype=str)

    splits = builder.create_splits(
        features, labels, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1
    )

    assert splits["train"]["count"] == 800
    assert splits["val"]["count"] == 100
    assert splits["test"]["count"] == 100
