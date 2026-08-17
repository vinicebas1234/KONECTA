"""Real-time recognition from webcam."""

import logging
import time
from collections import deque
from typing import Optional, Tuple, List

import cv2
import numpy as np

from vision_lab.landmarks import LandmarkExtractor
from vision_lab.processing import LandmarkNormalizer
from vision_lab.training import BaselineTrainer

logger = logging.getLogger(__name__)


class TemporalBuffer:
    """Buffer frames for temporal consistency."""

    def __init__(self, window_size: int = 5, confidence_threshold: float = 0.5):
        """Initialize buffer.

        Args:
            window_size: Number of frames to buffer
            confidence_threshold: Min confidence for prediction
        """
        self.window_size = window_size
        self.confidence_threshold = confidence_threshold
        self.buffer = deque(maxlen=window_size)
        self.prediction_buffer = deque(maxlen=window_size)

    def add_prediction(self, prediction: str, confidence: float) -> Optional[str]:
        """Add prediction to buffer and get consensus.

        Args:
            prediction: Predicted class
            confidence: Confidence score

        Returns:
            Consensus prediction or None if no consensus
        """
        if confidence < self.confidence_threshold:
            return None

        self.prediction_buffer.append(prediction)

        # Majority voting
        if len(self.prediction_buffer) >= 3:
            predictions = list(self.prediction_buffer)
            unique, counts = np.unique(predictions, return_counts=True)
            max_idx = np.argmax(counts)

            if counts[max_idx] >= len(predictions) * 0.6:  # 60% threshold
                return unique[max_idx]

        return None

    def reset(self):
        """Reset buffer."""
        self.buffer.clear()
        self.prediction_buffer.clear()


class RealtimeRecognizer:
    """Real-time recognition from webcam."""

    def __init__(self, model: BaselineTrainer, fps_target: int = 30):
        """Initialize recognizer.

        Args:
            model: Trained model
            fps_target: Target FPS
        """
        self.model = model
        self.fps_target = fps_target
        self.fps_actual = fps_target
        self.frame_time = 1.0 / fps_target

        self.extractor = LandmarkExtractor()
        self.temporal_buffer = TemporalBuffer(window_size=5)

        # Timing
        self.last_frame_time = time.time()
        self.latency_buffer = deque(maxlen=30)

    def process_frame(self, frame: np.ndarray) -> Tuple[Optional[str], float, float]:
        """Process single frame and return prediction.

        Args:
            frame: Input frame from webcam

        Returns:
            (prediction, confidence, latency_ms)
        """
        start_time = time.time()

        try:
            # Extract landmarks
            from vision_lab.core import Frame

            frame_obj = Frame(
                frame_id=0,
                timestamp=time.time(),
                image=frame,
            )
            frame_obj = self.extractor.extract(frame_obj)

            if frame_obj.landmarks is None:
                return None, 0.0, 0.0

            # Normalize
            landmarks = LandmarkNormalizer.normalize_body_centered(frame_obj.landmarks)

            # Predict
            pred, probs = self.model.predict(landmarks.reshape(1, -1))
            confidence = np.max(probs)

            # Temporal consistency
            consensus = self.temporal_buffer.add_prediction(pred[0], confidence)

            # Latency
            latency_ms = (time.time() - start_time) * 1000
            self.latency_buffer.append(latency_ms)

            return consensus, float(confidence), latency_ms

        except Exception as e:
            logger.error(f"Frame processing failed: {e}")
            return None, 0.0, 0.0

    def run(self, camera_id: int = 0, display: bool = True) -> None:
        """Run real-time recognition.

        Args:
            camera_id: Camera device ID
            display: Whether to display frames
        """
        cap = cv2.VideoCapture(camera_id)

        if not cap.isOpened():
            logger.error(f"Failed to open camera {camera_id}")
            return

        logger.info(f"Camera opened. FPS target: {self.fps_target}")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Process frame
                prediction, confidence, latency = self.process_frame(frame)

                # Update FPS
                current_time = time.time()
                elapsed = current_time - self.last_frame_time
                if elapsed > 0:
                    self.fps_actual = 1.0 / elapsed
                self.last_frame_time = current_time

                # Display if requested
                if display:
                    self._draw_info(
                        frame,
                        prediction=prediction,
                        confidence=confidence,
                        fps=self.fps_actual,
                        latency=latency,
                    )
                    cv2.imshow("KONECTA V3 - Real-time Recognition", frame)

                # Exit on ESC
                if cv2.waitKey(1) & 0xFF == 27:
                    break

        finally:
            cap.release()
            cv2.destroyAllWindows()
            logger.info("Camera closed")

    @staticmethod
    def _draw_info(
        frame: np.ndarray,
        prediction: Optional[str] = None,
        confidence: float = 0.0,
        fps: float = 0.0,
        latency: float = 0.0,
    ) -> None:
        """Draw prediction info on frame.

        Args:
            frame: Frame to draw on
            prediction: Predicted class
            confidence: Confidence score
            fps: Current FPS
            latency: Latency in ms
        """
        h, w = frame.shape[:2]

        # Background for text
        cv2.rectangle(frame, (0, 0), (w, 120), (0, 0, 0), -1)
        cv2.rectangle(frame, (0, 0), (w, 120), (200, 200, 200), 2)

        # Prediction (large)
        if prediction:
            text = f"SINAL: {prediction}"
            color = (0, 255, 0) if confidence > 0.8 else (255, 165, 0)
            cv2.putText(
                frame,
                text,
                (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,
                color,
                3,
            )

            # Confidence bar
            conf_width = int(confidence * 300)
            cv2.rectangle(frame, (20, 65), (20 + conf_width, 85), color, -1)
            cv2.rectangle(frame, (20, 65), (320, 85), (200, 200, 200), 2)
            cv2.putText(
                frame,
                f"{confidence * 100:.1f}%",
                (330, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                1,
            )

        # FPS and latency
        info_text = f"FPS: {fps:.1f} | Latency: {latency:.1f}ms"
        cv2.putText(
            frame,
            info_text,
            (20, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1,
        )

    def get_average_latency(self) -> float:
        """Get average latency.

        Returns:
            Average latency in ms
        """
        if self.latency_buffer:
            return float(np.mean(self.latency_buffer))
        return 0.0

    def get_average_fps(self) -> float:
        """Get average FPS.

        Returns:
            Average FPS
        """
        return self.fps_actual
