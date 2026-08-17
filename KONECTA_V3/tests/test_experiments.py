"""Test experiment management."""

import json
import pytest
from pathlib import Path

from vision_lab.experiments import (
    ExperimentConfig,
    ExperimentResult,
    ExperimentManager,
    PipelineComparator,
)


def test_experiment_config():
    """Test experiment configuration."""
    config = ExperimentConfig(
        name="test_exp",
        description="Test experiment",
        features_type="RAW_XYZ",
        model_type="RandomForest",
        dataset_name="train_set",
        hyperparams={"n_estimators": 100},
    )

    assert config.name == "test_exp"
    assert config.version == "V3"
    assert "n_estimators" in config.hyperparams


def test_experiment_result():
    """Test experiment result."""
    config = ExperimentConfig(
        name="test_exp",
        description="Test",
        features_type="RAW_XYZ",
        model_type="RandomForest",
        dataset_name="train_set",
        hyperparams={},
    )

    result = ExperimentResult(
        config=config,
        timestamp=1234567890.0,
        train_metrics={"accuracy": 0.9, "f1": 0.88},
        val_metrics={"accuracy": 0.85, "f1": 0.83},
        test_metrics=None,
        cross_signer_metrics=None,
        training_time=10.5,
    )

    assert result.config.name == "test_exp"
    assert result.training_time == 10.5
    assert result.train_metrics["accuracy"] == 0.9


def test_experiment_manager_init(tmp_path):
    """Test manager initialization."""
    manager = ExperimentManager(output_dir=tmp_path)

    assert manager.output_dir == tmp_path
    assert len(manager.experiments) == 0


def test_experiment_manager_log(tmp_path):
    """Test logging experiment."""
    manager = ExperimentManager(output_dir=tmp_path)

    config = ExperimentConfig(
        name="exp1",
        description="First experiment",
        features_type="RAW_XYZ",
        model_type="RandomForest",
        dataset_name="train_set",
        hyperparams={"n_estimators": 50},
    )

    result = manager.log_experiment(
        config=config,
        train_metrics={"accuracy": 0.9, "f1": 0.88},
        training_time=15.0,
    )

    assert len(manager.experiments) == 1
    assert result.config.name == "exp1"

    # Check file was saved
    saved_files = list(tmp_path.glob("*.json"))
    assert len(saved_files) == 1


def test_experiment_manager_multiple(tmp_path):
    """Test logging multiple experiments."""
    manager = ExperimentManager(output_dir=tmp_path)

    for i in range(3):
        config = ExperimentConfig(
            name=f"exp_{i}",
            description=f"Experiment {i}",
            features_type="RAW_XYZ",
            model_type="RandomForest",
            dataset_name="train_set",
            hyperparams={"n_estimators": 100 + i * 10},
        )

        manager.log_experiment(
            config=config,
            train_metrics={"accuracy": 0.8 + i * 0.05, "f1": 0.75 + i * 0.05},
            training_time=10.0 + i,
        )

    assert len(manager.experiments) == 3


def test_experiment_manager_get_best(tmp_path):
    """Test getting best experiment."""
    manager = ExperimentManager(output_dir=tmp_path)

    # Log experiments with different metrics
    for i, f1_score in enumerate([0.70, 0.85, 0.92]):
        config = ExperimentConfig(
            name=f"exp_{i}",
            description=f"Exp {i}",
            features_type="RAW_XYZ",
            model_type="RandomForest",
            dataset_name="train_set",
            hyperparams={},
        )

        manager.log_experiment(
            config=config,
            train_metrics={"accuracy": f1_score - 0.05, "f1": f1_score},
            training_time=10.0,
        )

    best = manager.get_best_experiment(metric="f1", dataset="train")
    assert best is not None
    assert best.config.name == "exp_2"


def test_experiment_manager_compare(tmp_path):
    """Test comparing experiments."""
    manager = ExperimentManager(output_dir=tmp_path)

    for i in range(3):
        config = ExperimentConfig(
            name=f"exp_{i}",
            description=f"Exp {i}",
            features_type="VELOCITY" if i % 2 == 0 else "RAW_XYZ",
            model_type="RandomForest",
            dataset_name="train_set",
            hyperparams={},
        )

        manager.log_experiment(
            config=config,
            train_metrics={"accuracy": 0.8, "f1": 0.75},
            test_metrics={"accuracy": 0.75, "f1": 0.70},
            training_time=10.0,
        )

    comparison = manager.compare_experiments(metric="f1")

    assert comparison["total_experiments"] == 3
    assert len(comparison["all_experiments"]) == 3


def test_experiment_manager_filter_by_features(tmp_path):
    """Test filtering by features."""
    manager = ExperimentManager(output_dir=tmp_path)

    for features in ["RAW_XYZ", "VELOCITY", "RAW_XYZ"]:
        config = ExperimentConfig(
            name=f"exp_{features}",
            description="Test",
            features_type=features,
            model_type="RandomForest",
            dataset_name="train_set",
            hyperparams={},
        )

        manager.log_experiment(
            config=config,
            train_metrics={"accuracy": 0.8, "f1": 0.75},
            training_time=10.0,
        )

    raw_exps = manager.get_by_features("RAW_XYZ")
    assert len(raw_exps) == 2

    vel_exps = manager.get_by_features("VELOCITY")
    assert len(vel_exps) == 1


def test_experiment_manager_filter_by_model(tmp_path):
    """Test filtering by model."""
    manager = ExperimentManager(output_dir=tmp_path)

    models = ["RandomForest", "SVM", "RandomForest"]

    for model in models:
        config = ExperimentConfig(
            name=f"exp_{model}",
            description="Test",
            features_type="RAW_XYZ",
            model_type=model,
            dataset_name="train_set",
            hyperparams={},
        )

        manager.log_experiment(
            config=config,
            train_metrics={"accuracy": 0.8, "f1": 0.75},
            training_time=10.0,
        )

    rf_exps = manager.get_by_model("RandomForest")
    assert len(rf_exps) == 2

    svm_exps = manager.get_by_model("SVM")
    assert len(svm_exps) == 1


def test_experiment_manager_save_csv(tmp_path):
    """Test saving comparison to CSV."""
    manager = ExperimentManager(output_dir=tmp_path)

    config = ExperimentConfig(
        name="exp_1",
        description="Test",
        features_type="RAW_XYZ",
        model_type="RandomForest",
        dataset_name="train_set",
        hyperparams={},
    )

    manager.log_experiment(
        config=config,
        train_metrics={"accuracy": 0.9, "f1": 0.88},
        test_metrics={"accuracy": 0.85, "f1": 0.83},
        training_time=10.0,
    )

    csv_path = manager.save_comparison_csv()

    assert csv_path.exists()
    with open(csv_path) as f:
        content = f.read()
        assert "exp_1" in content


def test_experiment_manager_save_html(tmp_path):
    """Test saving comparison to HTML."""
    manager = ExperimentManager(output_dir=tmp_path)

    config = ExperimentConfig(
        name="exp_1",
        description="Test",
        features_type="RAW_XYZ",
        model_type="RandomForest",
        dataset_name="train_set",
        hyperparams={},
    )

    manager.log_experiment(
        config=config,
        train_metrics={"accuracy": 0.9, "f1": 0.88},
        test_metrics={"accuracy": 0.85, "f1": 0.83},
        training_time=10.0,
    )

    html_path = manager.save_comparison_html()

    assert html_path.exists()
    with open(html_path) as f:
        content = f.read()
        assert "KONECTA V3" in content
        assert "Experiment Comparison" in content


def test_pipeline_comparator():
    """Test pipeline version comparator."""
    v1_results = {"accuracy": 0.75, "f1": 0.70}
    v2_results = {"accuracy": 0.82, "f1": 0.80}
    v3_results = {"accuracy": 0.90, "f1": 0.88}

    comparison = PipelineComparator.compare_versions(
        v1_results=v1_results,
        v2_results=v2_results,
        v3_results=v3_results,
    )

    assert "v1" in comparison
    assert "v2" in comparison
    assert "v3" in comparison
    assert "v1_to_v2_improvement" in comparison
    assert "v2_to_v3_improvement" in comparison


def test_pipeline_comparator_improvement_calculation():
    """Test improvement calculation."""
    v1 = {"f1": 0.80}
    v2 = {"f1": 0.90}

    comparison = PipelineComparator.compare_versions(
        v1_results=v1,
        v2_results=v2,
        v3_results=None,
    )

    improvement = comparison["v1_to_v2_improvement"]
    assert improvement == pytest.approx(12.5, abs=0.1)


def test_pipeline_comparator_report(tmp_path):
    """Test generating comparison report."""
    v1 = {"accuracy": 0.75, "f1": 0.70}
    v2 = {"accuracy": 0.82, "f1": 0.80}
    v3 = {"accuracy": 0.90, "f1": 0.88}

    comparison = PipelineComparator.compare_versions(v1, v2, v3)

    report_path = tmp_path / "report.json"
    PipelineComparator.generate_report(comparison, report_path)

    assert report_path.exists()

    with open(report_path) as f:
        report = json.load(f)
        assert "title" in report
        assert "comparison" in report
