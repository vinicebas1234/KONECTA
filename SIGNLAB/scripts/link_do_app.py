#!/usr/bin/env python3
"""Configura o app de gravação e mostra os links de acesso.

Uso:
    python scripts/link_do_app.py                  mostra os links
    python scripts/link_do_app.py --projeto 1      escolhe o projeto em que o app grava
    python scripts/link_do_app.py --novo-codigo    invalida o link que está com ela
"""
import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.backend import acesso  # noqa: E402
from app.backend.database import DB_PATH, init_db  # noqa: E402
from app.backend.routes import app_gravacao  # noqa: E402

TAILSCALE_PADRAO = Path("C:/Program Files/Tailscale/tailscale.exe")


def endereco_publico() -> str | None:
    """O nome *.ts.net desta máquina, se o Tailscale estiver instalado e logado."""
    exe = shutil.which("tailscale") or (str(TAILSCALE_PADRAO) if TAILSCALE_PADRAO.exists() else None)
    if not exe:
        return None
    try:
        saida = subprocess.run([exe, "status", "--json"], capture_output=True, timeout=10, check=True).stdout
        nome = json.loads(saida)["Self"]["DNSName"].rstrip(".")
    except Exception:
        return None
    return f"https://{nome}" if nome else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--projeto", type=int, help="id do projeto em que o app grava")
    ap.add_argument("--novo-codigo", action="store_true",
                    help="gera um código novo para o celular; o link antigo para de valer")
    args = ap.parse_args()

    init_db()
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    projetos = db.execute("SELECT id, name FROM projects ORDER BY id").fetchall()

    if args.projeto is not None:
        if not any(p["id"] == args.projeto for p in projetos):
            sys.exit(f"[ERRO] projeto {args.projeto} não existe.")
        # O que já está no projeto não dispara publicação: só o que ela gravar
        # daqui para frente. Sem isto, configurar o app retreinaria na hora e
        # trocaria o modelo que está no KONECTA.
        ultimo = db.execute(
            """SELECT COALESCE(MAX(e.id), 0) FROM examples e
               JOIN classes c ON c.id = e.class_id WHERE c.project_id = ?""",
            (args.projeto,)).fetchone()[0]
        app_gravacao.salvar_config(projeto_id=args.projeto)
        app_gravacao.salvar_estado(publicado_ate=ultimo, estado="ocioso", mensagem=None)
        print(f"[OK] o app grava no projeto {args.projeto}")

    if args.novo_codigo:
        acesso.trocar_codigo("gravacao")
        print("[OK] código do celular trocado; o link antigo parou de valer")

    cfg = app_gravacao.ler_config()
    print()
    if not cfg["projeto_id"]:
        print("O app ainda não tem projeto. Escolha um e rode de novo com --projeto N:")
        for p in projetos:
            print(f"   {p['id']:>3}  {p['name']}")
        print()
    else:
        nome = next((p["name"] for p in projetos if p["id"] == cfg["projeto_id"]), "?")
        print(f"Projeto do app: {cfg['projeto_id']} - {nome}")
        print(f"Publica no KONECTA em: {cfg['publicar_em']}")
        print(f"Treina {cfg['espera_s']}s depois da última gravação; "
              f"só publica com acurácia >= {cfg['acuracia_minima']:.0%}")
        print()

    codigos = acesso.codigos()
    print("PARA VOCÊ (admin, só neste computador):")
    print(f"   http://localhost:8100/entrar.html#codigo={codigos['admin']}")
    print()
    publico = endereco_publico()
    if publico:
        print("PARA ELA (mande pelo WhatsApp e peça para abrir no Chrome):")
        print(f"   {publico}/entrar.html#codigo={codigos['gravacao']}")
    else:
        print("PARA ELA: o Tailscale não está instalado ou logado neste computador.")
        print("   Veja APP_ANDROID.md, passo 1. Depois rode este script de novo.")


if __name__ == "__main__":
    main()
