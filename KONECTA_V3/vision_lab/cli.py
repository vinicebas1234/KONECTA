"""Command-line interface for KONECTA V3."""

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from vision_lab.experiments import (
    ExperimentManager,
    ExperimentConfig,
    PipelineComparator,
)
from vision_lab.dataset import DatasetLoader
from vision_lab.landmarks import LandmarkExtractor
from vision_lab.processing import (
    LandmarkCleaner,
    LandmarkInterpolator,
    LandmarkSmoother,
    LandmarkNormalizer,
)
from vision_lab.features import FeatureExtractor, FeatureSet
from vision_lab.dataset_builder import DatasetBuilder
from vision_lab.training import BaselineTrainer

logger = logging.getLogger(__name__)


class ExperimentCLI:
    """CLI for running experiments."""

    def __init__(self, output_dir: Path = None):
        """Initialize CLI.

        Args:
            output_dir: Output directory for experiments
        """
        self.manager = ExperimentManager(output_dir=output_dir)

    def run_baseline_experiment(
        self,
        dataset_path: Path,
        features_type: str = "RAW_XYZ",
        name: str = "baseline",
        description: str = "",
    ) -> None:
        """Run baseline experiment.

        Args:
            dataset_path: Path to dataset
            features_type: Feature type to use
            name: Experiment name
            description: Experiment description
        """
        logger.info(f"Starting baseline experiment: {name}")

        # Load dataset
        loader = DatasetLoader(dataset_path)
        videos = loader.load_all()
        logger.info(f"Loaded {len(videos)} videos")

        # Extract landmarks
        extractor = LandmarkExtractor()
        landmarks_data = []
        labels = []

        for video in videos[:10]:  # Use subset for speed
            for frame in video.frames[:50]:
                frame_obj = extractor.extract(frame)
                if frame_obj.landmarks is not None:
                    landmarks_data.append(frame_obj.landmarks)
                    labels.append(video.label)

        if len(landmarks_data) == 0:
            logger.error("No landmarks extracted")
            return

        landmarks_array = np.array(landmarks_data)
        labels_array = np.array(labels)

        logger.info(f"Extracted {len(landmarks_array)} landmark frames")

        # Process landmarks
        cleaner = LandmarkCleaner()
        smoother = LandmarkSmoother()
        normalizer = LandmarkNormalizer()

        landmarks_cleaned = cleaner.clean(landmarks_array)
        landmarks_smoothed = smoother.smooth(landmarks_cleaned)
        landmarks_normalized = normalizer.normalize_body_centered(landmarks_smoothed)

        # Extract features
        extractor_feat = FeatureExtractor()
        features = extractor_feat.extract(landmarks_normalized, features_type)

        logger.info(f"Extracted {features.shape[1]} features")

        # Build dataset
        builder = DatasetBuilder()
        X_train, X_val, X_test, y_train, y_val, y_test = builder.split_dataset(
            features, labels_array
        )

        # Train model
        trainer = BaselineTrainer()
        train_metrics = trainer.train(X_train, y_train, X_val, y_val)

        # Evaluate on test
        test_metrics = trainer.evaluate(X_test, y_test, dataset_name="test")

        # Log experiment
        config = ExperimentConfig(
            name=name,
            description=description or f"Baseline experiment with {features_type}",
            features_type=features_type,
            model_type="RandomForest",
            dataset_name="V-LIBRASIL",
            hyperparams={"n_estimators": trainer.n_estimators},
        )

        self.manager.log_experiment(
            config=config,
            train_metrics=train_metrics,
            val_metrics=train_metrics.get("val"),
            test_metrics=test_metrics,
            training_time=trainer.training_time,
        )

        logger.info(f"Experiment {name} completed")
        logger.info(f"Test F1: {test_metrics.get('f1', 0):.4f}")

    def compare_all(self, metric: str = "f1", top_n: int = 10) -> dict:
        """Compare all experiments.

        Args:
            metric: Metric to compare
            top_n: Number of top experiments

        Returns:
            Comparison dict
        """
        return self.manager.compare_experiments(metric=metric, top_n=top_n)

    def generate_report(self, output_format: str = "json") -> Path:
        """Generate experiment report.

        Args:
            output_format: Format (json/csv/html)

        Returns:
            Path to saved report
        """
        if output_format == "csv":
            return self.manager.save_comparison_csv()
        elif output_format == "html":
            return self.manager.save_comparison_html()
        else:  # json
            comparison = self.manager.compare_experiments()
            path = self.manager.output_dir / "comparison.json"
            with open(path, "w") as f:
                json.dump(comparison, f, indent=2, default=str)
            return path

    def list_experiments(self) -> list:
        """List all experiments.

        Returns:
            List of experiment names
        """
        return [exp.config.name for exp in self.manager.experiments]

    def get_summary(self) -> dict:
        """Get summary of all experiments.

        Returns:
            Summary dict
        """
        if not self.manager.experiments:
            return {"total": 0, "experiments": []}

        summary = {
            "total": len(self.manager.experiments),
            "experiments": [],
        }

        for exp in self.manager.experiments:
            test_metrics = exp.test_metrics or exp.train_metrics
            summary["experiments"].append({
                "name": exp.config.name,
                "features": exp.config.features_type,
                "model": exp.config.model_type,
                "f1": test_metrics.get("f1", 0),
                "accuracy": test_metrics.get("accuracy", 0),
                "training_time": exp.training_time,
            })

        return summary


class ReportGenerator:
    """Generate comprehensive reports."""

    @staticmethod
    def generate_markdown_report(
        experiments_dir: Path,
        output_path: Path,
    ) -> Path:
        """Generate markdown report.

        Args:
            experiments_dir: Directory with experiment files
            output_path: Output markdown path

        Returns:
            Path to report
        """
        manager = ExperimentManager(output_dir=experiments_dir)
        comparison = manager.compare_experiments()

        md_content = f"""# KONECTA V3 - Experiment Report

**Generated**: {__import__('datetime').datetime.now().isoformat()}

## Summary

- **Total Experiments**: {comparison.get('total_experiments', 0)}

## Top Experiments

| Name | Features | Model | Accuracy | F1 | Training Time |
|------|----------|-------|----------|----|----|
"""

        for exp in comparison.get("top_experiments", [])[:10]:
            md_content += f"""| {exp['name']} | {exp['features']} | {exp['model']} | {exp['accuracy']:.4f} | {exp['f1']:.4f} | {exp['training_time']:.2f}s |
"""

        with open(output_path, "w") as f:
            f.write(md_content)

        return output_path

    @staticmethod
    def generate_json_report(
        experiments_dir: Path,
        output_path: Path,
    ) -> Path:
        """Generate JSON report.

        Args:
            experiments_dir: Directory with experiment files
            output_path: Output JSON path

        Returns:
            Path to report
        """
        manager = ExperimentManager(output_dir=experiments_dir)
        comparison = manager.compare_experiments()

        with open(output_path, "w") as f:
            json.dump(comparison, f, indent=2, default=str)

        return output_path
