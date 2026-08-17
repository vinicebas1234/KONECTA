"""Model training and evaluation."""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Tuple, List, Optional

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)

logger = logging.getLogger(__name__)


class BaselineTrainer:
    """Train baseline Random Forest model."""

    def __init__(self, n_estimators: int = 100, random_state: int = 42):
        """Initialize trainer.

        Args:
            n_estimators: Number of trees in random forest
            random_state: Random seed for reproducibility
        """
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.model = None
        self.scaler = StandardScaler()
        self.classes = None
        self.training_time = 0
        self.history = {
            "train": [],
            "val": [],
            "test": [],
        }

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> Dict:
        """Train the model.

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features (optional)
            y_val: Validation labels (optional)

        Returns:
            Training metrics dict
        """
        logger.info(f"Training Random Forest with {self.n_estimators} estimators")
        start_time = time.time()

        # Fit scaler on train data
        X_train_scaled = self.scaler.fit_transform(X_train)

        # Store classes
        self.classes = np.unique(y_train)
        logger.info(f"Found {len(self.classes)} classes: {self.classes}")

        # Train model
        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,
            verbose=1,
        )
        self.model.fit(X_train_scaled, y_train)

        self.training_time = time.time() - start_time
        logger.info(f"Training complete in {self.training_time:.2f}s")

        # Evaluate on train
        metrics = self.evaluate(X_train, y_train, dataset_name="train")

        # Evaluate on val if provided
        if X_val is not None and y_val is not None:
            val_metrics = self.evaluate(X_val, y_val, dataset_name="val")
            metrics["val"] = val_metrics

        return metrics

    def evaluate(
        self, X: np.ndarray, y: np.ndarray, dataset_name: str = "test"
    ) -> Dict:
        """Evaluate model on dataset.

        Args:
            X: Features
            y: Labels
            dataset_name: Name of dataset (for logging)

        Returns:
            Metrics dict
        """
        if self.model is None:
            raise RuntimeError("Model not trained yet")

        X_scaled = self.scaler.transform(X)
        y_pred = self.model.predict(X_scaled)
        y_proba = self.model.predict_proba(X_scaled)

        # Compute metrics
        accuracy = accuracy_score(y, y_pred)
        precision = precision_score(y, y_pred, average="weighted", zero_division=0)
        recall = recall_score(y, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y, y_pred, average="weighted", zero_division=0)

        # Per-class metrics
        class_report = classification_report(
            y, y_pred, output_dict=True, zero_division=0
        )

        # Confusion matrix
        cm = confusion_matrix(y, y_pred)

        metrics = {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "class_report": class_report,
            "confusion_matrix": cm.tolist(),
            "n_samples": len(y),
        }

        logger.info(f"{dataset_name.upper()} Accuracy: {accuracy:.4f} | F1: {f1:.4f}")

        # Initialize key if not exists
        if dataset_name not in self.history:
            self.history[dataset_name] = []

        self.history[dataset_name].append(metrics)

        return metrics

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Make predictions.

        Args:
            X: Features

        Returns:
            (predictions, probabilities)
        """
        if self.model is None:
            raise RuntimeError("Model not trained yet")

        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)

        return predictions, probabilities

    def get_feature_importance(self, top_n: int = 20) -> List[Tuple[int, float]]:
        """Get top important features.

        Args:
            top_n: Number of top features to return

        Returns:
            List of (feature_index, importance) tuples
        """
        if self.model is None:
            raise RuntimeError("Model not trained yet")

        importances = self.model.feature_importances_
        indices = np.argsort(importances)[-top_n:][::-1]

        return [(int(idx), float(importances[idx])) for idx in indices]

    def save(self, path: Path) -> None:
        """Save model to disk.

        Args:
            path: Path to save model
        """
        import pickle

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb") as f:
            pickle.dump({"model": self.model, "scaler": self.scaler, "classes": self.classes}, f)

        logger.info(f"Model saved to {path}")

    @staticmethod
    def load(path: Path) -> "BaselineTrainer":
        """Load model from disk.

        Args:
            path: Path to model file

        Returns:
            Loaded trainer
        """
        import pickle

        with open(path, "rb") as f:
            data = pickle.load(f)

        trainer = BaselineTrainer()
        trainer.model = data["model"]
        trainer.scaler = data["scaler"]
        trainer.classes = data["classes"]

        logger.info(f"Model loaded from {path}")
        return trainer


class ExperimentTracker:
    """Track and compare experiments."""

    def __init__(self, output_dir: Path = None):
        """Initialize tracker.

        Args:
            output_dir: Where to save experiment data
        """
        self.output_dir = output_dir or Path("./experiments")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.experiments = []

    def log_experiment(
        self,
        name: str,
        features_type: str,
        model_type: str,
        metrics: Dict,
        hyperparams: Dict = None,
    ) -> Dict:
        """Log experiment.

        Args:
            name: Experiment name
            features_type: Type of features used
            model_type: Model type
            metrics: Evaluation metrics
            hyperparams: Hyperparameters (optional)

        Returns:
            Experiment dict
        """
        experiment = {
            "name": name,
            "timestamp": time.time(),
            "features": features_type,
            "model": model_type,
            "hyperparams": hyperparams or {},
            "metrics": metrics,
        }

        self.experiments.append(experiment)

        # Save to file
        exp_path = self.output_dir / f"{name}_experiment.json"
        with open(exp_path, "w") as f:
            json.dump(experiment, f, indent=2, default=str)

        logger.info(f"Experiment logged: {name}")
        return experiment

    def compare_experiments(self) -> Dict:
        """Compare all experiments.

        Returns:
            Comparison dict
        """
        if not self.experiments:
            return {"message": "No experiments to compare"}

        comparison = {
            "total_experiments": len(self.experiments),
            "experiments": [],
        }

        for exp in sorted(self.experiments, key=lambda x: x["metrics"].get("f1", 0), reverse=True):
            comparison["experiments"].append({
                "name": exp["name"],
                "features": exp["features"],
                "model": exp["model"],
                "accuracy": exp["metrics"].get("accuracy", 0),
                "f1": exp["metrics"].get("f1", 0),
                "recall": exp["metrics"].get("recall", 0),
                "precision": exp["metrics"].get("precision", 0),
            })

        return comparison

    def save_comparison(self, filename: str = "comparison.json") -> Path:
        """Save comparison to file.

        Args:
            filename: Output filename

        Returns:
            Path to saved file
        """
        comparison = self.compare_experiments()
        path = self.output_dir / filename

        with open(path, "w") as f:
            json.dump(comparison, f, indent=2, default=str)

        logger.info(f"Comparison saved to {path}")
        return path


class ModelEvaluator:
    """Detailed model evaluation."""

    @staticmethod
    def per_class_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
        """Compute per-class metrics.

        Args:
            y_true: True labels
            y_pred: Predicted labels

        Returns:
            Dict with per-class accuracy and F1
        """
        classes = np.unique(y_true)
        metrics = {}

        for cls in classes:
            mask = y_true == cls
            if np.sum(mask) == 0:
                continue

            cls_accuracy = accuracy_score(y_true[mask], y_pred[mask])
            cls_f1 = f1_score(
                y_true[mask], y_pred[mask], average="weighted", zero_division=0
            )

            metrics[cls] = {
                "accuracy": cls_accuracy,
                "f1": cls_f1,
                "count": int(np.sum(mask)),
            }

        return metrics

    @staticmethod
    def confusion_analysis(cm: np.ndarray, classes: np.ndarray) -> Dict:
        """Analyze confusion matrix.

        Args:
            cm: Confusion matrix
            classes: Class labels

        Returns:
            Analysis dict with top confusions
        """
        top_confusions = []

        # Find top confusion pairs
        for i in range(len(classes)):
            for j in range(len(classes)):
                if i != j and cm[i, j] > 0:
                    top_confusions.append({
                        "true_class": classes[i],
                        "predicted_class": classes[j],
                        "count": int(cm[i, j]),
                    })

        # Sort by count
        top_confusions = sorted(top_confusions, key=lambda x: x["count"], reverse=True)[:10]

        return {
            "top_confusions": top_confusions,
            "accuracy_diag": np.diag(cm).sum() / cm.sum(),
        }
