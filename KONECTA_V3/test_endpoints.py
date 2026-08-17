#!/usr/bin/env python
"""Test KONECTA V3 API endpoints"""

import requests
import numpy as np
import json

BASE_URL = "http://localhost:8000"

print("=" * 70)
print("KONECTA V3 - API ENDPOINT TESTS")
print("=" * 70)

# Test 1: Health
print("\n[TEST 1] Health Check")
response = requests.get(f"{BASE_URL}/health")
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

# Test 2: List Models (empty)
print("\n[TEST 2] List Models (should be empty)")
response = requests.get(f"{BASE_URL}/api/models")
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

# Test 3: Train Model
print("\n[TEST 3] Train Model")
X_train = np.random.randn(10, 228).tolist()
y_train = ["CASA"] * 5 + ["CARRO"] * 5

response = requests.post(
    f"{BASE_URL}/api/models/train",
    json={
        "model_name": "test_model_1",
        "n_estimators": 10,
        "X_train": X_train,
        "y_train": y_train
    }
)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

# Test 4: Predict
print("\n[TEST 4] Make Prediction")
landmarks = np.random.randn(228).tolist()

response = requests.post(
    f"{BASE_URL}/api/models/test_model_1/predict",
    json={
        "model_name": "test_model_1",
        "landmarks": landmarks
    }
)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

# Test 5: List Models (should have one now)
print("\n[TEST 5] List Models (should have one)")
response = requests.get(f"{BASE_URL}/api/models")
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

# Test 6: Log Experiment
print("\n[TEST 6] Log Experiment")
response = requests.post(
    f"{BASE_URL}/api/experiments/log",
    json={
        "name": "experiment_1",
        "description": "First experiment",
        "features_type": "RAW_XYZ",
        "model_type": "RandomForest",
        "dataset_name": "V-LIBRASIL",
        "train_accuracy": 0.90,
        "train_f1": 0.88,
        "test_accuracy": 0.85,
        "test_f1": 0.83
    }
)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

# Test 7: List Experiments
print("\n[TEST 7] List Experiments")
response = requests.get(f"{BASE_URL}/api/experiments")
print(f"Status: {response.status_code}")
data = response.json()
print(f"Total experiments: {data.get('total_experiments', 0)}")
if data.get('all_experiments'):
    print(f"First experiment: {json.dumps(data['all_experiments'][0], indent=2)}")

# Test 8: Get Best Experiment
print("\n[TEST 8] Get Best Experiment")
response = requests.get(f"{BASE_URL}/api/experiments/best")
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

print("\n" + "=" * 70)
print("ALL TESTS COMPLETED!")
print("=" * 70)
