"""Endpoints REST do KONECTA V2."""

from __future__ import annotations

import base64
import logging

import cv2
import numpy as np

from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

from backend.schemas import analise_para_dict
from backend.services import dataset_provider
from backend.services.analysis_service import service
from backend.services.capture_service import (
    capturar_webcam,
    extrair_landmarks,
    iniciar_sessao,
    obter_metadados,
    validar_sessao,
)
from backend.services.pipeline_service import (
    obter_analise_trajetoria,
    processar_sessao_completa,
)
from backend.services.recognition_service import service as recognition_service
from backend.services.training_service import TrainingService
from knowledge.ai_assistant import AIResearchAssistant, ProvedorAnthropic
from knowledge.reports import ReportGenerator

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "servico": "KONECTA V2 API", "versao": "0.1.0"}


@router.get("/fontes")
def fontes() -> dict:
    return {"fontes": dataset_provider.fontes_disponiveis()}


@router.get("/analise")
def obter_analise() -> dict:
    if service.analise is None:
        raise HTTPException(
            status_code=404,
            detail="Nenhuma analise executada ainda — use POST /api/analise ou o WebSocket /ws/analise",
        )
    return analise_para_dict(service.analise, fonte=service.fonte)


@router.post("/analise")
async def executar_analise(fonte: str = "sintetico", limite_sinais: int | None = None) -> dict:
    """Executa a analise de forma sincrona. Para progresso em tempo real,
    prefira o WebSocket `/ws/analise`."""
    if fonte not in dataset_provider.fontes_disponiveis():
        raise HTTPException(status_code=400, detail=f"Fonte desconhecida: {fonte}")
    analise = await run_in_threadpool(service.analisar, fonte, limite_sinais)
    return analise_para_dict(analise, fonte=fonte)


@router.get("/analise/relatorio", response_class=PlainTextResponse)
def relatorio() -> str:
    if service.analise is None:
        raise HTTPException(status_code=404, detail="Nenhuma analise executada ainda")
    return ReportGenerator().gerar_markdown(service.analise)


@router.post("/analise/interpretar")
async def interpretar_analise(tipo: str = "dataset") -> dict:
    """Interpreta a analise atual via AI Research Assistant (Claude).

    Tipos: 'dataset' (geral), 'coletas' (prioridades de coleta) ou 'treinamento' (próximos passos).
    """
    if service.analise is None:
        raise HTTPException(status_code=404, detail="Nenhuma analise executada ainda")
    if tipo not in ("dataset", "coletas", "treinamento"):
        raise HTTPException(status_code=400, detail=f"Tipo desconhecido: {tipo}")

    try:
        assistente = AIResearchAssistant(ProvedorAnthropic())
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI Research Assistant indisponível: {str(e)}. Verifique ANTHROPIC_API_KEY.",
        )

    resultado = await run_in_threadpool(
        _executar_interpretacao,
        assistente,
        service.analise,
        tipo,
    )
    return {"tipo": tipo, "resultado": resultado}


def _executar_interpretacao(assistente, analise, tipo: str) -> str:
    """Helper sincrono para executar a interpretacao (run_in_threadpool)."""
    if tipo == "dataset":
        return assistente.analisar_dataset(analise)
    elif tipo == "coletas":
        return assistente.recomendar_coletas(analise)
    else:  # treinamento
        return assistente.gerar_documentacao(analise)


# === Endpoints de Captura (Etapas 4-5) ===


@router.post("/captura/sessao")
async def criar_sessao_captura(
    id_sessao: str,
    sinal: str,
    sinalizante: str,
) -> dict:
    """Inicia uma nova sessão de captura de vídeo.

    Parâmetros:
    - id_sessao: identificador único da sessão
    - sinal: nome do sinal a ser capturado
    - sinalizante: identificação do articulador
    """
    return await run_in_threadpool(iniciar_sessao, id_sessao, sinal, sinalizante)


@router.get("/captura/sessao/{id_sessao}")
async def obter_sessao_captura(id_sessao: str) -> dict:
    """Obtém metadados de uma sessão de captura."""
    try:
        return await run_in_threadpool(obter_metadados, id_sessao)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/captura/sessao/{id_sessao}/webcam")
async def capturar_webcam_sessao(
    id_sessao: str,
    duracao_segundos: float = 5.0,
) -> dict:
    """Captura vídeo da webcam da máquina onde o backend está rodando e
    preenche a sessão (deve ter sido criada antes via POST /captura/sessao).

    Importante: esta é a webcam do HOST do backend, não a webcam do
    navegador de quem acessa o frontend — pensado para uso local/desktop.
    Chamada bloqueante (roda em threadpool) durante `duracao_segundos`.
    """
    try:
        return await run_in_threadpool(capturar_webcam, id_sessao, duracao_segundos)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/captura/sessao/{id_sessao}/validar")
async def validar_captura(id_sessao: str) -> dict:
    """Valida a qualidade de uma sessão de captura.

    Retorna:
    - valida: bool
    - pontuacao: float [0, 1]
    - problemas: list[str]
    - avisos: list[str]
    """
    try:
        return await run_in_threadpool(validar_sessao, id_sessao)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/captura/sessao/{id_sessao}/landmarks")
async def extrair_landmarks_sessao(
    id_sessao: str,
    incluir_maos: bool = True,
    incluir_corpo: bool = True,
) -> dict:
    """Extrai landmarks de uma sessão de captura.

    Usa MediaPipe para detectar:
    - Mãos: 21 pontos por mão (se incluir_maos=True)
    - Corpo: 33 pontos de pose (se incluir_corpo=True)

    Retorna lista de frames com landmarks normalizados [0, 1].
    """
    try:
        return await run_in_threadpool(
            extrair_landmarks,
            id_sessao,
            incluir_maos,
            incluir_corpo,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# === Pipeline End-to-End (Etapas 4-6 + Knowledge Engine) ===


@router.post("/pipeline/processar")
async def processar_pipeline_completo(
    id_sessao: str,
    sinal: str,
    sinalizante: str,
) -> dict:
    """Processa pipeline completo: captura → landmarks → tracking → análise.

    Etapas:
    1. Captura (Etapa 4): Recupera frames da sessão
    2. MediaPipe (Etapa 5): Extrai 21 pontos de mão
    3. Tracking (Etapa 6): Analisa trajetórias, dominância, localização
    4. Amostra: Converte em Core type (pronto para Knowledge Engine)

    Retorna:
    - Metadados da amostra
    - Análise de trajetória
    - Tensor de landmarks para ML
    """
    try:
        return await run_in_threadpool(
            processar_sessao_completa,
            id_sessao,
            sinal,
            sinalizante,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pipeline/sessao/{id_sessao}/trajetoria")
async def obter_trajetoria_analise(id_sessao: str) -> dict:
    """Recupera análise de trajetória de uma sessão processada.

    Retorna:
    - Dominância (direita/esquerda/ambas)
    - Local principal (alto/baixo/neutro)
    - Complexidade estimada
    - Velocidade e estabilidade de cada mão
    """
    try:
        analise = await run_in_threadpool(obter_analise_trajetoria, id_sessao)
        if not analise:
            raise ValueError(f"Análise de '{id_sessao}' não encontrada")
        return analise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# === Reconhecimento em Tempo Real ===


@router.post("/reconhecer")
async def reconhecer_sinal(landmarks: list = Body(...)) -> dict:
    """Reconhece um sinal Libras a partir dos landmarks.

    Parâmetros:
    - landmarks: Lista de frames com landmarks das mãos
                 Formato esperado: [[x, y, z, ...], ...]
                 Onde cada ponto tem 3 coordenadas (x, y, z)

    Retorna:
    - sinal: Nome do sinal reconhecido
    - confianca: Probabilidade [0, 1]
    - modelo: Qual modelo foi usado
    """
    try:
        resultado = await run_in_threadpool(recognition_service.reconhecer, landmarks)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao reconhecer: {str(e)}")


@router.post("/processar-frames-opencv")
async def processar_frames_opencv(payload: dict = Body(...)) -> dict:
    """Processa frames e extrai features simples com OpenCV (sem MediaPipe)."""
    try:
        sinal = payload.get("sinal", "")
        frames_list = payload.get("frames", [])

        if not frames_list or len(frames_list) == 0:
            return {"sucesso": False, "landmarks": [], "erro": "Sem frames"}

        landmarks_result = []

        for frame_data in frames_list:
            try:
                if isinstance(frame_data, list):
                    frame_array = np.array(frame_data, dtype=np.uint8)
                    if frame_array.size > 0:
                        # Normalizar para formato de imagem (640x480x3)
                        frame_array = frame_array.reshape(480, 640, 3) if frame_array.size == 921600 else frame_array

                        # Extrair histograma como features (126 features)
                        hist = cv2.calcHist([frame_array], [0, 1, 2], None, [7, 7, 3], [0, 256, 0, 256, 0, 256])
                        hist = cv2.normalize(hist, hist).flatten()[:126]

                        # Pad com zeros se necessário
                        if len(hist) < 126:
                            hist = np.pad(hist, (0, 126 - len(hist)))

                        landmarks_result.append(hist.tolist())
            except Exception as e:
                logger.warning("Falha ao processar frame em /processar-frames-opencv: %s", e)

        return {
            "sucesso": len(landmarks_result) > 0,
            "landmarks": landmarks_result,
            "frames_processados": len(landmarks_result)
        }

    except Exception as e:
        return {"sucesso": False, "landmarks": [], "erro": str(e)}


@router.post("/treinar")
async def treinar_modelo(dados: dict = Body(...)) -> dict:
    """Treina novo modelo com dados capturados pelo usuário.

    Parâmetros:
    - dados: Dict com formato {'A': [[frame1], [frame2], ...], 'B': [...], ...}

    Retorna:
    - sucesso: True/False
    - mensagem: Descrição do resultado
    - sinais: Quantidade de sinais treinados
    - amostras_por_sinal: Contagem de amostras por sinal
    """
    try:
        resultado = await run_in_threadpool(TrainingService.treinar_modelo, dados)
        if resultado["sucesso"]:
            # Recarregar modelos no recognition_service
            recognition_service._load_models()
        return resultado
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao treinar: {str(e)}")


