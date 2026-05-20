"""
Serviço de reconhecimento de sinais via câmera usando MediaPipe.
Detecta landmarks da mão e classifica o gesto como letra do alfabeto.
"""
import cv2
import numpy as np
import mediapipe as mp
import base64
from app.models.schemas import HandGestureResult
from app.config import HAND_DETECTION_CONFIDENCE, HAND_TRACKING_CONFIDENCE


class HandRecognizer:
    """Reconhecedor de gestos de Libras usando MediaPipe Hands"""
    
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,       # Modo vídeo (mais rápido)
            max_num_hands=2,
            min_detection_confidence=HAND_DETECTION_CONFIDENCE,
            min_tracking_confidence=HAND_TRACKING_CONFIDENCE,
        )
        self.mp_draw = mp.solutions.drawing_utils
    
    def _decode_frame(self, base64_frame: str) -> np.ndarray:
        """Decodifica frame base64 (vindo do frontend) para OpenCV"""
        img_bytes = base64.b64decode(base64_frame)
        np_arr = np.frombuffer(img_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return frame
    
    def _extract_landmarks(self, frame: np.ndarray) -> list | None:
        """Extrai landmarks da mão no frame"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        if results.multi_hand_landmarks:
            # Pega a primeira mão detectada
            hand = results.multi_hand_landmarks[0]
            landmarks = []
            for lm in hand.landmark:
                landmarks.append({
                    "x": round(lm.x, 4),
                    "y": round(lm.y, 4),
                    "z": round(lm.z, 4)
                })
            return landmarks
        return None
    
    def _classify_gesture(self, landmarks: list) -> tuple[str, float]:
        """
        Classifica os landmarks da mão em uma letra de Libras.
        
        Cada dedo tem 4 pontos (tip, dip, pip, mcp).
        Analisamos quais dedos estão levantados ou dobrados.
        
        Índices MediaPipe:
        - Polegar:   4 (tip), 3 (ip), 2 (mcp), 1 (cmc)
        - Indicador: 8 (tip), 7 (dip), 6 (pip), 5 (mcp)
        - Médio:    12 (tip), 11 (dip), 10 (pip), 9 (mcp)
        - Anelar:   16 (tip), 15 (dip), 14 (pip), 13 (mcp)
        - Mínimo:   20 (tip), 19 (dip), 18 (pip), 17 (mcp)
        """
        
        # Detecta quais dedos estão levantados
        fingers_up = self._get_fingers_up(landmarks)
        thumb, index, middle, ring, pinky = fingers_up
        
        # ===== CLASSIFICAÇÃO BÁSICA POR COMBINAÇÃO DE DEDOS =====
        # (Versão simplificada — para TCC, pode expandir com ML depois)
        
        # A: Mão fechada, polegar ao lado
        if not index and not middle and not ring and not pinky and thumb:
            return ("A", 0.8)
        
        # B: Todos os dedos levantados, polegar dobrado
        if index and middle and ring and pinky and not thumb:
            return ("B", 0.8)
        
        # C: Mão em formato de C (todos semi-dobrados)
        # Simplificação: nenhum dedo totalmente aberto nem fechado
        
        # D: Só indicador levantado
        if index and not middle and not ring and not pinky:
            return ("D", 0.7)
        
        # I: Só mínimo levantado
        if not index and not middle and not ring and pinky and not thumb:
            return ("I", 0.8)
        
        # L: Polegar e indicador em L
        if thumb and index and not middle and not ring and not pinky:
            return ("L", 0.85)
        
        # V: Indicador e médio abertos
        if index and middle and not ring and not pinky:
            return ("V", 0.8)
        
        # W: Indicador, médio e anelar abertos
        if index and middle and ring and not pinky:
            return ("W", 0.75)
        
        # Y: Polegar e mínimo abertos (hang loose)
        if thumb and not index and not middle and not ring and pinky:
            return ("Y", 0.85)
        
        # S: Mão totalmente fechada
        if not thumb and not index and not middle and not ring and not pinky:
            return ("S", 0.7)
        
        # 5 / Aberta: Todos os dedos abertos
        if thumb and index and middle and ring and pinky:
            return ("5", 0.8)
        
        return ("?", 0.0)
    
    def _get_fingers_up(self, landmarks: list) -> list[bool]:
        """Retorna lista de booleans indicando quais dedos estão levantados"""
        fingers = []
        
        # Polegar: compara x (porque é lateral)
        # Se a ponta (4) está mais à esquerda que a junta (3) = levantado (mão direita)
        thumb_up = landmarks[4]["x"] < landmarks[3]["x"]
        fingers.append(thumb_up)
        
        # Outros dedos: compara y (ponta acima da junta pip = levantado)
        tip_ids = [8, 12, 16, 20]
        pip_ids = [6, 10, 14, 18]
        
        for tip, pip in zip(tip_ids, pip_ids):
            fingers.append(landmarks[tip]["y"] < landmarks[pip]["y"])
        
        return fingers
    
    def process_frame(self, base64_frame: str) -> HandGestureResult:
        """Processa um frame e retorna o gesto detectado"""
        try:
            frame = self._decode_frame(base64_frame)
            landmarks = self._extract_landmarks(frame)
            
            if landmarks is None:
                return HandGestureResult(
                    detected=False,
                    letter=None,
                    confidence=0.0
                )
            
            letter, confidence = self._classify_gesture(landmarks)
            
            return HandGestureResult(
                detected=True,
                letter=letter,
                confidence=confidence,
                landmarks=landmarks
            )
        except Exception as e:
            print(f"Erro ao processar frame: {e}")
            return HandGestureResult(detected=False, confidence=0.0)
    
    def release(self):
        """Libera recursos do MediaPipe"""
        self.hands.close()


# Singleton global
hand_recognizer = HandRecognizer()