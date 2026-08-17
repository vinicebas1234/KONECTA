"""Motor Claude Logic - Validação contextual.

Responsável: decisões com contexto (fallback quando 0.7 <= confidence <= 0.85).
Latência alvo: < 500ms.
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import anthropic

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Resultado da validação contextual."""

    is_valid: bool
    confidence_adjusted: float
    reasoning: str
    recommendation: str  # accept|retry|request_clarification
    latency_ms: float
    status: str = "success"
    error: Optional[str] = None


class MotorClaudeLogic:
    """Validação contextual usando Claude.

    Usado quando:
    - Confidence do KONECTA V3 entre 0.7-0.85
    - Precisa validar se faz sentido com histórico

    Estratégia:
    1. Análise do resultado
    2. Contextualização com histórico do usuário
    3. Validação semântica
    4. Recomendação de ação
    """

    def __init__(self, api_key: Optional[str], model: str = "claude-3-5-sonnet-20241022"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.performance_stats: Dict[str, Any] = {
            "total_calls": 0,
            "total_time_ms": 0.0,
            "api_errors": 0,
        }

    async def validate_with_context(
        self,
        signal: str,
        confidence: float,
        user_history: List[str],
        image_quality: Dict,
    ) -> ValidationResult:
        """Valida resultado com contexto do usuário.

        Args:
            signal: Sinal identificado pelo KONECTA V3
            confidence: Confiança (0.7-0.85)
            user_history: Últimos sinais feitos pelo usuário
            image_quality: Qualidade da imagem (da Gemini Vision)

        Returns:
            ValidationResult com decisão e confiança ajustada
        """
        start_time = time.time()

        try:
            pattern_analysis = self._analyze_pattern(signal, user_history)
            response = self._call_claude(signal, confidence, user_history, image_quality, pattern_analysis)
            content = response.content[0].text
            validation = self._parse_response(content)
            return self._success_result(validation, confidence, start_time)

        except anthropic.APIError as error:
            logger.error("Erro API Claude: %s", error)
            self.performance_stats["api_errors"] += 1
            return ValidationResult(
                is_valid=False,
                confidence_adjusted=confidence,
                reasoning="Erro ao validar com Claude",
                recommendation="retry",
                latency_ms=(time.time() - start_time) * 1000,
                status="error",
                error=str(error),
            )

        except Exception as error:
            logger.error("Erro inesperado: %s", error)
            return ValidationResult(
                is_valid=False,
                confidence_adjusted=confidence,
                reasoning="Erro ao processar validação",
                recommendation="accept",  # Fallback: aceita resultado
                latency_ms=(time.time() - start_time) * 1000,
                status="error",
                error=str(error),
            )

    def _call_claude(
        self,
        signal: str,
        confidence: float,
        user_history: List[str],
        image_quality: Dict,
        pattern_analysis: Dict,
    ) -> Any:
        """Monta o prompt e chama a API do Claude."""
        prompt = self._build_validation_prompt(
            signal=signal,
            confidence=confidence,
            user_history=user_history,
            image_quality=image_quality,
            pattern_analysis=pattern_analysis,
        )
        return self.client.messages.create(
            model=self.model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )

    def _success_result(self, validation: Dict, confidence: float, start_time: float) -> ValidationResult:
        """Constrói resultado de sucesso e registra estatísticas."""
        latency = (time.time() - start_time) * 1000
        self.performance_stats["total_calls"] += 1
        self.performance_stats["total_time_ms"] += latency
        return ValidationResult(
            is_valid=validation.get("is_valid", False),
            confidence_adjusted=validation.get("confidence_adjusted", confidence),
            reasoning=validation.get("reasoning", ""),
            recommendation=validation.get("recommendation", "accept"),
            latency_ms=latency,
            status="success",
        )

    def _build_validation_prompt(
        self,
        signal: str,
        confidence: float,
        user_history: List[str],
        image_quality: Dict,
        pattern_analysis: Dict,
    ) -> str:
        """Monta prompt para Claude."""
        history_text = ", ".join(user_history[-10:]) if user_history else "nenhum histórico"
        pattern_text = pattern_analysis.get("pattern", "")
        frequency = pattern_analysis.get("frequency", {}).get(signal, 0)

        return f"""
Você é um validador especializado em reconhecimento de Libras.

═══════════════════════════════════════════════════════════
RESULTADO DO MODELO DE RECONHECIMENTO:
═══════════════════════════════════════════════════════════
• Sinal Identificado: {signal}
• Confiança Inicial: {confidence:.1%}
• Qualidade da Imagem: {image_quality.get('quality_score', 'N/A')}/100
• Mãos Visíveis: {image_quality.get('hands_visible', 'N/A')}
• Iluminação Adequada: {image_quality.get('lighting_ok', 'N/A')}

═══════════════════════════════════════════════════════════
CONTEXTO DO USUÁRIO:
═══════════════════════════════════════════════════════════
• Últimos 10 sinais: {history_text}
• Padrão: {pattern_text}
• Frequência de '{signal}' no histórico: {frequency} vezes

═══════════════════════════════════════════════════════════
TAREFA:
═══════════════════════════════════════════════════════════
1. O resultado faz sentido contextualmente?
   - Usuário faz este sinal frequentemente?
   - Faz sentido após os sinais anteriores?

2. Qualidade da detecção?
   - Imagem com qualidade suficiente?
   - Hands visibility adequada?

3. Confiança Final?
   - Qual sua confiança ajustada? (0-100%)
   - Diferente da inicial?

4. Recomendação?
   - "accept": Aceita o resultado
   - "retry": Pede ao usuário para repetir
   - "request_clarification": Pergunta se foi este sinal

═══════════════════════════════════════════════════════════
RESPONDA EM JSON (sem markdown):
═══════════════════════════════════════════════════════════
{{
    "is_valid": bool,
    "confidence_adjusted": float (0.0 a 1.0),
    "reasoning": "explicação breve (1-2 linhas)",
    "recommendation": "accept|retry|request_clarification"
}}
"""

    def _parse_response(self, response_text: str) -> Dict:
        """Parse resposta JSON do Claude (direto ou extraído de texto)."""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        try:
            return self._extract_json(response_text)
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback
        logger.warning("Não conseguiu fazer parse: %s", response_text[:100])
        return {
            "is_valid": False,
            "confidence_adjusted": 0.5,
            "reasoning": "Erro ao processar resposta",
            "recommendation": "accept",
        }

    @staticmethod
    def _extract_json(response_text: str) -> Dict:
        """Extrai e decodifica o primeiro objeto JSON completo do texto."""
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if not 0 <= start < end:
            raise ValueError("JSON não encontrado no texto")
        json_str = response_text[start:end]
        return json.loads(json_str)

    def _analyze_pattern(self, _signal: str, history: List[str]) -> Dict[str, Any]:
        """Analisa padrão de sinais do usuário."""
        if not history:
            return {"pattern": "sem histórico", "frequency": {}}

        frequency: Dict[str, int] = {}
        for item in history:
            frequency[item] = frequency.get(item, 0) + 1

        if len(history) >= 3:
            pattern = f"sequência recente: {' → '.join(history[-3:])}"
        else:
            pattern = f"sinais: {', '.join(history)}"

        return {
            "pattern": pattern,
            "frequency": frequency,
            "total_history": len(history),
        }

    def get_stats(self) -> Dict:
        """Retorna estatísticas."""
        stats = self.performance_stats.copy()
        if stats["total_calls"] > 0:
            stats["avg_latency_ms"] = stats["total_time_ms"] / stats["total_calls"]
            stats["error_rate"] = stats["api_errors"] / stats["total_calls"]
        return stats


# Teste
if __name__ == "__main__":
    import asyncio
    import os

    async def _test() -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("❌ ANTHROPIC_API_KEY não configurada")
            return

        motor = MotorClaudeLogic(api_key)
        result = await motor.validate_with_context(
            signal="OLHO",
            confidence=0.78,
            user_history=["BOCA", "OLHO", "MÃO", "OLHO"],
            image_quality={
                "quality_score": 85,
                "hands_visible": True,
                "lighting_ok": True,
            },
        )
        print(f"Validação: {result}")
        print(f"Stats: {motor.get_stats()}")

    asyncio.run(_test())
