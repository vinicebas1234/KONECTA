"""Fontes de amostras para o Knowledge Engine.

Enquanto o Dataset Engine (etapa 7) nao define o armazenamento da V2, este
modulo oferece: um adaptador SOMENTE LEITURA do dataset da V1
(`OCR/dados_libras`) e um gerador sintetico para demonstracao. Quando o
Dataset Engine existir, este adaptador migra para la.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from core.types import Amostra

# services -> backend -> KONECTA_V2 -> raiz do repositorio
_RAIZ = Path(__file__).resolve().parents[3]
CAMINHO_V1 = _RAIZ / "OCR" / "dados_libras"

Progresso = Optional[Callable[[str], None]]


def fontes_disponiveis() -> dict[str, bool]:
    return {
        "v1_dinamicos": (CAMINHO_V1 / "dinamicos").exists(),
        "v1_estaticos": (CAMINHO_V1 / "estaticos").exists(),
        "sintetico": True,
    }


def contar_v1_dinamicos() -> dict:
    """Estatisticas rapidas dos sinais dinamicos SEM carregar os `.npy`.

    Antes esta contagem reusava `carregar_v1_dinamicos()`, que decodifica
    todos os arrays de landmarks so para contar (~1366 sinais / ~4200
    arquivos = alguns minutos). Aqui apenas listamos nomes de arquivo.
    """
    base = CAMINHO_V1 / "dinamicos"
    if not base.exists():
        return {"amostras": 0, "sinais": 0, "sinalizantes": 0}

    n_amostras = 0
    n_sinais = 0
    articuladores: set[str] = set()

    for pasta_sinal in base.iterdir():
        if not pasta_sinal.is_dir():
            continue
        pasta = pasta_sinal / "public"
        if not pasta.exists():
            continue
        arquivos = list(pasta.glob("public_*.npy"))
        if not arquivos:
            continue
        n_sinais += 1
        n_amostras += len(arquivos)

        marcadores = list(pasta.glob("*.npy.done"))
        if len(marcadores) == len(arquivos):
            for m in marcadores:
                match = re.search(r"Articulador(\d+)", m.name)
                if match:
                    articuladores.add(f"Articulador{match.group(1)}")
        if not articuladores:
            articuladores.add("desconhecido")

    return {
        "amostras": n_amostras,
        "sinais": n_sinais,
        "sinalizantes": len(articuladores) if articuladores else 0,
    }


def contar_v1_estaticos() -> dict:
    """Estatisticas rapidas dos sinais estaticos SEM carregar os `.npy`."""
    base = CAMINHO_V1 / "estaticos"
    if not base.exists():
        return {"amostras": 0, "sinais": 0, "sinalizantes": 0}

    n_amostras = 0
    n_sinais = 0
    for pasta_sinal in base.iterdir():
        if not pasta_sinal.is_dir():
            continue
        arquivos = _arquivos_npy_estatico(pasta_sinal)
        if not arquivos:
            continue
        n_sinais += 1
        n_amostras += len(arquivos)

    # A V1 nao persiste o vinculo amostra->sinalizante nos sinais estaticos
    # (ver carregar_v1_estaticos): todas as amostras usam "desconhecido".
    return {"amostras": n_amostras, "sinais": n_sinais, "sinalizantes": 1 if n_amostras else 0}


def carregar(fonte: str, limite_sinais: int | None = None, on_progresso: Progresso = None) -> list[Amostra]:
    if fonte == "v1_dinamicos":
        return carregar_v1_dinamicos(limite_sinais, on_progresso)
    if fonte == "v1_estaticos":
        return carregar_v1_estaticos(limite_sinais, on_progresso)
    if fonte == "sintetico":
        return gerar_sintetico()
    raise ValueError(f"Fonte desconhecida: {fonte}")


def _taxa_frames_sem_deteccao(landmarks: np.ndarray) -> float:
    """Fracao de frames em que nenhuma mao foi detectada (todos os pontos zerados)."""
    return float(np.mean(np.all(landmarks == 0, axis=(1, 2))))


def carregar_v1_dinamicos(
    limite_sinais: int | None = None, on_progresso: Progresso = None
) -> list[Amostra]:
    """Le os sinais dinamicos da V1: `dinamicos/<Sinal>/public/public_NNNN.npy`.

    Cada arquivo tem shape (frames, 126) = 2 maos x 21 pontos x 3 coords,
    remodelado aqui para (frames, 42, 3). Os marcadores `*.npy.done` indicam
    os videos de origem (Articulador1..3); quando a contagem bate com a de
    amostras, o articulador e atribuido por ordem — uma heuristica, ja que a
    V1 nao grava o vinculo amostra->articulador explicitamente.
    """
    base = CAMINHO_V1 / "dinamicos"
    amostras: list[Amostra] = []
    pastas = sorted(p for p in base.iterdir() if p.is_dir())
    if limite_sinais:
        pastas = pastas[:limite_sinais]

    for i, pasta_sinal in enumerate(pastas):
        if on_progresso and i % 100 == 0:
            on_progresso(f"Lendo dataset V1: {i}/{len(pastas)} sinais")
        pasta = pasta_sinal / "public"
        if not pasta.exists():
            continue
        arquivos = sorted(pasta.glob("public_*.npy"))
        marcadores = sorted(pasta.glob("*.npy.done"))
        articuladores: list[str] | None = None
        if len(marcadores) == len(arquivos):
            nomes = [re.search(r"Articulador(\d+)", m.name) for m in marcadores]
            if all(nomes):
                articuladores = [f"Articulador{n.group(1)}" for n in nomes]

        for j, arquivo in enumerate(arquivos):
            dados = np.load(arquivo)
            landmarks = dados.reshape(dados.shape[0], -1, 3).astype(np.float32)
            amostras.append(Amostra(
                id=f"{pasta_sinal.name}/{arquivo.stem}",
                sinal=pasta_sinal.name,
                sinalizante=articuladores[j] if articuladores else "desconhecido",
                caminho=str(arquivo),
                n_frames=landmarks.shape[0],
                fps=None,          # a V1 reamostra para 30 frames sem gravar o fps original
                duracao_s=None,
                confianca_media=None,  # a V1 nao persiste a confianca do MediaPipe
                taxa_landmarks_perdidos=_taxa_frames_sem_deteccao(landmarks),
                landmarks=landmarks,
            ))
    return amostras


def _arquivos_npy_estatico(pasta_sinal: Path) -> list[Path]:
    """Lista os `.npy` de um sinal estatico.

    Alguns sinais (ex.: B, D, E, F, G) tem as amostras direto na pasta do
    sinal (`<Letra>/NNNN.npy`); outros guardam num subdiretorio
    `<Letra>/local/local_NNNN.npy`. Usar so `glob("*.npy")` ignora esse
    segundo formato e descartava silenciosamente ~70% das amostras
    estaticas (5 de 7 sinais ficavam com 0 amostras). Aqui buscamos em
    ambos os niveis.
    """
    diretos = sorted(pasta_sinal.glob("*.npy"))
    aninhados = sorted(pasta_sinal.glob("*/*.npy"))
    return diretos + aninhados


def carregar_v1_estaticos(
    limite_sinais: int | None = None, on_progresso: Progresso = None
) -> list[Amostra]:
    """Le os sinais estaticos da V1: `estaticos/<Letra>/NNNN.npy` (ou
    `estaticos/<Letra>/local/local_NNNN.npy`), shape (126,)."""
    base = CAMINHO_V1 / "estaticos"
    amostras: list[Amostra] = []
    pastas = sorted(p for p in base.iterdir() if p.is_dir())
    if limite_sinais:
        pastas = pastas[:limite_sinais]

    for i, pasta_sinal in enumerate(pastas):
        if on_progresso and i % 5 == 0:
            on_progresso(f"Lendo dataset V1 (estaticos): {i}/{len(pastas)} sinais")
        for arquivo in _arquivos_npy_estatico(pasta_sinal):
            dados = np.load(arquivo)
            landmarks = dados.reshape(1, -1, 3).astype(np.float32)
            amostras.append(Amostra(
                id=f"{pasta_sinal.name}/{arquivo.stem}",
                sinal=pasta_sinal.name,
                sinalizante="desconhecido",
                caminho=str(arquivo),
                n_frames=1,
                taxa_landmarks_perdidos=_taxa_frames_sem_deteccao(landmarks),
                landmarks=landmarks,
            ))
    return amostras


def gerar_sintetico(n_sinais: int = 5, n_sinalizantes: int = 3, n_execucoes: int = 4) -> list[Amostra]:
    """Dataset sintetico pequeno para demonstracao e testes da interface."""
    amostras: list[Amostra] = []
    idx = 0
    for s in range(n_sinais):
        for a in range(n_sinalizantes):
            for _ in range(n_execucoes):
                rng = np.random.default_rng(idx)
                n_frames = 30
                base = rng.random((1, 42, 3))
                trajetoria = base + np.cumsum(
                    rng.normal(0, 0.01, (n_frames, 42, 3)), axis=0
                )
                amostras.append(Amostra(
                    id=f"sintetico_{idx:04d}",
                    sinal=f"SINAL_{s + 1:02d}",
                    sinalizante=f"Articulador{a + 1}",
                    n_frames=n_frames,
                    fps=30.0,
                    duracao_s=1.0,
                    confianca_media=float(rng.uniform(0.7, 0.99)),
                    taxa_landmarks_perdidos=float(rng.uniform(0.0, 0.1)),
                    landmarks=trajetoria.astype(np.float32),
                ))
                idx += 1
    return amostras
