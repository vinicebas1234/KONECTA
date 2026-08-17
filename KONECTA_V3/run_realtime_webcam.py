#!/usr/bin/env python
"""Run real-time webcam recognition"""

from vision_lab.training import BaselineTrainer
from vision_lab.realtime import RealtimeRecognizer
import numpy as np

print("=" * 80)
print("KONECTA V3 - REAL-TIME WEBCAM RECOGNITION")
print("=" * 80)

# ============================================
# STEP 1: Train a model
# ============================================

print("\n[STEP 1] Training model with synthetic data...")
print("This will take a few seconds...")

X_train = np.random.randn(100, 228).astype(np.float32)
y_train = np.array(["CASA"] * 50 + ["CARRO"] * 50)

trainer = BaselineTrainer(n_estimators=50)
metrics = trainer.train(X_train, y_train)

print(f"✅ Model trained!")
print(f"   Train Accuracy: {metrics['accuracy']:.4f}")
print(f"   Train F1: {metrics['f1']:.4f}")

# ============================================
# STEP 2: Start real-time recognition
# ============================================

print("\n[STEP 2] Starting webcam recognition...")
print("=" * 80)
print("CONTROLS:")
print("  - Webcam will open in a new window")
print("  - Shows real-time body pose detection")
print("  - Shows prediction and confidence")
print("  - Press ESC or 'q' to exit")
print("=" * 80)

recognizer = RealtimeRecognizer(model=trainer, fps_target=30)

try:
    recognizer.run(camera_id=0, display=True)
except Exception as e:
    print(f"Error: {e}")
    print("Make sure your webcam is connected and available.")

print("\n✅ Webcam recognition stopped!")
print(f"Average FPS: {recognizer.get_average_fps():.1f}")
print(f"Average Latency: {recognizer.get_average_latency():.1f}ms")

print("\n" + "=" * 80)
