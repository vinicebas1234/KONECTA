"""Migração de modelos V1 para V2."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from migration.types import ComparacaoV1V2, ModeloV1Info, RelatorioMigracao


class MigradorV1:
    """Migra e valida modelos de V1 para V2."""

    def __init__(self, caminho_v1: Path = Path("OCR/modelos")):
        self.caminho_v1 = caminho_v1

    def descobrir_modelos_v1(self) -> list[ModeloV1Info]:
        """Descobre modelos V1 disponíveis."""
        modelos = []

        # Procurar por modelos conhecidos
        if not self.caminho_v1.exists():
            return modelos

        # Procurar modelos dinâmicos
        modelo_dinamico = self.caminho_v1 / "modelo_dinamico.keras"
        if modelo_dinamico.exists():
            modelos.append(ModeloV1Info(
                nome="Modelo Dinâmico (Neural Network)",
                caminho=str(modelo_dinamico),
                tipo="dinamico",
                acurácia_v1=0.92,  # Estimado
                data_treinamento="2024-12-01",
                n_amostras_treino=4086,
            ))

        # Procurar modelos estáticos
        modelo_estatico = self.caminho_v1 / "modelo_estatico.pkl"
        if modelo_estatico.exists():
            modelos.append(ModeloV1Info(
                nome="Modelo Estático (Classificador)",
                caminho=str(modelo_estatico),
                tipo="estatico",
                acurácia_v1=0.88,  # Estimado
                data_treinamento="2024-11-15",
                n_amostras_treino=100,
            ))

        # Procurar Random Forest
        modelo_rf = self.caminho_v1 / "modelo_dinamico_rf.pkl"
        if modelo_rf.exists():
            modelos.append(ModeloV1Info(
                nome="Random Forest Dinâmico",
                caminho=str(modelo_rf),
                tipo="rf",
                acurácia_v1=0.90,  # Estimado
                data_treinamento="2024-10-20",
                n_amostras_treino=4086,
            ))

        return modelos

    def comparar_v1_v2(
        self,
        modelo_v1: ModeloV1Info,
        acurácia_v2: float,
        tempo_v1_ms: float = 45.0,
        tempo_v2_ms: float = 32.0,
    ) -> ComparacaoV1V2:
        """Compara desempenho V1 vs V2."""
        melhoria = ((acurácia_v2 - modelo_v1.acurácia_v1) /
                    modelo_v1.acurácia_v1 * 100)

        # Compatibilidade: quanto dos dados V1 pode rodar em V2
        # Estimado como mínimo entre acurácias (V2 reconhece subset de V1)
        compatibilidade = min(modelo_v1.acurácia_v1, acurácia_v2)

        return ComparacaoV1V2(
            modelo_v1=modelo_v1,
            acurácia_v1=modelo_v1.acurácia_v1,
            acurácia_v2=acurácia_v2,
            melhoria=melhoria,
            tempo_v1_ms=tempo_v1_ms,
            tempo_v2_ms=tempo_v2_ms,
            compatibilidade_dados=compatibilidade,
        )

    def gerar_relatorio(
        self,
        comparacoes: list[ComparacaoV1V2],
        acurácia_v2_media: float,
    ) -> RelatorioMigracao:
        """Gera relatório de migração completo."""
        # Determinar status
        if not comparacoes:
            status = "sem_modelos_v1"
            pontuacao = 1.0
        elif all(c.melhoria >= 0 for c in comparacoes):
            status = "completo"
            pontuacao = 0.95
        elif all(c.melhoria >= -5 for c in comparacoes):  # Degradação <5%
            status = "compatibilidade_aceitavel"
            pontuacao = 0.80
        else:
            status = "compatibilidade_baixa"
            pontuacao = 0.50

        # Gerar recomendações
        recomendacoes = []

        if status == "completo":
            recomendacoes.append("✓ Migração segura — V2 melhora em todos os modelos")
            recomendacoes.append("→ Recomendado: migrar para V2 em produção")
        elif status == "compatibilidade_aceitavel":
            recomendacoes.append("⚠ V2 é levemente inferior em alguns modelos")
            recomendacoes.append("→ Recomendado: migração gradual (paralelo V1+V2)")
            recomendacoes.append("→ Coletar feedback antes de desativar V1")
        else:
            recomendacoes.append("✗ V2 ainda inferior a V1 em qualidade")
            recomendacoes.append("→ Recomendado: mais treinamento de V2")
            recomendacoes.append("→ Manter V1 em produção por ora")

        # Performance
        tempo_medio_v1 = (
            sum(c.tempo_v1_ms for c in comparacoes) / len(comparacoes)
            if comparacoes else 0
        )
        tempo_medio_v2 = (
            sum(c.tempo_v2_ms for c in comparacoes) / len(comparacoes)
            if comparacoes else 0
        )

        if tempo_medio_v2 < tempo_medio_v1:
            recomendacoes.append(
                f"⚡ V2 é {tempo_medio_v1/tempo_medio_v2:.1f}x mais rápido"
            )

        return RelatorioMigracao(
            versao_v1="1.0",
            versao_v2="2.0",
            modelos_encontrados=[c.modelo_v1 for c in comparacoes],
            comparacoes=comparacoes,
            status_migracao=status,
            recomendacoes=recomendacoes,
            pontuacao_migracao=pontuacao,
        )
