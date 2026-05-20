from pydantic import BaseModel
from typing import Optional
from enum import Enum


class TokenType(str, Enum):
    WORD = "word"           # Sinal próprio encontrado
    FINGERSPELL = "fingerspell"  # Soletrado letra por letra


class LibrasSign(BaseModel):
    """Representa um sinal de letra (datilologia)"""
    id: str
    letter: str
    hint: str
    image_url: str


class LibrasWord(BaseModel):
    """Representa um sinal de palavra/expressão"""
    id: str
    word: str
    category: str
    hint: str
    image_url: str
    video_url: Optional[str] = None


class TranslatedToken(BaseModel):
    """Um token traduzido (pode ser sinal próprio ou soletrado)"""
    original: str
    type: TokenType
    signs: list[dict]  # Lista de sinais (letra ou palavra)


class TranslationRequest(BaseModel):
    text: str


class TranslationResponse(BaseModel):
    original_text: str
    tokens: list[TranslatedToken]


class AddWordRequest(BaseModel):
    word: str
    category: str
    hint: str
    image_url: str
    video_url: Optional[str] = None


class HandGestureResult(BaseModel):
    """Resultado do reconhecimento de gesto"""
    detected: bool
    letter: Optional[str] = None
    confidence: float = 0.0
    landmarks: Optional[list] = None


# WebSocket message types
class WSMessageType(str, Enum):
    # Cliente → Servidor
    TRANSLATE_TEXT = "translate_text"
    CAMERA_FRAME = "camera_frame"
    
    # Servidor → Cliente
    TRANSLATION_RESULT = "translation_result"
    GESTURE_RESULT = "gesture_result"
    ERROR = "error"