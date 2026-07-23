"""Teste Smoke — Etapa 13 (Migração V1)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from migration import MigradorV1


def main() -> None:
    print("=" * 70)
    print("TESTE SMOKE — MIGRAÇÃO V1")
    print("=" * 70)
    print()

    # Criar migrador
    migrador = MigradorV1()

    # Descobrir modelos V1
    print("▶️  Descobrindo modelos V1...")
    print("-" * 70)
    modelos = migrador.descobrir_modelos_v1()
    print(f"✓ {len(modelos)} modelos encontrados:")
    for modelo in modelos:
        print(f"   • {modelo.nome} ({modelo.tipo})")
        print(f"     - Acurácia V1: {modelo.acurácia_v1:.1%}")
        print(f"     - Treino: {modelo.n_amostras_treino} amostras")
    print()

    # Simular comparação V1 vs V2
    if modelos:
        print("▶️  Simulando comparação V1 vs V2...")
        print("-" * 70)

        comparacoes = []
        for modelo in modelos:
            # Simular desempenho V2 ligeiramente melhor
            acurácia_v2 = min(modelo.acurácia_v1 * 1.05 + 0.01, 0.99)

            comparacao = migrador.comparar_v1_v2(
                modelo_v1=modelo,
                acurácia_v2=acurácia_v2,
                tempo_v1_ms=45.0,
                tempo_v2_ms=32.0,
            )

            comparacoes.append(comparacao)

            print(f"\n{modelo.nome}:")
            print(f"  V1: {comparacao.acurácia_v1:.1%} em {comparacao.tempo_v1_ms:.0f}ms")
            print(f"  V2: {comparacao.acurácia_v2:.1%} em {comparacao.tempo_v2_ms:.0f}ms")
            print(f"  Melhoria: {comparacao.melhoria:+.1f}%")
            print(f"  Compatibilidade: {comparacao.compatibilidade_dados:.1%}")

        print()

        # Gerar relatório
        print("▶️  Gerando relatório de migração...")
        print("-" * 70)
        relatorio = migrador.gerar_relatorio(
            comparacoes=comparacoes,
            acurácia_v2_media=sum(c.acurácia_v2 for c in comparacoes) / len(comparacoes),
        )

        print(f"\nStatus: {relatorio.status_migracao}")
        print(f"Pontuação: {relatorio.pontuacao_migracao:.1%}")
        print(f"\nRecomendações:")
        for rec in relatorio.recomendacoes:
            print(f"  • {rec}")
    else:
        print("⚠️  Nenhum modelo V1 encontrado em OCR/modelos/")
        print("   (Teste com dados simulados)")
        print()

        # Teste com dados simulados
        from migration.types import ModeloV1Info

        modelo_simulado = ModeloV1Info(
            nome="Modelo Simulado V1",
            caminho="simulado",
            tipo="rf",
            acurácia_v1=0.92,
            data_treinamento="2024-12-01",
            n_amostras_treino=4086,
        )

        comparacao = migrador.comparar_v1_v2(
            modelo_v1=modelo_simulado,
            acurácia_v2=0.95,
        )

        relatorio = migrador.gerar_relatorio(
            comparacoes=[comparacao],
            acurácia_v2_media=0.95,
        )

        print(f"Status: {relatorio.status_migracao}")
        print(f"Pontuação: {relatorio.pontuacao_migracao:.1%}")
        print(f"\nRecomendações:")
        for rec in relatorio.recomendacoes:
            print(f"  • {rec}")

    print()
    print("=" * 70)
    print("✅ TESTE SMOKE: OK")
    print("=" * 70)


if __name__ == "__main__":
    main()
