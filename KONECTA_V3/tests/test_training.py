"""Test model training and evaluation."""

import numpy as np
import pytest
from pathlib import Path

from vision_lab.training import BaselineTrainer, ExperimentTracker, ModelEvaluator


def test_baseline_trainer_init():
    """Test trainer initialization."""
    trainer = BaselineTrainer(n_estimators=50)
    assert trainer.n_estimators == 50
    assert trainer.model is None


def test_baseline_train(tmp_path):
    """Test model training."""
    trainer = BaselineTrainer(n_estimators=10)

    # Create dummy data
    X_train = np.random.rand(100, 50).astype(np.float32)
    y_train = np.array(["A"] * 50 + ["B"] * 50)

    metrics = trainer.train(X_train, y_train)

    assert trainer.model is not None
    assert "accuracy" in metrics
    assert metrics["accuracy"] >= 0.0
    assert metrics["accuracy"] <= 1.0


def test_baseline_evaluate(tmp_path):
    """Test model evaluation."""
    trainer = BaselineTrainer(n_estimators=10)

    # Train
    X_train = np.random.rand(100, 50).astype(np.float32)
    y_train = np.array(["A"] * 50 + ["B"] * 50)
    trainer.train(X_train, y_train)

    # Evaluate
    X_test = np.random.rand(20, 50).astype(np.float32)
    y_test = np.array(["A"] * 10 + ["B"] * 10)

    metrics = trainer.evaluate(X_test, y_test)

    assert "accuracy" in metrics
    assert "f1" in metrics
    assert "confusion_matrix" in metrics
    assert len(metrics["confusion_matrix"]) == 2


def test_baseline_predict(tmp_path):
    """Test predictions."""
    trainer = BaselineTrainer(n_estimators=10)

    # Train
    X_train = np.random.rand(100, 50).astype(np.float32)
    y_train = np.array(["A"] * 50 + ["B"] * 50)
    trainer.train(X_train, y_train)

    # Predict
    X_test = np.random.rand(20, 50).astype(np.float32)
    preds, probs = trainer.predict(X_test)

    assert len(preds) == 20
    assert preds.dtype.kind in ('U', 'O', 'S')  # String or object dtype
    assert probs.shape == (20, 2)


def test_baseline_feature_importance(tmp_path):
    """Test feature importance."""
    trainer = BaselineTrainer(n_estimators=10)

    # Train
    X_train = np.random.rand(100, 50).astype(np.float32)
    y_train = np.array(["A"] * 50 + ["B"] * 50)
    trainer.train(X_train, y_train)

    # Get importances
    importances = trainer.get_feature_importance(top_n=10)

    assert len(importances) == 10
    assert all(isinstance(idx, int) for idx, _ in importances)
    assert all(isinstance(imp, float) for _, imp in importances)


def test_baseline_save_load(tmp_path):
    """Test model save/load."""
    trainer = BaselineTrainer(n_estimators=10)

    # Train
    X_train = np.random.rand(100, 50).astype(np.float32)
    y_train = np.array(["A"] * 50 + ["B"] * 50)
    trainer.train(X_train, y_train)

    # Save
    model_path = tmp_path / "model.pkl"
    trainer.save(model_path)
    assert model_path.exists()

    # Load
    loaded = BaselineTrainer.load(model_path)
    assert loaded.model is not None
    assert loaded.classes is not None


def test_experiment_tracker_init(tmp_path):
    """Test experiment tracker initialization."""
    tracker = ExperimentTracker(output_dir=tmp_path)
    assert tracker.output_dir == tmp_path


def test_experiment_tracker_log(tmp_path):
    """Test logging experiments."""
    tracker = ExperimentTracker(output_dir=tmp_path)

    metrics = {"accuracy": 0.95, "f1": 0.94}
    exp = tracker.log_experiment(
        name="exp_001",
        features_type="baseline",
        model_type="random_forest",
        metrics=metrics,
    )

    assert exp["name"] == "exp_001"
    assert exp["features"] == "baseline"
    assert len(tracker.experiments) == 1


def test_experiment_tracker_compare(tmp_path):
    """Test comparing experiments."""
    tracker = ExperimentTracker(output_dir=tmp_path)

    # Log multiple experiments
    tracker.log_experiment(
        name="exp_001",
        features_type="baseline",
        model_type="rf",
        metrics={"accuracy": 0.90, "f1": 0.89},
    )
    tracker.log_experiment(
        name="exp_002",
        features_type="with_velocity",
        model_type="rf",
        metrics={"accuracy": 0.95, "f1": 0.94},
    )

    comparison = tracker.compare_experiments()
    assert comparison["total_experiments"] == 2
    assert len(comparison["experiments"]) == 2


def test_experiment_tracker_save(tmp_path):
    """Test saving comparison."""
    tracker = ExperimentTracker(output_dir=tmp_path)
    tracker.log_experiment(
        name="exp_001",
        features_type="baseline",
        model_type="rf",
        metrics={"accuracy": 0.90, "f1": 0.89},
    )

    path = tracker.save_comparison()
    assert path.exists()


def test_model_evaluator_per_class(tmp_path):
    """Test per-class metrics."""
    y_true = np.array(["A", "A", "A", "B", "B", "B"])
    y_pred = np.array(["A", "A", "B", "B", "B", "A"])

    metrics = ModelEvaluator.per_class_metrics(y_true, y_pred)

    assert "A" in metrics
    assert "B" in metrics
    assert "accuracy" in metrics["A"]


def test_model_evaluator_confusion(tmp_path):
    """Test confusion analysis."""
    cm = np.array([[8, 2], [1, 9]])
    classes = np.array(["A", "B"])

    analysis = ModelEvaluator.confusion_analysis(cm, classes)

    assert "top_confusions" in analysis
    assert len(analysis["top_confusions"]) > 0
