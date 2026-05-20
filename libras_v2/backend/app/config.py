from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SIGNS_DIR = STATIC_DIR / "signs"

# Confiança mínima para detecção de mãos (0.0 a 1.0)
HAND_DETECTION_CONFIDENCE = 0.7
HAND_TRACKING_CONFIDENCE = 0.5

# WebSocket
WS_HEARTBEAT_INTERVAL = 30  # segundos
