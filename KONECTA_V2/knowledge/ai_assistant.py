"""AI Research Assistant — LLMs como especialistas em analise dos dados.

Importante: a IA generativa NAO reconhece Libras. O reconhecimento e feito
pelos modelos treinados no proprio KONECTA. Aqui os LLMs apenas interpretam
as analises do Knowledge Engine, resultados de treinamento e recomendacoes,
apoiando o pesquisador.

Fluxo: Dataset -> Knowledge Engine -> LLM -> Relatorios -> Pesquisador
"""

from __future__ import annotations

from typing import Protocol

from core.types import AnaliseDataset
from knowledge.reports import ReportGenerator

SISTEMA_PESQUISA = (
    "Voce e um especialista em reconhecimento de linguas de sinais, visao "
    "computacional (MediaPipe) e aprendizado de maquina. Analisa datasets de "
    "Libras compostos por landmarks de maos, avalia resultados de treinamento "
    "e recomenda melhorias. Responda em portugues, de forma objetiva e "
    "tecnica, sempre priorizando recomendacoes acionaveis para o pesquisador."
)


class ProvedorLLM(Protocol):
    """Contrato minimo de um provedor de LLM (Claude, GPT, Gemini, local)."""

    def perguntar(self, sistema: str, pergunta: str) -> str: ...


class ProvedorAnthropic:
    """Implementacao de referencia usando o SDK oficial `anthropic`.

    Credenciais: ANTHROPIC_API_KEY no ambiente (ou perfil de `ant auth login`).
    """

    def __init__(self, modelo: str = "claude-opus-4-8", max_tokens: int = 16000):
        import anthropic

        self._client = anthropic.Anthropic()
        self.modelo = modelo
        self.max_tokens = max_tokens

    def perguntar(self, sistema: str, pergunta: str) -> str:
        resposta = self._client.messages.create(
            model=self.modelo,
            max_tokens=self.max_tokens,
            thinking={"type": "adaptive"},
            system=sistema,
            messages=[{"role": "user", "content": pergunta}],
        )
        return "".join(b.text for b in resposta.content if b.type == "text")


class ProvedorOpenAI:
    """Provedor GPT. TODO: implementar quando o suporte multi-provedor entrar."""

    def perguntar(self, sistema: str, pergunta: str) -> str:
        raise NotImplementedError("Suporte a OpenAI ainda nao implementado")


class ProvedorLocal:
    """Modelos locais (Llama, Mistral via Ollama). TODO: implementar."""

    def perguntar(self, sistema: str, pergunta: str) -> str:
        raise NotImplementedError("Suporte a modelos locais ainda nao implementado")


class AIResearchAssistant:
    """Orquestra as consultas ao LLM a partir dos artefatos do Knowledge Engine."""

    def __init__(self, provedor: ProvedorLLM):
        self.provedor = provedor
        self._relatorios = ReportGenerator()

    def analisar_dataset(self, analise: AnaliseDataset) -> str:
        """Interpretacao geral do dataset: riscos, vieses e proximos passos."""
        relatorio = self._relatorios.gerar_markdown(analise)
        return self.provedor.perguntar(
            SISTEMA_PESQUISA,
            "Analise o relatorio abaixo, produzido pelo Knowledge Engine do "
            "KONECTA. Aponte os principais riscos para o treinamento (dados, "
            "diversidade, qualidade) e liste as acoes prioritarias antes do "
            f"proximo treinamento.\n\n{relatorio}",
        )

    def analisar_treinamento(self, metricas: dict) -> str:
        """Interpretacao de um treinamento: overfitting, classes problematicas etc.

        `metricas` deve conter o que o AI Engine exportar: accuracy, precision,
        recall, F1, avaliacao cross-signer, curvas por epoca e matriz de confusao.
        """
        return self.provedor.perguntar(
            SISTEMA_PESQUISA,
            "Interprete os resultados de treinamento abaixo. Identifique "
            "overfitting/underfitting, classes problematicas e hipoteses de "
            f"melhoria, citando as evidencias numericas.\n\n{metricas}",
        )

    def recomendar_coletas(self, analise: AnaliseDataset) -> str:
        """Prioriza a proxima rodada de coletas com justificativas."""
        relatorio = self._relatorios.gerar_markdown(analise)
        return self.provedor.perguntar(
            SISTEMA_PESQUISA,
            "Com base no relatorio abaixo, produza uma lista priorizada de "
            "coletas (sinal, quantidade sugerida, perfil de sinalizante) com "
            f"o motivo de cada prioridade.\n\n{relatorio}",
        )

    def gerar_documentacao(self, analise: AnaliseDataset, contexto: str = "") -> str:
        """Resumo tecnico do experimento para a documentacao cientifica."""
        relatorio = self._relatorios.gerar_markdown(analise)
        return self.provedor.perguntar(
            SISTEMA_PESQUISA,
            "Escreva um resumo tecnico (estilo secao de artigo) descrevendo o "
            "estado atual do dataset e os proximos passos do experimento. "
            f"Contexto adicional do pesquisador: {contexto or 'nenhum'}\n\n{relatorio}",
        )
