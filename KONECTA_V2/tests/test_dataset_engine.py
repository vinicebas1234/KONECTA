"""Teste do Dataset Engine — abstração de fontes e carregamento.

Roda com: python tests/test_dataset_engine.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.dataset import manager as dataset_engine


def main() -> None:
    print("=== Dataset Engine — Teste de Abstração de Fontes ===\n")

    # Verificar quais fontes estão disponíveis
    fontes = dataset_engine.fontes_disponiveis()
    print("Fontes disponíveis:")
    for nome, disponivel in fontes.items():
        status = "✓" if disponivel else "✗"
        print(f"  {status} {nome}")
    print()

    # Testar carregamento de cada fonte disponível
    for nome, disponivel in fontes.items():
        if not disponivel:
            print(f"[PULADO] {nome} — não disponível\n")
            continue

        print(f"[TESTANDO] {nome}")
        try:
            # Contar sem carregar as amostras
            stats = dataset_engine.contar(nome)
            print(f"  Estatísticas rápidas:")
            print(f"    - Amostras: {stats['amostras']}")
            print(f"    - Sinais: {stats['sinais']}")
            print(f"    - Sinalizantes: {stats['sinalizantes']}")

            # Carregar com limite pequenininho
            amostras = dataset_engine.listar(nome, limite_sinais=3)
            assert len(amostras) > 0, "Nenhuma amostra carregada!"
            amostra_primeira = amostras[0]
            print(f"  Primeira amostra:")
            print(f"    - ID: {amostra_primeira.id}")
            print(f"    - Sinal: {amostra_primeira.sinal}")
            print(f"    - Sinalizante: {amostra_primeira.sinalizante}")
            print(f"    - Frames: {amostra_primeira.n_frames}")

            # Testar cache
            amostras_cached = dataset_engine.listar(nome, limite_sinais=3, usar_cache=True)
            assert len(amostras_cached) == len(amostras), "Cache falhou!"
            print(f"  Cache: ✓ funcionando")

            print()

        except Exception as e:
            print(f"  ✗ Erro: {e}\n")

    print("=== Teste concluído ===")


if __name__ == "__main__":
    main()
