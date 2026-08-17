"""Test cross-signer evaluation."""

import numpy as np
import pytest

from vision_lab.cross_signer import CrossSignerEvaluator, PerClassAnalyzer, ErrorAnalysisReporter


def test_cross_signer_evaluator_init():
    """Test evaluator initialization."""
    evaluator = CrossSignerEvaluator()
    assert len(evaluator.results) == 0
    assert len(evaluator.per_signer_accuracy) == 0


def test_cross_signer_evaluate():
    """Test cross-signer evaluation."""
    evaluator = CrossSignerEvaluator()

    # Create dummy data with 3 signers
    X = np.random.rand(300, 50).astype(np.float32)
    y = np.array(["A"] * 150 + ["B"] * 150)
    signers = np.array(["S1"] * 100 + ["S2"] * 100 + ["S3"] * 100)

    results = evaluator.evaluate(X, y, signers, n_estimators=5)

    assert results["total_signers"] == 3
    assert len(results["signers"]) == 3
    assert results["mean_accuracy"] > 0
    assert results["mean_f1"] > 0


def test_cross_signer_problematic_signers():
    """Test identifying problematic signers."""
    evaluator = CrossSignerEvaluator()
    evaluator.per_signer_accuracy = {
        "S1": 0.95,
        "S2": 0.65,  # Below threshold
        "S3": 0.85,
    }

    problematic = evaluator.get_problematic_signers(threshold=0.70)
    assert len(problematic) == 1
    assert problematic[0][0] == "S2"


def test_cross_signer_best_worst():
    """Test getting best/worst signers."""
    evaluator = CrossSignerEvaluator()
    evaluator.per_signer_accuracy = {
        "S1": 0.95,
        "S2": 0.65,
        "S3": 0.85,
        "S4": 0.75,
        "S5": 0.90,
    }

    best = evaluator.get_best_signers(top_n=2)
    assert len(best) == 2
    assert best[0][0] == "S1"

    worst = evaluator.get_worst_signers(top_n=2)
    assert len(worst) == 2
    assert worst[0][0] == "S2"


def test_per_class_analyzer_init():
    """Test per-class analyzer initialization."""
    analyzer = PerClassAnalyzer()
    assert len(analyzer.per_class_metrics) == 0


def test_per_class_analyzer_analyze():
    """Test per-class analysis."""
    analyzer = PerClassAnalyzer()

    y_true = np.array(["A", "A", "A", "B", "B", "B", "C", "C", "C"])
    y_pred = np.array(["A", "A", "B", "B", "B", "A", "C", "C", "C"])

    results = analyzer.analyze(y_true, y_pred)

    assert "A" in results["classes"]
    assert "B" in results["classes"]
    assert "C" in results["classes"]


def test_per_class_difficult_classes():
    """Test identifying difficult classes."""
    analyzer = PerClassAnalyzer()
    analyzer.per_class_metrics = {
        "CLASS_A": {"accuracy": 0.95, "f1": 0.94},
        "CLASS_B": {"accuracy": 0.65, "f1": 0.63},  # Below threshold
        "CLASS_C": {"accuracy": 0.85, "f1": 0.84},
    }

    difficult = analyzer.get_difficult_classes(threshold=0.70)
    assert len(difficult) == 1
    assert difficult[0][0] == "CLASS_B"


def test_per_class_easy_classes():
    """Test identifying easy classes."""
    analyzer = PerClassAnalyzer()
    analyzer.per_class_metrics = {
        "A": {"accuracy": 0.95, "f1": 0.94},
        "B": {"accuracy": 0.65, "f1": 0.63},
        "C": {"accuracy": 0.85, "f1": 0.84},
    }

    easy = analyzer.get_easy_classes(top_n=2)
    assert len(easy) == 2
    assert easy[0][0] == "A"


def test_error_analysis_confusion_pairs():
    """Test confusion pair analysis."""
    cm = np.array([
        [8, 2, 0],
        [1, 9, 0],
        [0, 0, 10],
    ])
    classes = np.array(["A", "B", "C"])

    pairs = ErrorAnalysisReporter.confusion_pairs(cm, classes, top_n=5)
    assert len(pairs) > 0
    assert all("true_class" in p for p in pairs)


def test_error_analysis_report():
    """Test error report generation."""
    y_true = np.array(["A", "A", "A", "B", "B", "B"])
    y_pred = np.array(["A", "A", "B", "B", "B", "A"])
    classes = np.array(["A", "B"])
    cm = np.array([[2, 1], [1, 2]])

    report = ErrorAnalysisReporter.generate_report(y_true, y_pred, classes, cm)

    assert "accuracy" in report
    assert "f1" in report
    assert "confusion_pairs" in report
    assert "per_class" in report
    assert report["accuracy"] == pytest.approx(2/3, rel=1e-5)
