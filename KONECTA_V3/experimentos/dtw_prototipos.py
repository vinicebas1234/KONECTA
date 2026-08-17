"""Mede reconhecimento por protótipo + DTW, cross-signer, sem treinar nada.

Responde a pergunta que falta no projeto: quanto uma comparação por similaridade
entrega no mesmo split honesto onde a LSTM entregou 0,44%?

Split (idêntico ao da Fase 0 do LSAE):
    treino = Articulador 1 e 3   → viram os protótipos
    teste  = Articulador 2       → sinalizante nunca visto

Protótipos são calculados SÓ com o treino. Reaproveitar
``perfil_dinamico_sinais.pkl`` seria mais rápido, mas ele foi computado sobre o
dataset inteiro — incluindo o Articulador 2 — e contaminaria o teste.

Só leitura: nada em archive/, SIGNLAB ou TEXTO_PARA_LIBRAS é modificado.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

RAIZ_V1 = Path("C:/KONECTA/archive/OCR")
DADOS = RAIZ_V1 / "dados_libras" / "dinamicos"
CSV_MAPA = RAIZ_V1 / "vlibrasil_converter_20260630_184206.csv"

SINALIZANTES_TREINO = {"1", "3"}
SINALIZANTE_TESTE = "2"

PONTOS_RESUMO = 8  # trajetória reamostrada para o filtro grosseiro
CANDIDATOS_DTW = 50  # quantos sobrevivem ao filtro e vão para o DTW


# ----------------------------------------------------------------- dados


def carregar_mapa_sinalizante() -> Dict[Path, str]:
    """arquivo .npy → número do articulador, lido do log da conversão."""
    mapa: Dict[Path, str] = {}
    with open(CSV_MAPA, "r", encoding="utf-8", errors="replace") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha.get("status") != "ok":
                continue
            nome = linha.get("arquivo", "")
            if "Articulador" not in nome:
                continue
            articulador = nome.split("Articulador")[1][0]
            # o destino aponta para OCR/, mas os dados moraram para archive/OCR/
            destino = Path(linha["destino"])
            mapa[Path(*destino.parts[-5:])] = articulador
    return mapa


def carregar_dataset(mapa: Dict[Path, str], limite_classes: Optional[int] = None):
    """Devolve (treino, teste) como listas de (rotulo, sequencia)."""
    treino: List[Tuple[str, np.ndarray]] = []
    teste: List[Tuple[str, np.ndarray]] = []

    classes = sorted(p.name for p in DADOS.iterdir() if p.is_dir())
    if limite_classes:
        classes = classes[:limite_classes]

    for rotulo in classes:
        pasta = DADOS / rotulo / "public"
        if not pasta.is_dir():
            continue
        for caminho in sorted(pasta.glob("*.npy")):
            chave = Path(*caminho.parts[-5:])
            articulador = mapa.get(chave)
            if articulador is None:
                continue
            try:
                sequencia = np.load(caminho).astype(np.float32)
            except Exception:
                continue
            if sequencia.ndim != 2 or sequencia.shape[0] < 2:
                continue
            destino = treino if articulador in SINALIZANTES_TREINO else (
                teste if articulador == SINALIZANTE_TESTE else None
            )
            if destino is not None:
                destino.append((rotulo, sequencia))
    return treino, teste


# ----------------------------------------------------------- normalização


def normalizar(sequencia: np.ndarray) -> np.ndarray:
    """Centra e escala cada frame, para tirar posição e tamanho da pessoa.

    O dataset vem em (T, 126) = 2 mãos x 21 pontos x 3 coords. Sem isto, a
    distância mede onde a pessoa estava na imagem, não o gesto que ela fez.
    """
    seq = np.asarray(sequencia, dtype=np.float32)
    if seq.shape[1] % 3 != 0:
        return seq
    pontos = seq.reshape(seq.shape[0], -1, 3)

    saida = np.zeros_like(pontos)
    for i, frame in enumerate(pontos):
        validos = frame[np.any(frame != 0, axis=1)]
        if len(validos) == 0:
            continue
        centro = validos.mean(axis=0)
        centrado = frame - centro
        escala = float(np.linalg.norm(centrado[np.any(frame != 0, axis=1)], axis=1).mean())
        saida[i] = centrado / escala if escala > 1e-6 else centrado
    return saida.reshape(seq.shape[0], -1)


def reamostrar(sequencia: np.ndarray, n: int) -> np.ndarray:
    """Reamostra a sequência para n passos por interpolação linear."""
    if len(sequencia) == n:
        return sequencia
    origem = np.linspace(0.0, 1.0, len(sequencia))
    destino = np.linspace(0.0, 1.0, n)
    return np.stack([np.interp(destino, origem, sequencia[:, c])
                     for c in range(sequencia.shape[1])], axis=1)


# ------------------------------------------------------------------ DTW


def dtw(a: np.ndarray, b: np.ndarray, banda: int = 10) -> float:
    """Distância DTW com banda de Sakoe-Chiba (limita o quanto pode esticar)."""
    n, m = len(a), len(b)
    custo = np.full((n + 1, m + 1), np.inf, dtype=np.float32)
    custo[0, 0] = 0.0
    for i in range(1, n + 1):
        inicio = max(1, i - banda)
        fim = min(m, i + banda)
        dif = b[inicio - 1:fim] - a[i - 1]
        distancias = np.sqrt((dif * dif).sum(axis=1))
        for desloc, j in enumerate(range(inicio, fim + 1)):
            custo[i, j] = distancias[desloc] + min(
                custo[i - 1, j], custo[i, j - 1], custo[i - 1, j - 1]
            )
    return float(custo[n, m] / (n + m))


# ------------------------------------------------------------ protótipos


def construir_prototipos(treino, comprimento: int, modo: str = "media"):
    """Constrói as referências de comparação.

    ``media``: uma referência por sinal (média das amostras de treino).
    ``knn``:   cada amostra de treino vira uma referência própria.

    A distinção importa porque as amostras de um sinal vêm de pessoas
    diferentes: a média entre dois estilos de execução pode não se parecer com
    nenhum dos dois.
    """
    por_rotulo = defaultdict(list)
    for rotulo, sequencia in treino:
        por_rotulo[rotulo].append(reamostrar(normalizar(sequencia), comprimento))

    prototipos, resumos, rotulos = [], [], []
    for rotulo, amostras in sorted(por_rotulo.items()):
        referencias = [np.mean(np.stack(amostras), axis=0)] if modo == "media" else amostras
        for referencia in referencias:
            prototipos.append(referencia)
            resumos.append(reamostrar(referencia, PONTOS_RESUMO).reshape(-1))
            rotulos.append(rotulo)
    return rotulos, prototipos, np.stack(resumos)


def prever(sequencia, rotulos, prototipos, resumos, comprimento, candidatos):
    """Filtro grosseiro por euclidiana, reranking fino por DTW."""
    consulta = reamostrar(normalizar(sequencia), comprimento)
    resumo = reamostrar(consulta, PONTOS_RESUMO).reshape(-1)

    distancias = np.linalg.norm(resumos - resumo, axis=1)
    k = min(candidatos, len(rotulos))
    finalistas = np.argpartition(distancias, k - 1)[:k]

    pontuados = [(dtw(consulta, prototipos[i]), rotulos[i]) for i in finalistas]
    pontuados.sort()
    # deduplica mantendo a melhor distancia por rotulo (modo knn repete rotulos)
    vistos, ranking = set(), []
    for distancia, rotulo in pontuados:
        if rotulo not in vistos:
            vistos.add(rotulo)
            ranking.append((rotulo, distancia))
    return ranking


# ------------------------------------------------------------------ main


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--classes", type=int, default=None, help="limita nº de classes")
    p.add_argument("--comprimento", type=int, default=30)
    p.add_argument("--candidatos", type=int, default=CANDIDATOS_DTW)
    p.add_argument("--modo", choices=["media", "knn"], default="media")
    args = p.parse_args()

    print("carregando mapa de sinalizantes…", flush=True)
    mapa = carregar_mapa_sinalizante()
    print(f"  {len(mapa)} arquivos mapeados", flush=True)

    print("carregando dataset…", flush=True)
    treino, teste = carregar_dataset(mapa, args.classes)
    classes_treino = {r for r, _ in treino}
    print(f"  treino: {len(treino)} amostras, {len(classes_treino)} classes "
          f"(Articulador {'+'.join(sorted(SINALIZANTES_TREINO))})", flush=True)
    print(f"  teste:  {len(teste)} amostras (Articulador {SINALIZANTE_TESTE})", flush=True)

    if not treino or not teste:
        print("FALHOU: split vazio", flush=True)
        return 1

    print("construindo protótipos (só com treino)…", flush=True)
    rotulos, prototipos, resumos = construir_prototipos(treino, args.comprimento, args.modo)
    print(f"  {len(rotulos)} referencias (modo={args.modo})", flush=True)

    print("avaliando…", flush=True)
    inicio = time.time()
    acertos = 0
    acertos_top5 = 0
    avaliados = 0
    tempos = []
    for i, (verdadeiro, sequencia) in enumerate(teste):
        if verdadeiro not in classes_treino:
            continue  # sinal sem protótipo: não é falha do método
        t0 = time.time()
        ranking = prever(sequencia, rotulos, prototipos, resumos,
                         args.comprimento, args.candidatos)
        tempos.append(time.time() - t0)
        avaliados += 1
        nomes = [r for r, _ in ranking]
        acertos += int(bool(nomes) and nomes[0] == verdadeiro)
        acertos_top5 += int(verdadeiro in nomes[:5])
        if avaliados % 100 == 0:
            print(f"  {avaliados} avaliados… acurácia parcial "
                  f"{acertos / avaliados:.2%}", flush=True)

    duracao = time.time() - inicio
    acuracia = acertos / avaliados if avaliados else 0.0
    acaso = 1.0 / max(1, len(classes_treino))

    print("", flush=True)
    print("=" * 62, flush=True)
    print(f"RESULTADO  acuracia_cross_signer={acuracia:.4%}", flush=True)
    print(f"           acertos_top1={acertos}/{avaliados}", flush=True)
    print(f"           acuracia_top5={acertos_top5/avaliados:.4%}", flush=True)
    print(f"           classes={len(classes_treino)}  acaso={acaso:.4%}", flush=True)
    print(f"           vezes_o_acaso={acuracia / acaso:.1f}x", flush=True)
    print(f"           latencia_mediana={np.median(tempos) * 1000:.0f}ms/consulta", flush=True)
    print(f"           duracao_total={duracao:.0f}s", flush=True)
    print("           referencia LSTM (Fase 0) = 0.44%", flush=True)
    print("=" * 62, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
