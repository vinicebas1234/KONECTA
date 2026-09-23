"""Controle de acesso do SIGNLAB.

Com o app de gravação publicado na internet (Tailscale Funnel), qualquer um
que tenha o endereço alcança esta porta — e até aqui o SIGNLAB não tinha senha
nenhuma: quem chegasse apagava projeto. São dois códigos, dois papéis:

- ``admin``: tudo, como antes.
- ``gravacao``: só ``/app-api/``, que fica preso ao projeto configurado para o
  app. Com o link do celular não se lista projeto, não se treina, não se baixa
  arquivo e não se apaga nada.

O código viaja num cookie HttpOnly. Não existe exceção para localhost, de
propósito: o Funnel entrega as requisições da internet vindas de 127.0.0.1,
então liberar localhost liberaria o mundo.
"""
import hmac
import json
import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from .database import DB_PATH

ARQUIVO = DB_PATH.parent / "acesso.json"
COOKIE = "signlab_acesso"
VALIDADE_S = 180 * 24 * 3600

# Abertos: a tela de entrada e a casca do app (HTML, JS, ícones — nenhum dado).
# A casca precisa ser aberta para o Android instalar o app e para ele abrir
# sem rede; os dados vêm de /app-api/, que exige código.
ABERTOS_EXATOS = {"/entrar.html", "/api/entrar", "/api/sair", "/app"}
ABERTOS_PREFIXO = ("/app/",)

router = APIRouter(tags=["acesso"])


def codigos() -> dict:
    """``{'admin': ..., 'gravacao': ...}``, gerados na primeira chamada."""
    if ARQUIVO.exists():
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    dados = {"admin": secrets.token_urlsafe(24),
             "gravacao": secrets.token_urlsafe(24)}
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(dados, indent=2), encoding="utf-8")
    return dados


def trocar_codigo(papel: str) -> str:
    """Gera um código novo para o papel; o antigo para de valer na hora."""
    dados = codigos()
    dados[papel] = secrets.token_urlsafe(24)
    ARQUIVO.write_text(json.dumps(dados, indent=2), encoding="utf-8")
    return dados[papel]


def papel_de(codigo: str | None) -> str | None:
    if not codigo:
        return None
    for papel, valor in codigos().items():
        if hmac.compare_digest(codigo.encode(), valor.encode()):
            return papel
    return None


def _aberto(caminho: str) -> bool:
    return caminho in ABERTOS_EXATOS or caminho.startswith(ABERTOS_PREFIXO)


async def exigir_acesso(request: Request, call_next):
    resposta = await _decidir(request, call_next)
    # Sem isto o Chrome reaproveita JS antigo por heurística de cache e uma
    # correção "não funciona" — já custou diagnósticos errados neste projeto.
    # Revalidar a cada carga custa um 304.
    resposta.headers.setdefault("Cache-Control", "no-cache")
    return resposta


async def _decidir(request: Request, call_next):
    caminho = request.url.path
    if _aberto(caminho):
        return await call_next(request)

    papel = papel_de(request.cookies.get(COOKIE))
    if papel == "admin" or (papel == "gravacao" and caminho.startswith("/app-api/")):
        return await call_next(request)

    quer_pagina = (request.method == "GET"
                   and "text/html" in request.headers.get("accept", ""))
    if quer_pagina:
        # Quem tem o link do celular e abre a raiz cai no app, não num erro.
        return RedirectResponse("/app/" if papel == "gravacao" else "/entrar.html",
                                status_code=303)
    if papel is None:
        return JSONResponse({"detail": "Faça login com o link de acesso."},
                            status_code=401)
    return JSONResponse({"detail": "Este acesso só permite gravar pelo app."},
                        status_code=403)


class EntrarIn(BaseModel):
    codigo: str


@router.post("/api/entrar")
def entrar(body: EntrarIn):
    codigo = body.codigo.strip()
    papel = papel_de(codigo)
    if papel is None:
        raise HTTPException(401, "Código inválido. Peça um link novo.")
    resposta = JSONResponse(
        {"papel": papel, "destino": "/" if papel == "admin" else "/app/"})
    # secure=True também em http://localhost: o Chrome trata localhost como
    # contexto seguro e aceita o cookie.
    resposta.set_cookie(COOKIE, codigo, max_age=VALIDADE_S, httponly=True,
                        secure=True, samesite="lax", path="/")
    return resposta


@router.post("/api/sair")
def sair():
    resposta = JSONResponse({"ok": True})
    resposta.delete_cookie(COOKIE, path="/", secure=True, httponly=True,
                           samesite="lax")
    return resposta
