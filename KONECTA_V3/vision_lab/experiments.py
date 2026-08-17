"""Experiment management and tracking."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Experiment configuration."""

    name: str
    description: str
    features_type: str
    model_type: str
    dataset_name: str
    hyperparams: Dict
    version: str = "V3"

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ExperimentResult:
    """Single experiment result."""

    config: ExperimentConfig
    timestamp: float
    train_metrics: Dict
    val_metrics: Optional[Dict]
    test_metrics: Optional[Dict]
    cross_signer_metrics: Optional[Dict]
    training_time: float
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "config": self.config.to_dict(),
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "train_metrics": self.train_metrics,
            "val_metrics": self.val_metrics,
            "test_metrics": self.test_metrics,
            "cross_signer_metrics": self.cross_signer_metrics,
            "training_time": self.training_time,
            "notes": self.notes,
        }


class ExperimentManager:
    """Manage experiments and track results."""

    def __init__(self, output_dir: Path = None):
        """Initialize experiment manager.

        Args:
            output_dir: Directory to save experiments
        """
        self.output_dir = Path(output_dir or "./experiments")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.experiments: List[ExperimentResult] = []
        self._load_existing_experiments()

    def _load_existing_experiments(self) -> None:
        """Load existing experiments from disk."""
        for exp_file in self.output_dir.glob("*.json"):
            try:
                with open(exp_file, "r") as f:
                    data = json.load(f)
                    logger.info(f"Loaded experiment: {exp_file.name}")
            except Exception as e:
                logger.warning(f"Failed to load {exp_file}: {e}")

    def log_experiment(
        self,
        config: ExperimentConfig,
        train_metrics: Dict,
        val_metrics: Optional[Dict] = None,
        test_metrics: Optional[Dict] = None,
        cross_signer_metrics: Optional[Dict] = None,
        training_time: float = 0.0,
        notes: str = "",
    ) -> ExperimentResult:
        """Log a new experiment.

        Args:
            config: Experiment configuration
            train_metrics: Training metrics
            val_metrics: Validation metrics (optional)
            test_metrics: Test metrics (optional)
            cross_signer_metrics: Cross-signer metrics (optional)
            training_time: Training duration in seconds
            notes: Additional notes

        Returns:
            Experiment result
        """
        result = ExperimentResult(
            config=config,
            timestamp=time.time(),
            train_metrics=train_metrics,
            val_metrics=val_metrics,
            test_metrics=test_metrics,
            cross_signer_metrics=cross_signer_metrics,
            training_time=training_time,
            notes=notes,
        )

        self.experiments.append(result)

        # Save to disk
        exp_data = result.to_dict()
        exp_file = self.output_dir / f"{config.name}_{int(result.timestamp)}.json"
        with open(exp_file, "w") as f:
            json.dump(exp_data, f, indent=2)

        logger.info(f"Experiment logged: {config.name}")
        return result

    def get_best_experiment(
        self, metric: str = "f1", dataset: str = "test"
    ) -> Optional[ExperimentResult]:
        """Get best experiment by metric.

        Args:
            metric: Metric to sort by (e.g., 'f1', 'accuracy')
            dataset: Dataset to use (train/val/test)

        Returns:
            Best experiment or None
        """
        if not self.experiments:
            return None

        valid_exps = []
        for exp in self.experiments:
            metrics_dict = None
            if dataset == "train":
                metrics_dict = exp.train_metrics
            elif dataset == "val":
                metrics_dict = exp.val_metrics
            elif dataset == "test":
                metrics_dict = exp.test_metrics

            if metrics_dict and metric in metrics_dict:
                valid_exps.append((exp, metrics_dict[metric]))

        if valid_exps:
            return max(valid_exps, key=lambda x: x[1])[0]
        return None

    def compare_experiments(
        self, metric: str = "f1", top_n: int = 10
    ) -> Dict:
        """Compare all experiments.

        Args:
            metric: Metric to compare by
            top_n: Number of top experiments to return

        Returns:
            Comparison dict
        """
        if not self.experiments:
            return {"message": "No experiments to compare"}

        experiments_data = []
        for exp in self.experiments:
            test_metrics = exp.test_metrics or exp.train_metrics

            if metric in test_metrics:
                experiments_data.append({
                    "name": exp.config.name,
                    "features": exp.config.features_type,
                    "model": exp.config.model_type,
                    "dataset": exp.config.dataset_name,
                    "accuracy": test_metrics.get("accuracy", 0),
                    "f1": test_metrics.get("f1", 0),
                    "precision": test_metrics.get("precision", 0),
                    "recall": test_metrics.get("recall", 0),
                    "training_time": exp.training_time,
                    "timestamp": datetime.fromtimestamp(exp.timestamp).isoformat(),
                })

        # Sort by metric
        experiments_data.sort(
            key=lambda x: x.get(metric, 0), reverse=True
        )

        return {
            "total_experiments": len(self.experiments),
            "top_experiments": experiments_data[:top_n],
            "all_experiments": experiments_data,
        }

    def get_by_features(self, features_type: str) -> List[ExperimentResult]:
        """Get all experiments using specific features.

        Args:
            features_type: Feature type to filter by

        Returns:
            List of experiments
        """
        return [
            exp for exp in self.experiments
            if exp.config.features_type == features_type
        ]

    def get_by_model(self, model_type: str) -> List[ExperimentResult]:
        """Get all experiments using specific model.

        Args:
            model_type: Model type to filter by

        Returns:
            List of experiments
        """
        return [
            exp for exp in self.experiments
            if exp.config.model_type == model_type
        ]

    def save_comparison_csv(
        self, filename: str = "comparison.csv", metric: str = "f1"
    ) -> Path:
        """Save comparison to CSV.

        Args:
            filename: Output filename
            metric: Metric to include

        Returns:
            Path to saved file
        """
        import csv

        path = self.output_dir / filename
        comparison = self.compare_experiments(metric=metric, top_n=1000)

        with open(path, "w", newline="") as f:
            if comparison.get("all_experiments"):
                writer = csv.DictWriter(
                    f, fieldnames=comparison["all_experiments"][0].keys()
                )
                writer.writeheader()
                writer.writerows(comparison["all_experiments"])

        logger.info(f"Comparison saved to {path}")
        return path

    def save_comparison_html(
        self, filename: str = "comparison.html", metric: str = "f1"
    ) -> Path:
        """Save comparison to HTML.

        Args:
            filename: Output filename
            metric: Metric to include

        Returns:
            Path to saved file
        """
        path = self.output_dir / filename
        comparison = self.compare_experiments(metric=metric, top_n=100)

        html = """<!DOCTYPE html>
<html>
<head>
    <title>KONECTA V3 - Experiment Comparison</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; background-color: white; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .metric-good { color: green; font-weight: bold; }
        .metric-fair { color: orange; font-weight: bold; }
        .metric-poor { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <h1>KONECTA V3 - Experiment Comparison</h1>
    <p>Total Experiments: """ + str(comparison.get("total_experiments", 0)) + """</p>
    <p>Generated: """ + datetime.now().isoformat() + """</p>

    <h2>Top Experiments</h2>
    <table>
        <tr>
            <th>Name</th>
            <th>Features</th>
            <th>Model</th>
            <th>Accuracy</th>
            <th>F1</th>
            <th>Precision</th>
            <th>Recall</th>
            <th>Training Time (s)</th>
            <th>Timestamp</th>
        </tr>
"""

        for exp in comparison.get("all_experiments", []):
            f1_class = (
                "metric-good" if exp["f1"] > 0.85
                else "metric-fair" if exp["f1"] > 0.70
                else "metric-poor"
            )

            html += f"""        <tr>
            <td>{exp['name']}</td>
            <td>{exp['features']}</td>
            <td>{exp['model']}</td>
            <td>{exp['accuracy']:.4f}</td>
            <td class="{f1_class}">{exp['f1']:.4f}</td>
            <td>{exp['precision']:.4f}</td>
            <td>{exp['recall']:.4f}</td>
            <td>{exp['training_time']:.2f}</td>
            <td>{exp['timestamp']}</td>
        </tr>
"""

        html += """    </table>
</body>
</html>"""

        with open(path, "w") as f:
            f.write(html)

        logger.info(f"HTML comparison saved to {path}")
        return path


class PipelineComparator:
    """Compare V1, V2, and V3 pipelines."""

    @staticmethod
    def compare_versions(
        v1_results: Optional[Dict],
        v2_results: Optional[Dict],
        v3_results: Optional[Dict],
    ) -> Dict:
        """Compare pipeline versions.

        Args:
            v1_results: V1 pipeline results
            v2_results: V2 pipeline results
            v3_results: V3 pipeline results

        Returns:
            Comparison dict
        """
        comparison = {
            "v1": v1_results or {},
            "v2": v2_results or {},
            "v3": v3_results or {},
        }

        # Add improvements
        if v2_results and v1_results:
            v1_f1 = v1_results.get("f1", 0)
            v2_f1 = v2_results.get("f1", 0)
            if v1_f1 > 0:
                improvement = ((v2_f1 - v1_f1) / v1_f1) * 100
                comparison["v1_to_v2_improvement"] = improvement

        if v3_results and v2_results:
            v2_f1 = v2_results.get("f1", 0)
            v3_f1 = v3_results.get("f1", 0)
            if v2_f1 > 0:
                improvement = ((v3_f1 - v2_f1) / v2_f1) * 100
                comparison["v2_to_v3_improvement"] = improvement

        return comparison

    @staticmethod
    def generate_report(
        comparison: Dict, output_path: Path
    ) -> Path:
        """Generate comparison report.

        Args:
            comparison: Comparison dict
            output_path: Path to save report

        Returns:
            Path to saved report
        """
        report = {
            "title": "KONECTA Pipeline Version Comparison",
            "timestamp": datetime.now().isoformat(),
            "comparison": comparison,
        }

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Report saved to {output_path}")
        return output_path
