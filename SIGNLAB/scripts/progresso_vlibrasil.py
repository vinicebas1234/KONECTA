#!/usr/bin/env python3
"""Mostra o andamento da importacao e da extracao do V-LIBRASIL.

Le' o disco, nao o processo: pode abrir, fechar e reabrir a vontade, e
funciona mesmo que o import tenha sido disparado de outra janela.
"""
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ORIGEM = Path("C:/KONECTA/Datasets/videos UFPE (V-LIBRASIL)/data")
DESTINO = RAIZ / "projects" / "vlibrasil-completo"
INTERVALO = 15


def barra(feito: int, total: int, largura: int = 32) -> str:
    cheio = int(largura * feito / total) if total else 0
    return "#" * cheio + "-" * (largura - cheio)


def contar(pasta: Path, padrao: str) -> int:
    return sum(1 for _ in pasta.rglob(padrao)) if pasta.exists() else 0


def main():
    total = contar(ORIGEM, "*.mp4")
    if not total:
        sys.exit(f"[ERRO] dataset nao encontrado em {ORIGEM}")

    anterior, parado_desde = None, time.monotonic()
    while True:
        copiados = contar(DESTINO, "*.mp4")
        extraidos = contar(DESTINO / "sequences", "*.npy")
        livre = shutil.disk_usage("C:/").free / 2**30

        print("\033[2J\033[H", end="")            # limpa a tela
        print("=" * 52)
        print("  V-LIBRASIL - andamento")
        print("=" * 52)
        print(f"\n  copiando   [{barra(copiados, total)}] {copiados:>5}/{total}")
        print(f"  extraindo  [{barra(extraidos, total)}] {extraidos:>5}/{total}")
        print(f"\n  disco livre: {livre:.0f} GB")

        estado = (copiados, extraidos)
        if estado == anterior:
            parado = time.monotonic() - parado_desde
            if parado > 90:
                print(f"  [!] sem mudanca ha {parado/60:.0f} min")
        else:
            anterior, parado_desde = estado, time.monotonic()

        if extraidos >= total:
            print("\n  [OK] concluido")
            return
        print(f"\n  atualiza a cada {INTERVALO}s - Ctrl+C para sair")
        time.sleep(INTERVALO)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  (encerrado - a importacao continua rodando)")
