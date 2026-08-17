"""Build datasets for training."""

import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
from datetime import datetime

from vision_lab.core import Frame, Video, Dataset
from vision_lab.features import FeatureExtractor, FeatureType
from vision_lab.dataset import VideoLoader

logger = logging.getLogger(__name__)


class DatasetBuilder:
    """Build processed datasets ready for training."""

    def __init__(self, output_dir: Path = None):
        """Initialize builder.

        Args:
            output_dir: Where to save processed data
        """
        self.output_dir = output_dir or Path("./data")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirs
        (self.output_dir / "raw").mkdir(exist_ok=True)
        (self.output_dir / "processed").mkdir(exist_ok=True)
        (self.output_dir / "features").mkdir(exist_ok=True)
        (self.output_dir / "metadata").mkdir(exist_ok=True)

    def build_dataset(
        self,
        dataset: Dataset,
        feature_types: List[FeatureType],
        output_name: str = "dataset",
    ) -> Dict:
        """Build complete dataset with features.

        Args:
            dataset: Dataset to process
            feature_types: Features to extract
            output_name: Name for output files

        Returns:
            Metadata about built dataset
        """
        logger.info(f"Building dataset: {output_name}")

        feature_extractor = FeatureExtractor(feature_types)
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "dataset_name": dataset.name,
            "output_name": output_name,
            "feature_types": [ft.value for ft in feature_types],
            "feature_dim": feature_extractor.get_feature_dim(),
            "num_videos": len(dataset.videos),
            "num_classes": len(dataset.classes),
            "num_signers": len(dataset.signers),
            "samples": [],
        }

        features_list = []
        labels_list = []
        video_ids = []

        total_videos = len(dataset.videos)
        for idx, video in enumerate(dataset.videos):
            try:
                logger.info(f"Processing {idx+1}/{total_videos}: {video.id}")

                # Load video
                with VideoLoader(video) as loader:
                    frames = list(loader.iter_frames())

                if len(frames) == 0:
                    logger.warning(f"No frames in {video.id}")
                    continue

                # Extract features from each frame
                for frame in frames:
                    features = feature_extractor.extract_single_frame(frame)
                    if np.any(features != 0):  # Only include non-zero features
                        features_list.append(features)
                        labels_list.append(video.class_name)
                        video_ids.append(video.id)

                # Update metadata
                metadata["samples"].append({
                    "video_id": video.id,
                    "class": video.class_name,
                    "signer": video.signer_id,
                    "frames_extracted": len(frames),
                    "status": "success",
                })

            except Exception as e:
                logger.error(f"Failed to process {video.id}: {e}")
                metadata["samples"].append({
                    "video_id": video.id,
                    "class": video.class_name,
                    "signer": video.signer_id,
                    "status": "failed",
                    "error": str(e),
                })

        # Save features
        features_array = np.array(features_list, dtype=np.float32)
        features_path = self.output_dir / "features" / f"{output_name}_features.npy"
        np.save(features_path, features_array)
        logger.info(f"Saved {len(features_list)} feature vectors to {features_path}")

        # Save labels
        labels_array = np.array(labels_list, dtype=str)
        labels_path = self.output_dir / "features" / f"{output_name}_labels.npy"
        np.save(labels_path, labels_array)

        # Save metadata
        metadata_path = self.output_dir / "metadata" / f"{output_name}_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        metadata["features_saved"] = str(features_path)
        metadata["labels_saved"] = str(labels_path)
        metadata["metadata_saved"] = str(metadata_path)
        metadata["total_samples"] = len(features_list)

        logger.info(f"Dataset built: {len(features_list)} samples")

        return metadata

    @staticmethod
    def load_dataset(features_path: Path, labels_path: Path) -> Tuple[np.ndarray, np.ndarray]:
        """Load built dataset.

        Args:
            features_path: Path to features.npy
            labels_path: Path to labels.npy

        Returns:
            (features, labels) arrays
        """
        features = np.load(features_path)
        labels = np.load(labels_path)
        return features, labels

    def create_splits(
        self,
        features: np.ndarray,
        labels: np.ndarray,
        train_ratio: float = 0.7,
        val_ratio: float = 0.1,
        test_ratio: float = 0.2,
        random_seed: int = 42,
    ) -> Dict:
        """Create train/val/test splits.

        Args:
            features: Feature array
            labels: Label array
            train_ratio: Training set ratio
            val_ratio: Validation set ratio
            test_ratio: Test set ratio
            random_seed: Random seed for reproducibility

        Returns:
            Dict with train/val/test indices and counts
        """
        np.random.seed(random_seed)

        n_samples = len(features)
        indices = np.arange(n_samples)
        np.random.shuffle(indices)

        # Calculate split indices
        train_end = int(n_samples * train_ratio)
        val_end = train_end + int(n_samples * val_ratio)

        train_idx = indices[:train_end]
        val_idx = indices[train_end:val_end]
        test_idx = indices[val_end:]

        return {
            "train": {
                "indices": train_idx,
                "features": features[train_idx],
                "labels": labels[train_idx],
                "count": len(train_idx),
            },
            "val": {
                "indices": val_idx,
                "features": features[val_idx],
                "labels": labels[val_idx],
                "count": len(val_idx),
            },
            "test": {
                "indices": test_idx,
                "features": features[test_idx],
                "labels": labels[test_idx],
                "count": len(test_idx),
            },
        }

    def create_cross_signer_split(
        self,
        dataset: Dataset,
        features: np.ndarray,
        labels: np.ndarray,
        test_signer: str,
    ) -> Dict:
        """Create cross-signer split (leave-one-signer-out).

        Args:
            dataset: Original dataset
            features: Feature array
            labels: Label array
            test_signer: Signer to hold out for test

        Returns:
            Dict with train/test split
        """
        # Get video IDs for test signer
        test_videos = dataset.get_videos_by_signer(test_signer)
        test_video_ids = {v.id for v in test_videos}

        # We need to map back to original videos (this is simplified)
        # In practice, would need to track which sample came from which video
        logger.warning("Cross-signer split requires video-to-sample mapping")

        return {
            "train": {"count": len(features)},
            "test": {"count": 0, "signer": test_signer},
        }
