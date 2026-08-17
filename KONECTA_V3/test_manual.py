"""Manual testing of the complete pipeline."""

import numpy as np
from pathlib import Path
from vision_lab.core import Frame, Video
from vision_lab.landmarks import LandmarkExtractor
from vision_lab.processing import (
    LandmarkCleaner,
    LandmarkSmoother,
    LandmarkNormalizer,
)
from vision_lab.features import FeatureExtractor
from vision_lab.training import BaselineTrainer
from vision_lab.experiments import ExperimentManager, ExperimentConfig
from vision_lab.visualization import QualityAnalyzer


def test_complete_pipeline():
    """Test the complete pipeline from landmarks to experiments."""

    print("\n" + "="*70)
    print("[TEST] KONECTA V3 - COMPLETE PIPELINE TEST")
    print("="*70)

    # ========================================
    # FASE 1: Generate synthetic landmarks
    # ========================================
    print("\n[OK] FASE 1: Generating synthetic landmarks...")

    # Create dummy frames with synthetic landmarks
    n_frames = 100
    n_classes = 3
    classes = ["CASA", "CARRO", "LIVRO"]

    landmarks_data = []
    labels = []

    # Generate synthetic data
    for frame_id in range(n_frames):
        # Random landmarks (228 = 76 points × 3)
        landmarks = np.random.randn(228).astype(np.float32)
        landmarks_data.append(landmarks)
        labels.append(classes[frame_id % n_classes])

    landmarks_array = np.array(landmarks_data)
    labels_array = np.array(labels)

    print(f"   Generated: {landmarks_array.shape}")
    print(f"   Classes: {set(labels_array)}")

    # ========================================
    # FASE 2: Quality Analysis
    # ========================================
    print("\n[OK] FASE 2: Quality analysis...")

    analyzer = QualityAnalyzer()
    quality_scores = []

    for landmarks in landmarks_array[:10]:
        # Create a dummy frame
        frame = Frame(0, 0, np.zeros((480, 640, 3), dtype=np.uint8))
        frame.landmarks = landmarks
        result = analyzer.analyze_frame(frame)
        quality_scores.append(result['score'])

    avg_quality = np.mean(quality_scores)
    print(f"   Average quality: {avg_quality:.1f}/100")

    # ========================================
    # FASE 3: Processing
    # ========================================
    print("\n[OK] FASE 3: Processing landmarks...")

    # Apply normalization to each frame
    landmarks_normalized_list = []
    for lm in landmarks_array:
        norm = LandmarkNormalizer.normalize_body_centered(lm)
        norm = LandmarkNormalizer.normalize_scale(norm)
        landmarks_normalized_list.append(norm)

    landmarks_normalized = np.array(landmarks_normalized_list)

    print(f"   Original: {landmarks_array.shape}")
    print(f"   Normalized: {landmarks_normalized.shape}")

    # ========================================
    # FASE 4: Feature Engineering
    # ========================================
    print("\n[OK] FASE 4: Feature engineering...")

    # For simplicity, use normalized landmarks as features
    features_raw = landmarks_normalized.astype(np.float32)

    # Compute velocity features (delta between frames)
    features_vel = np.zeros_like(features_raw)
    features_vel[1:] = np.diff(features_raw, axis=0)

    print(f"   RAW Features: {features_raw.shape}")
    print(f"   VELOCITY Features: {features_vel.shape}")

    # ========================================
    # FASE 5: Training
    # ========================================
    print("\n[OK] FASE 5: Model training...")

    # Split data
    n_train = int(0.7 * len(features_raw))
    n_val = int(0.1 * len(features_raw))

    X_train = features_raw[:n_train]
    y_train = labels_array[:n_train]
    X_val = features_raw[n_train:n_train+n_val]
    y_val = labels_array[n_train:n_train+n_val]
    X_test = features_raw[n_train+n_val:]
    y_test = labels_array[n_train+n_val:]

    trainer = BaselineTrainer(n_estimators=10)
    train_metrics = trainer.train(X_train, y_train, X_val, y_val)
    test_metrics = trainer.evaluate(X_test, y_test, dataset_name="test")

    print(f"   Train Accuracy: {train_metrics['accuracy']:.4f}")
    print(f"   Train F1: {train_metrics['f1']:.4f}")
    print(f"   Test Accuracy: {test_metrics['accuracy']:.4f}")
    print(f"   Test F1: {test_metrics['f1']:.4f}")

    # ========================================
    # FASE 8: Experiment Logging
    # ========================================
    print("\n[OK] FASE 8: Experiment tracking...")

    manager = ExperimentManager(output_dir=Path("./experiments"))

    config = ExperimentConfig(
        name="manual_test_raw",
        description="Manual test with RAW_XYZ features",
        features_type="RAW_XYZ",
        model_type="RandomForest",
        dataset_name="synthetic",
        hyperparams={"n_estimators": 10},
    )

    result = manager.log_experiment(
        config=config,
        train_metrics=train_metrics,
        val_metrics=None,
        test_metrics=test_metrics,
        training_time=trainer.training_time,
        notes="Manual end-to-end test"
    )

    print(f"   Experiment logged: {config.name}")
    print(f"   Saved to: ./experiments/")

    # Test with VELOCITY features (already created above)

    X_train_vel = features_vel[:n_train]
    X_val_vel = features_vel[n_train:n_train+n_val]
    X_test_vel = features_vel[n_train+n_val:]

    trainer2 = BaselineTrainer(n_estimators=10)
    train_metrics2 = trainer2.train(X_train_vel, y_train, X_val_vel, y_val)
    test_metrics2 = trainer2.evaluate(X_test_vel, y_test, dataset_name="test")

    config2 = ExperimentConfig(
        name="manual_test_velocity",
        description="Manual test with VELOCITY features",
        features_type="VELOCITY",
        model_type="RandomForest",
        dataset_name="synthetic",
        hyperparams={"n_estimators": 10},
    )

    manager.log_experiment(
        config=config2,
        train_metrics=train_metrics2,
        test_metrics=test_metrics2,
        training_time=trainer2.training_time,
    )

    # ========================================
    # Compare Experiments
    # ========================================
    print("\n[OK] COMPARACAO DE EXPERIMENTOS:")

    comparison = manager.compare_experiments(metric="f1")
    print(f"   Total experiments: {comparison['total_experiments']}")

    for exp in comparison['all_experiments']:
        print(f"   - {exp['name']}: F1={exp['f1']:.4f}, Accuracy={exp['accuracy']:.4f}")

    # Generate reports
    csv_path = manager.save_comparison_csv()
    html_path = manager.save_comparison_html()

    print(f"\n   CSV Report: {csv_path}")
    print(f"   HTML Report: {html_path}")

    # ========================================
    # Summary
    # ========================================
    print("\n" + "="*70)
    print("[SUCCESS] PIPELINE TEST COMPLETED SUCCESSFULLY!")
    print("="*70)
    print(f"[OK] Landmarks processed: {len(landmarks_array)}")
    print(f"[OK] Classes: {set(labels_array)}")
    print(f"[OK] Models trained: 2")
    print(f"[OK] Experiments logged: {comparison['total_experiments']}")
    print(f"[OK] Reports generated: CSV, HTML")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_complete_pipeline()
