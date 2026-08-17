"""Test real-time recognition."""

import numpy as np
import pytest

from vision_lab.realtime import TemporalBuffer, RealtimeRecognizer
from vision_lab.training import BaselineTrainer


def test_temporal_buffer_init():
    """Test buffer initialization."""
    buffer = TemporalBuffer(window_size=5)
    assert buffer.window_size == 5
    assert len(buffer.buffer) == 0


def test_temporal_buffer_add_prediction():
    """Test adding predictions."""
    buffer = TemporalBuffer(window_size=5, confidence_threshold=0.5)

    # Low confidence - should not be added
    result = buffer.add_prediction("CASA", 0.3)
    assert result is None

    # High confidence - should be added
    result = buffer.add_prediction("CASA", 0.9)
    assert result is None  # Need multiple predictions for consensus


def test_temporal_buffer_consensus():
    """Test consensus voting."""
    buffer = TemporalBuffer(window_size=5, confidence_threshold=0.5)

    # Add same prediction multiple times
    for _ in range(3):
        result = buffer.add_prediction("CASA", 0.9)

    # Should have consensus now
    assert result == "CASA"


def test_temporal_buffer_mixed_predictions():
    """Test mixed predictions."""
    buffer = TemporalBuffer(window_size=5, confidence_threshold=0.5)

    # Add conflicting predictions
    buffer.add_prediction("CASA", 0.9)
    buffer.add_prediction("CARRO", 0.9)
    result = buffer.add_prediction("CASA", 0.9)

    # CASA appears 2/3 times - should win
    assert result == "CASA"


def test_temporal_buffer_reset():
    """Test buffer reset."""
    buffer = TemporalBuffer(window_size=5)

    buffer.add_prediction("CASA", 0.9)
    assert len(buffer.prediction_buffer) > 0

    buffer.reset()
    assert len(buffer.buffer) == 0
    assert len(buffer.prediction_buffer) == 0


def test_realtime_recognizer_init():
    """Test recognizer initialization."""
    trainer = BaselineTrainer(n_estimators=5)

    # Need to train first
    X_train = np.random.rand(50, 50).astype(np.float32)
    y_train = np.array(["A"] * 25 + ["B"] * 25)
    trainer.train(X_train, y_train)

    recognizer = RealtimeRecognizer(model=trainer)
    assert recognizer.model is not None
    assert recognizer.fps_target == 30


def test_realtime_recognizer_process_frame():
    """Test frame processing."""
    trainer = BaselineTrainer(n_estimators=5)

    X_train = np.random.rand(50, 50).astype(np.float32)
    y_train = np.array(["A"] * 25 + ["B"] * 25)
    trainer.train(X_train, y_train)

    recognizer = RealtimeRecognizer(model=trainer)

    # Create dummy frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Should handle gracefully (no landmarks detected)
    prediction, confidence, latency = recognizer.process_frame(frame)

    assert prediction is None or isinstance(prediction, str)
    assert 0 <= confidence <= 1.0
    assert latency >= 0


def test_realtime_recognizer_latency():
    """Test latency tracking."""
    trainer = BaselineTrainer(n_estimators=5)

    X_train = np.random.rand(50, 50).astype(np.float32)
    y_train = np.array(["A"] * 25 + ["B"] * 25)
    trainer.train(X_train, y_train)

    recognizer = RealtimeRecognizer(model=trainer)

    # Process multiple frames
    for _ in range(5):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        recognizer.process_frame(frame)

    avg_latency = recognizer.get_average_latency()
    assert avg_latency >= 0


def test_realtime_recognizer_fps():
    """Test FPS tracking."""
    trainer = BaselineTrainer(n_estimators=5)

    X_train = np.random.rand(50, 50).astype(np.float32)
    y_train = np.array(["A"] * 25 + ["B"] * 25)
    trainer.train(X_train, y_train)

    recognizer = RealtimeRecognizer(model=trainer, fps_target=30)

    avg_fps = recognizer.get_average_fps()
    assert avg_fps >= 0
