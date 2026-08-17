"""Pipeline Orquestrador - Coordena todos os motores.

Prioridade: latência baixa + máxima acurácia.
"""

import asyncio
import base64
import logging
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app_central.motors.motor_claude_logic import MotorClaudeLogic, ValidationResult
from app_central.motors.motor_konecta_v3 import MotorKonectaV3, RecognitionResult

logger = logging.getLogger(__name__)

# Timeouts por fase do pipeline (em segundos)
KONECTA_TIMEOUT = 1.0
GEMINI_TIMEOUT = 1.5
CLAUDE_TIMEOUT = 0.8
GROK_TIMEOUT = 1.2

# Limiares de confiança
HIGH_CONFIDENCE_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.7

# Valores padrão quando o Gemini Vision não está disponível
DEFAULT_IMAGE_QUALITY: Dict[str, Any] = {
    "quality_score": 50,
    "hands_visible": False,
    "lighting_ok": False,
}


class ConfidenceLevel(Enum):
    """Níveis de confiança do reconhecimento."""

    HIGH = "high"  # > 0.85
    MEDIUM = "medium"  # 0.7 - 0.85
    LOW = "low"  # < 0.7


@dataclass
class PipelineResult:
    """Resultado final do pipeline."""

    signal: str
    confidence: float
    latency_ms: float
    confidence_level: str
    validated_by: str  # konecta_v3|ensemble|claude_logic|grok_context
    recommendation: str
    user_history: List[str]
    status: str = "success"
    error: Optional[str] = None
    detailed_results: Optional[Dict] = None


class RecognizerPipeline:
    """Orquestra todos os motores em paralelo.

    Fluxo:
    1. KONECTA V3 + Gemini Vision (paralelo)
    2. Validação cruzada por confiança
    3. Claude Logic se necessário (0.7-0.85)
    4. Grok Context se necessário (< 0.7)
    5. Cache + N8N assincronamente
    """

    def __init__(self, config: Dict):
        self.config = config
        self.konecta = MotorKonectaV3(
            model_path=config.get("konecta_model_path", "models/v1")
        )
        self.claude = MotorClaudeLogic(
            api_key=config.get("claude_api_key"),
            model=config.get("claude_model", "claude-3-5-sonnet-20241022"),
        )
        # Gemini e Grok ficam opcionais: ativados quando implementados/disponíveis
        self.gemini: Any = None
        self.grok: Any = None
        self.cache_manager: Any = None
        self.n8n_client: Any = None

        self.performance_stats: Dict[str, Any] = {
            "total_processed": 0,
            "avg_latency_ms": 0,
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0,
            "errors": 0,
        }

    async def process_frame(self, frame: np.ndarray, user_id: str = "default") -> PipelineResult:
        """Processa um frame através do pipeline completo.

        Latência esperada:
        - Caso HIGH confidence: ~300ms (KONECTA V3 + validação)
        - Caso MEDIUM confidence: ~700ms (+ Claude Logic)
        - Caso LOW confidence: ~1200ms (+ Grok Context)
        """
        start_time = time.time()
        detailed_results: Dict[str, Any] = {}

        try:
            konecta_result, gemini_result = await self._recognize_parallel(frame)
            self._collect_primary_results(detailed_results, konecta_result, gemini_result)

            confidence_level = self._get_confidence_level(konecta_result.confidence)

            if confidence_level == ConfidenceLevel.HIGH:
                final_result = self._accept_high_confidence(
                    konecta_result, detailed_results, start_time
                )
            elif confidence_level == ConfidenceLevel.MEDIUM:
                final_result = await self._validate_with_claude(
                    konecta_result, gemini_result, user_id, detailed_results, start_time
                )
            else:
                final_result = await self._enrich_with_grok(
                    konecta_result, user_id, detailed_results, start_time
                )

            self._schedule_side_effects(final_result, user_id)
            self._update_stats(final_result)

            logger.info(
                "Pipeline finalizado: %s em %.0fms",
                final_result.signal,
                final_result.latency_ms,
            )
            return final_result

        except asyncio.TimeoutError:
            logger.error("Timeout no pipeline")
            return self._result_error(start_time, "Pipeline timeout")

        except Exception as error:
            logger.error("Erro no pipeline: %s", error)
            return self._result_error(start_time, str(error))

    # ─────────────────────────────────────────────────────────
    # FASE 1: Reconhecimento paralelo
    # ─────────────────────────────────────────────────────────

    async def _recognize_parallel(self, frame: np.ndarray) -> Tuple[RecognitionResult, Optional[Any]]:
        """Executa KONECTA V3 (sempre) e Gemini Vision (se disponível) em paralelo."""
        konecta_task = asyncio.create_task(self.konecta.process(frame))
        gemini_task = None
        if self.gemini:
            gemini_task = asyncio.create_task(self.gemini.validate(self._frame_to_base64(frame)))

        if gemini_task:
            return await asyncio.wait_for(
                asyncio.gather(konecta_task, gemini_task), timeout=GEMINI_TIMEOUT
            )
        konecta_result = await asyncio.wait_for(konecta_task, timeout=KONECTA_TIMEOUT)
        return konecta_result, None

    @staticmethod
    def _collect_primary_results(
        detailed_results: Dict[str, Any],
        konecta_result: RecognitionResult,
        gemini_result: Optional[Any],
    ) -> None:
        """Registra os resultados primários no dicionário de detalhes."""
        detailed_results["konecta_v3"] = asdict(konecta_result)
        if gemini_result is not None:
            detailed_results["gemini_vision"] = gemini_result
        logger.info(
            "KONECTA V3: %s (%.1f%%)",
            konecta_result.signal,
            konecta_result.confidence * 100,
        )

    # ─────────────────────────────────────────────────────────
    # FASE 2: Validação cruzada por confiança
    # ─────────────────────────────────────────────────────────

    def _accept_high_confidence(
        self,
        konecta_result: RecognitionResult,
        detailed_results: Dict[str, Any],
        start_time: float,
    ) -> PipelineResult:
        """Caso HIGH confidence: aceita o resultado sem validação adicional."""
        self.performance_stats["high_confidence"] += 1
        return PipelineResult(
            signal=konecta_result.signal,
            confidence=konecta_result.confidence,
            latency_ms=(time.time() - start_time) * 1000,
            confidence_level=ConfidenceLevel.HIGH.value,
            validated_by="ensemble",  # KONECTA V3 + Gemini
            recommendation="accept",
            user_history=[konecta_result.signal],
            detailed_results=detailed_results,
        )

    async def _validate_with_claude(
        self,
        konecta_result: RecognitionResult,
        gemini_result: Optional[Any],
        user_id: str,
        detailed_results: Dict[str, Any],
        start_time: float,
    ) -> PipelineResult:
        """Caso MEDIUM confidence: valida o resultado com Claude Logic."""
        user_history = await self._get_user_history(user_id)
        image_quality = self._extract_quality_from_gemini(gemini_result)

        claude_result: ValidationResult = await asyncio.wait_for(
            self.claude.validate_with_context(
                signal=konecta_result.signal,
                confidence=konecta_result.confidence,
                user_history=user_history,
                image_quality=image_quality,
            ),
            timeout=CLAUDE_TIMEOUT,
        )
        detailed_results["claude_logic"] = asdict(claude_result)
        logger.info(
            "Claude ajustou confiança: %.1f%% → %.1f%%",
            konecta_result.confidence * 100,
            claude_result.confidence_adjusted * 100,
        )

        self.performance_stats["medium_confidence"] += 1
        return PipelineResult(
            signal=konecta_result.signal,
            confidence=claude_result.confidence_adjusted,
            latency_ms=(time.time() - start_time) * 1000,
            confidence_level=ConfidenceLevel.MEDIUM.value,
            validated_by="claude_logic",
            recommendation=claude_result.recommendation,
            user_history=user_history,
            detailed_results=detailed_results,
        )

    async def _enrich_with_grok(
        self,
        konecta_result: RecognitionResult,
        user_id: str,
        detailed_results: Dict[str, Any],
        start_time: float,
    ) -> PipelineResult:
        """Caso LOW confidence: enriquece a predição com Grok Context."""
        user_history = await self._get_user_history(user_id)
        final_signal = konecta_result.signal
        validated_by = "grok_context"

        if self.grok:
            grok_result = await asyncio.wait_for(
                self.grok.enrich_with_context(
                    signal=konecta_result.signal,
                    confidence=konecta_result.confidence,
                    user_id=user_id,
                ),
                timeout=GROK_TIMEOUT,
            )
            detailed_results["grok_context"] = grok_result
            final_signal = grok_result.get("most_likely_signal", konecta_result.signal)

        self.performance_stats["low_confidence"] += 1
        return PipelineResult(
            signal=final_signal,
            confidence=konecta_result.confidence,
            latency_ms=(time.time() - start_time) * 1000,
            confidence_level=ConfidenceLevel.LOW.value,
            validated_by=validated_by,
            recommendation="accept",  # Fallback
            user_history=user_history,
            detailed_results=detailed_results,
        )

    # ─────────────────────────────────────────────────────────
    # FASE 3: Efeitos colaterais (cache + N8N) assíncronos
    # ─────────────────────────────────────────────────────────

    def _schedule_side_effects(self, result: PipelineResult, user_id: str) -> None:
        """Dispara atualização de cache/N8N em background sem bloquear o resultado."""
        asyncio.create_task(self._update_cache_and_notify(result, user_id))

    def _update_stats(self, result: PipelineResult) -> None:
        """Atualiza estatísticas acumuladas do pipeline."""
        self.performance_stats["total_processed"] += 1
        total = self.performance_stats["total_processed"]
        previous_avg = self.performance_stats["avg_latency_ms"]
        self.performance_stats["avg_latency_ms"] = (
            previous_avg * (total - 1) + result.latency_ms
        ) / total

    # ─────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _get_confidence_level(confidence: float) -> ConfidenceLevel:
        """Classifica o nível de confiança de uma predição."""
        if confidence > HIGH_CONFIDENCE_THRESHOLD:
            return ConfidenceLevel.HIGH
        if confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    async def _get_user_history(self, user_id: str) -> List[str]:
        """Obtém histórico do usuário (do cache), quando disponível."""
        if self.cache_manager:
            return await self.cache_manager.get_history(user_id)
        return []

    @classmethod
    def _extract_quality_from_gemini(cls, gemini_result: Optional[Any]) -> Dict[str, Any]:
        """Extrai a qualidade da imagem reportada pelo Gemini Vision."""
        if gemini_result is None:
            return dict(DEFAULT_IMAGE_QUALITY)
        return {
            "quality_score": gemini_result.get("quality_score", DEFAULT_IMAGE_QUALITY["quality_score"]),
            "hands_visible": gemini_result.get("hands_visible", DEFAULT_IMAGE_QUALITY["hands_visible"]),
            "lighting_ok": gemini_result.get("lighting_ok", DEFAULT_IMAGE_QUALITY["lighting_ok"]),
        }

    @staticmethod
    def _frame_to_base64(frame: np.ndarray) -> str:
        """Converte um frame BGR em uma string base64 (JPEG)."""
        _, buffer = cv2.imencode(".jpg", frame)
        return base64.b64encode(buffer.tobytes()).decode()

    async def _update_cache_and_notify(self, result: PipelineResult, user_id: str) -> None:
        """Atualiza cache e notifica N8N (assincronamente)."""
        try:
            if self.cache_manager:
                await self.cache_manager.save_result(user_id, result)
            if self.n8n_client:
                await self.n8n_client.notify_signal(result, user_id)
        except Exception as error:
            logger.warning("Erro ao atualizar cache/N8N: %s", error)

    def _result_error(self, start_time: float, error: str) -> PipelineResult:
        """Constrói PipelineResult de erro e registra nas estatísticas."""
        self.performance_stats["errors"] += 1
        return PipelineResult(
            signal="ERROR",
            confidence=0.0,
            latency_ms=(time.time() - start_time) * 1000,
            confidence_level="low",
            validated_by="none",
            recommendation="retry",
            user_history=[],
            status="error",
            error=error,
        )

    def get_stats(self) -> Dict:
        """Retorna estatísticas do pipeline."""
        total = self.performance_stats["total_processed"]
        if total > 0:
            return {
                **self.performance_stats,
                "success_rate": (total - self.performance_stats["errors"]) / total,
                "distribution": {
                    "high_confidence": self.performance_stats["high_confidence"] / total,
                    "medium_confidence": self.performance_stats["medium_confidence"] / total,
                    "low_confidence": self.performance_stats["low_confidence"] / total,
                },
            }
        return self.performance_stats


# Teste
if __name__ == "__main__":
    import os

    async def _test() -> None:
        config = {
            "konecta_model_path": "models/v1",
            "claude_api_key": os.getenv("ANTHROPIC_API_KEY"),
            "claude_model": "claude-3-5-sonnet-20241022",
        }
        pipeline = RecognizerPipeline(config)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = await pipeline.process_frame(frame)
        print(f"Resultado: {result}")
        print(f"Stats: {pipeline.get_stats()}")

    asyncio.run(_test())
