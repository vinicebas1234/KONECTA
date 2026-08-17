"""Cross-signer validation and analysis."""

import logging
from typing import Dict, List, Tuple, Optional
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from vision_lab.training import BaselineTrainer

logger = logging.getLogger(__name__)


class CrossSignerEvaluator:
    """Evaluate model generalization across signers."""

    def __init__(self):
        self.results = []
        self.per_signer_accuracy = {}
        self.per_signer_f1 = {}

    def evaluate(
        self,
        features: np.ndarray,
        labels: np.ndarray,
        signer_ids: np.ndarray,
        n_estimators: int = 100,
    ) -> Dict:
        """Evaluate model with leave-one-signer-out cross-validation.

        Args:
            features: Feature array (n_samples, n_features)
            labels: Class labels
            signer_ids: Signer ID for each sample
            n_estimators: Random Forest estimators

        Returns:
            Cross-validation results dict
        """
        unique_signers = np.unique(signer_ids)
        logger.info(f"Cross-signer evaluation with {len(unique_signers)} signers")

        results = {
            "total_signers": len(unique_signers),
            "signers": [],
            "overall_accuracy": 0.0,
            "overall_f1": 0.0,
            "mean_accuracy": 0.0,
            "std_accuracy": 0.0,
            "mean_f1": 0.0,
            "std_f1": 0.0,
        }

        all_accuracies = []
        all_f1s = []

        for test_signer in unique_signers:
            # Split: test on this signer, train on others
            test_mask = signer_ids == test_signer
            train_mask = ~test_mask

            X_train = features[train_mask]
            y_train = labels[train_mask]
            X_test = features[test_mask]
            y_test = labels[test_mask]

            if len(X_test) == 0:
                logger.warning(f"No test samples for signer {test_signer}")
                continue

            logger.info(f"Training on {len(X_train)} samples, testing on {len(X_test)} from signer {test_signer}")

            # Train
            trainer = BaselineTrainer(n_estimators=n_estimators)
            trainer.train(X_train, y_train)

            # Evaluate
            metrics = trainer.evaluate(X_test, y_test, dataset_name=f"signer_{test_signer}")

            accuracy = metrics["accuracy"]
            f1 = metrics["f1"]

            all_accuracies.append(accuracy)
            all_f1s.append(f1)

            self.per_signer_accuracy[test_signer] = accuracy
            self.per_signer_f1[test_signer] = f1

            results["signers"].append({
                "signer_id": str(test_signer),
                "n_train": len(X_train),
                "n_test": len(X_test),
                "accuracy": accuracy,
                "f1": f1,
                "precision": metrics["precision"],
                "recall": metrics["recall"],
            })

            self.results.append({
                "signer": test_signer,
                "accuracy": accuracy,
                "f1": f1,
            })

        # Compute overall statistics
        if all_accuracies:
            results["mean_accuracy"] = float(np.mean(all_accuracies))
            results["std_accuracy"] = float(np.std(all_accuracies))
            results["mean_f1"] = float(np.mean(all_f1s))
            results["std_f1"] = float(np.std(all_f1s))

            # Overall (train on all but one, test on that one)
            results["overall_accuracy"] = results["mean_accuracy"]
            results["overall_f1"] = results["mean_f1"]

        logger.info(f"Cross-signer mean accuracy: {results['mean_accuracy']:.4f} ± {results['std_accuracy']:.4f}")
        logger.info(f"Cross-signer mean F1: {results['mean_f1']:.4f} ± {results['std_f1']:.4f}")

        return results

    def get_problematic_signers(self, threshold: float = 0.70) -> List[Tuple[str, float]]:
        """Get signers with performance below threshold.

        Args:
            threshold: Accuracy threshold

        Returns:
            List of (signer_id, accuracy) tuples
        """
        problematic = []
        for signer, acc in self.per_signer_accuracy.items():
            if acc < threshold:
                problematic.append((str(signer), acc))

        return sorted(problematic, key=lambda x: x[1])

    def get_best_signers(self, top_n: int = 5) -> List[Tuple[str, float]]:
        """Get signers with best performance.

        Args:
            top_n: Number of top signers

        Returns:
            List of (signer_id, accuracy) tuples
        """
        sorted_signers = sorted(self.per_signer_accuracy.items(), key=lambda x: x[1], reverse=True)
        return [(str(signer), acc) for signer, acc in sorted_signers[:top_n]]

    def get_worst_signers(self, top_n: int = 5) -> List[Tuple[str, float]]:
        """Get signers with worst performance.

        Args:
            top_n: Number of worst signers

        Returns:
            List of (signer_id, accuracy) tuples
        """
        sorted_signers = sorted(self.per_signer_accuracy.items(), key=lambda x: x[1])
        return [(str(signer), acc) for signer, acc in sorted_signers[:top_n]]


class PerClassAnalyzer:
    """Analyze performance per class."""

    def __init__(self):
        self.per_class_metrics = {}

    def analyze(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
        """Analyze per-class performance.

        Args:
            y_true: True labels
            y_pred: Predicted labels

        Returns:
            Per-class metrics dict
        """
        classes = np.unique(y_true)
        results = {"classes": {}}

        for cls in classes:
            mask = y_true == cls
            if np.sum(mask) == 0:
                continue

            cls_accuracy = accuracy_score(y_true[mask], y_pred[mask])
            cls_f1 = f1_score(
                y_true[mask], y_pred[mask], average="weighted", zero_division=0
            )
            cls_precision = precision_score(
                y_true[mask], y_pred[mask], average="weighted", zero_division=0
            )
            cls_recall = recall_score(
                y_true[mask], y_pred[mask], average="weighted", zero_division=0
            )

            results["classes"][str(cls)] = {
                "accuracy": cls_accuracy,
                "f1": cls_f1,
                "precision": cls_precision,
                "recall": cls_recall,
                "n_samples": int(np.sum(mask)),
            }

            self.per_class_metrics[cls] = {
                "accuracy": cls_accuracy,
                "f1": cls_f1,
            }

        return results

    def get_difficult_classes(self, threshold: float = 0.70) -> List[Tuple[str, float]]:
        """Get classes with performance below threshold.

        Args:
            threshold: Accuracy threshold

        Returns:
            List of (class_id, accuracy) tuples
        """
        difficult = []
        for cls, metrics in self.per_class_metrics.items():
            if metrics["accuracy"] < threshold:
                difficult.append((str(cls), metrics["accuracy"]))

        return sorted(difficult, key=lambda x: x[1])

    def get_easy_classes(self, top_n: int = 10) -> List[Tuple[str, float]]:
        """Get classes with best performance.

        Args:
            top_n: Number of top classes

        Returns:
            List of (class_id, accuracy) tuples
        """
        sorted_classes = sorted(
            self.per_class_metrics.items(), key=lambda x: x[1]["accuracy"], reverse=True
        )
        return [(str(cls), metrics["accuracy"]) for cls, metrics in sorted_classes[:top_n]]


class ErrorAnalysisReporter:
    """Generate detailed error analysis reports."""

    @staticmethod
    def confusion_pairs(cm: np.ndarray, classes: np.ndarray, top_n: int = 10) -> List[Dict]:
        """Get top confusion pairs.

        Args:
            cm: Confusion matrix
            classes: Class labels
            top_n: Number of top pairs

        Returns:
            List of confusion pair dicts
        """
        pairs = []

        for i in range(len(classes)):
            for j in range(len(classes)):
                if i != j and cm[i, j] > 0:
                    pairs.append({
                        "true_class": str(classes[i]),
                        "predicted_class": str(classes[j]),
                        "count": int(cm[i, j]),
                        "error_rate": float(cm[i, j] / np.sum(cm[i, :])),
                    })

        return sorted(pairs, key=lambda x: x["count"], reverse=True)[:top_n]

    @staticmethod
    def generate_report(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        classes: np.ndarray,
        cm: np.ndarray,
    ) -> Dict:
        """Generate comprehensive error report.

        Args:
            y_true: True labels
            y_pred: Predicted labels
            classes: Class labels
            cm: Confusion matrix

        Returns:
            Error report dict
        """
        report = {
            "accuracy": accuracy_score(y_true, y_pred),
            "f1": f1_score(y_true, y_pred, average="weighted", zero_division=0),
            "total_errors": int(np.sum(y_true != y_pred)),
            "error_rate": float(np.mean(y_true != y_pred)),
            "confusion_pairs": ErrorAnalysisReporter.confusion_pairs(cm, classes),
        }

        # Per-class error analysis
        report["per_class"] = {}
        for i, cls in enumerate(classes):
            mask = y_true == cls
            cls_correct = np.sum(y_pred[mask] == cls)
            cls_total = np.sum(mask)

            if cls_total > 0:
                report["per_class"][str(cls)] = {
                    "correct": int(cls_correct),
                    "total": int(cls_total),
                    "accuracy": float(cls_correct / cls_total),
                    "error_count": int(cls_total - cls_correct),
                }

        return report
