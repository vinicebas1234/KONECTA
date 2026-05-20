"""
Servidor FastAPI principal com:
- API REST para tradução e dicionário
- WebSocket para comunicação em tempo real (câmera + transcrição)
"""
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR
from app.models.schemas import (
    TranslationRequest, TranslationResponse,
    AddWordRequest, WSMessageType
)
from app.services.translator import translate_phrase
from app.services.dictionary import (
    get_all_words, get_words_by_category,
    get_categories, add_word, search_words
)
from app.services.hand_recognizer import hand_recognizer


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialização e encerramento do app"""
    print("🤟 Servidor Libras iniciado!")
    yield
    hand_recognizer.release()
    print("👋 Servidor Libras encerrado.")


app = FastAPI(
    title="Libras TCC API",
    description="API de tradução Texto ↔ Libras com reconhecimento de gestos",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS para o frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos (imagens dos sinais)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ========================================
# 🔤 ENDPOINTS REST — Tradução
# ========================================

@app.post("/api/translate", response_model=TranslationResponse)
async def translate_text(request: TranslationRequest):
    """Traduz texto em português para sinais de Libras"""
    tokens = translate_phrase(request.text)
    return TranslationResponse(
        original_text=request.text,
        tokens=tokens
    )


@app.get("/api/translate/{phrase}")
async def translate_get(phrase: str):
    """Traduz via GET (mais simples para testes)"""
    tokens = translate_phrase(phrase)
    return {"original_text": phrase, "tokens": [t.model_dump() for t in tokens]}


# ========================================
# 📚 ENDPOINTS REST — Dicionário
# ========================================

@app.get("/api/dictionary")
async def list_words():
    """Lista todas as palavras do dicionário"""
    return get_all_words()


@app.get("/api/dictionary/categories")
async def list_categories():
    """Lista todas as categorias disponíveis"""
    return get_categories()


@app.get("/api/dictionary/category/{category}")
async def words_by_category(category: str):
    """Lista palavras de uma categoria"""
    return get_words_by_category(category)


@app.get("/api/dictionary/search/{query}")
async def search(query: str):
    """Busca palavras no dicionário"""
    return search_words(query)


@app.post("/api/dictionary")
async def create_word(request: AddWordRequest):
    """Adiciona nova palavra/expressão ao dicionário"""
    new_word = add_word(request)
    return {"message": f"Palavra '{new_word.word}' adicionada!", "word": new_word}


# ========================================
# 🔌 WEBSOCKET — Comunicação em tempo real
# ========================================

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    WebSocket para comunicação bidirecional em tempo real:
    
    Cliente → Servidor:
      - translate_text: recebe texto transcrito → retorna sinais
      - camera_frame: recebe frame base64 → retorna gesto detectado
    
    Servidor → Cliente:
      - translation_result: sinais traduzidos
      - gesture_result: letra/gesto reconhecido
    """
    await ws.accept()
    print("🔌 Cliente WebSocket conectado")
    
    try:
        while True:
            # Recebe mensagem do cliente
            raw = await ws.receive_text()
            message = json.loads(raw)
            msg_type = message.get("type")
            payload = message.get("data", {})
            
            # --- Texto → Libras ---
            if msg_type == WSMessageType.TRANSLATE_TEXT:
                text = payload.get("text", "")
                if text:
                    tokens = translate_phrase(text)
                    await ws.send_json({
                        "type": WSMessageType.TRANSLATION_RESULT,
                        "data": {
                            "original": text,
                            "tokens": [t.model_dump() for t in tokens]
                        }
                    })
            
            # --- Frame de câmera → Reconhecimento de gesto ---
            elif msg_type == WSMessageType.CAMERA_FRAME:
                frame_b64 = payload.get("frame", "")
                if frame_b64:
                    # Processa em thread separada para não bloquear
                    result = await asyncio.to_thread(
                        hand_recognizer.process_frame, frame_b64
                    )
                    await ws.send_json({
                        "type": WSMessageType.GESTURE_RESULT,
                        "data": result.model_dump()
                    })
            
            else:
                await ws.send_json({
                    "type": WSMessageType.ERROR,
                    "data": {"message": f"Tipo desconhecido: {msg_type}"}
                })
    
    except WebSocketDisconnect:
        print("🔌 Cliente WebSocket desconectado")
    except Exception as e:
        print(f"❌ Erro WebSocket: {e}")
        await ws.close()