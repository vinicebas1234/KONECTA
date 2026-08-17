#!/usr/bin/env python
"""Test capture and recognition endpoints"""

import requests
import cv2
import numpy as np
from pathlib import Path
import json

BASE_URL = "http://localhost:8000"

print("=" * 80)
print("KONECTA V3 - CAPTURE & RECOGNITION TESTS")
print("=" * 80 + "\n")

# ============================================
# OPTION 1: WITH VIDEO FILE
# ============================================

print("\n" + "="*80)
print("OPTION 1: EXTRACTION FROM VIDEO FILE")
print("="*80)

# Create a dummy video for testing
print("\n[STEP 1] Creating dummy video for testing...")
output_path = "test_video.mp4"

# Create a simple video with 30 frames
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(output_path, fourcc, 30.0, (640, 480))

for i in range(30):
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    # Add some text
    cv2.putText(frame, f"Frame {i}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    out.write(frame)

out.release()
print(f"[OK] Video created: {output_path}")

# ============================================
# TEST 1: Discover Dataset
# ============================================

print("\n[TEST 1] Discover Dataset")
print("-" * 80)

response = requests.post(
    f"{BASE_URL}/api/datasets/discover",
    json={"path": "."}
)

print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

# ============================================
# TEST 2: Extract Landmarks from Video
# ============================================

print("\n[TEST 2] Extract Landmarks from Video")
print("-" * 80)

video_id = "test_video"

response = requests.post(
    f"{BASE_URL}/api/videos/{video_id}/extract-landmarks"
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    print(f"[OK] Landmarks extracted!")
    print(f"   Total frames: {data.get('total_frames', 0)}")
    print(f"   Valid frames: {data.get('valid_frames', 0)}")
    print(f"   Detection rate: {data.get('detection_rate', 0):.2%}")
else:
    print(f"Error: {response.text}")

# ============================================
# TEST 3: Get Quality Analysis
# ============================================

print("\n[TEST 3] Get Quality Analysis")
print("-" * 80)

response = requests.get(
    f"{BASE_URL}/api/videos/{video_id}/quality"
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Total frames analyzed: {len(data.get('frames', []))}")
    if data.get('frames'):
        first_frame = data['frames'][0]
        print(f"\nFirst frame quality:")
        print(f"  Score: {first_frame.get('score', 0)}")
        print(f"  Status: {first_frame.get('status', 'unknown')}")
else:
    print(f"Error: {response.text}")

# ============================================
# TEST 4: Get Temporal Analysis
# ============================================

print("\n[TEST 4] Get Temporal Analysis")
print("-" * 80)

response = requests.get(
    f"{BASE_URL}/api/videos/{video_id}/temporal"
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Temporal Analysis Report:")
    print(json.dumps(data, indent=2))
else:
    print(f"Error: {response.text}")

# ============================================
# OPTION 2: REAL-TIME WEBCAM
# ============================================

print("\n\n" + "="*80)
print("OPTION 2: REAL-TIME WEBCAM RECOGNITION")
print("="*80)

print("\n[INFO] Para testar webcam em tempo real, use este código Python:")
print("""
from vision_lab.training import BaselineTrainer
from vision_lab.realtime import RealtimeRecognizer
import numpy as np

# 1. Train a model first
print("[1] Training model...")
X_train = np.random.randn(100, 228).astype(np.float32)
y_train = np.array(["CASA"] * 50 + ["CARRO"] * 50)
trainer = BaselineTrainer()
trainer.train(X_train, y_train)

# 2. Start real-time recognition
print("[2] Starting webcam recognition...")
recognizer = RealtimeRecognizer(model=trainer)
recognizer.run(camera_id=0, display=True)
# Press ESC to exit
""")

print("\nOu use o arquivo de teste pronto:")
print("  python run_realtime_webcam.py")

# ============================================
# TEST 5: Extract Frame with Landmarks
# ============================================

print("\n[TEST 5] Get Frame with Landmarks Overlay")
print("-" * 80)

response = requests.get(
    f"{BASE_URL}/api/videos/{video_id}/frame/0?with_landmarks=true"
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    print("[OK] Frame retrieved with landmarks overlay!")
    # Save the frame
    data = response.json()
    print(f"   Frame ID: {data.get('frame_id')}")
    print(f"   Image size: {len(data.get('image', '')) // 1024}KB")
else:
    print(f"Error: {response.text}")

print("\n" + "="*80)
print("ALL TESTS COMPLETED!")
print("="*80)
