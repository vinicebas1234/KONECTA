"""Ciclo 9: experimento de calibração cross-signer — diagnóstico, não feature.

CONTEXTO — o problema exato que este módulo investiga
------------------------------------------------------
O Ciclo 7 (`ml/training.py::evaluate_leave_one_signer_out`) mediu **28,0%
top-1 / 49,3% top-5** cross-signer em 25 sinais reais do V-LIBRASIL (ver
commit `0447574`). Um experimento anterior e isolado do projeto
(`KONECTA_V3/experimentos/dtw_prototipos.py`, resultados em
`KONECTA_V3/RECONHECIMENTO_RECOMENDACAO.md` seção 5.1) mediu **47,4% top-1**
em 20 sinais com uma abordagem também de protótipo+DTW. Mesma família de
método, vocabulário quase do mesmo tamanho, resultado bem diferente.

Lendo `dtw_prototipos.py` (linha a linha, comentado abaixo onde cada variante
o reproduz) identificamos 4 diferenças concretas em relação ao pipeline do
Ciclo 7:

1. Fonte dos dados: `dtw_prototipos.py` usa `.npy` já extraídos por outro
   pipeline (126-dim, sem flags de presença); o Ciclo 7 extrai landmarks NOVOS
   via MediaPipe (128-dim, com flags). **NÃO testado aqui** — reprocessar o
   dataset V1 antigo está fora do escopo deste ciclo. Fica registrado como
   suspeita não eliminada, possivelmente a maior causa do gap.
2. Normalização: center-of-mass (ambas as mãos juntas) vs. por-mão (punho).
3. DTW: banda de Sakoe-Chiba + reamostragem para comprimento fixo vs. exato,
   sem banda, sobre o comprimento original.
4. Split de avaliação: único (treino=Articulador 1+3, teste=Articulador 2)
   vs. leave-one-signer-out com 3 dobras.

Os fatores 2-4 são isolados aqui, um de cada vez, adicionando cada mudança à
anterior (V0 → V1 → V2 → V3), sempre sobre o MESMO conjunto de landmarks
brutos extraídos uma única vez (`load_raw_dataset`) — é o que torna a
comparação honesta: se os dados de entrada mudassem entre variantes, um
resultado diferente não provaria nada sobre o fator testado.

Nada aqui é produção: `ml/features.py::normalize_hand_landmarks`,
`ml/dtw.py::dtw_distance` e `ml/training.py::evaluate_leave_one_signer_out`
continuam exatamente como estão — são reaproveitados (não copiados) por V0/V1
e permanecem o que o resto do LLA usa. As funções novas deste módulo só
existem para as variantes V2/V3, que production ainda não usa.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from libras_learning_agent.ml.dataset import (
    DEFAULT_VLIBRASIL_ROOT,
    Sample,
    discover_vocabulary,
)
from libras_learning_agent.ml.dtw import dtw_distance
from libras_learning_agent.ml.features import VECTOR_SIZE, normalize_hand_landmarks
from libras_learning_agent.ml.training import evaluate_leave_one_signer_out
from libras_learning_agent.vision.hand_landmarks import (
    HandExtractionResult,
    extract_hand_landmarks,
)

# Mesmo vocabulário do Ciclo 7: `discover_vocabulary(..., min_signs=25, max_signs=25)`
# devolve os 25 primeiros sinais (ordem alfabética) com os 3 articuladores
# presentes — confirmado que é um prefixo determinístico do vocabulário de até
# 30 sinais que os parâmetros default do Ciclo 7 seleccionariam. O commit
# `0447574` documenta "25 sinais reais do V-LIBRASIL (escolha determinística,
# primeiros em ordem alfabética)" e "28,0% top-1 / 49,3% top-5" — é o número
# que V0 deve reproduzir.
VOCAB_SIZE = 25

# Split único de `dtw_prototipos.py` / Fase 0 do LSAE.
SPLIT_TRAIN_SIGNERS = ("1", "3")
SPLIT_TEST_SIGNER = "2"

# Parâmetros default de `dtw_prototipos.py` (`--comprimento`, `banda=10`).
RESAMPLE_LENGTH = 30
SAKOE_CHIBA_BAND = 10


# ============================================================================
# Extração dos dados brutos — uma única vez, reaproveitada por todas as variantes
# ============================================================================


@dataclass(frozen=True)
class RawSample:
    """Uma amostra ainda não normalizada: extração crua do Ciclo 1 + rótulos."""

    sign: str
    signer: str
    extraction: HandExtractionResult
    video_path: Path


def load_raw_dataset(
    vocab_size: int = VOCAB_SIZE,
    videos_root: Path = DEFAULT_VLIBRASIL_ROOT,
    model_path: Optional[Path] = None,
) -> List[RawSample]:
    """Extrai landmarks BRUTOS (MediaPipe, Ciclo 1) uma única vez.

    Devolve a extração crua, não normalizada — cada variante decide sua
    própria normalização a partir daqui (`_build_samples`). É o ponto que
    garante que V0-V3 comparam o MESMO dado bruto (mesmos vídeos, mesmos
    frames, mesma detecção de mão): só normalização/DTW/split mudam depois
    deste ponto. Chame esta função UMA VEZ por execução do experimento — ver
    `run_all`.
    """
    vocabulary = discover_vocabulary(videos_root, min_signs=vocab_size, max_signs=vocab_size)
    raw: List[RawSample] = []
    total = sum(len(videos) for videos in vocabulary.values())
    done = 0
    for sign, by_signer in vocabulary.items():
        for signer, video_path in sorted(by_signer.items()):
            result = extract_hand_landmarks(video_path, model_path=model_path)
            raw.append(RawSample(sign=sign, signer=signer, extraction=result, video_path=video_path))
            done += 1
            print(f"[{done}/{total}] {sign} (signer {signer}): {result.frame_count} frames", flush=True)
    return raw


def _build_samples(raw: Sequence[RawSample], normalize_fn: Callable[[HandExtractionResult], np.ndarray]) -> List[Sample]:
    """Aplica uma função de normalização aos dados brutos, sem re-extrair vídeo."""
    return [
        Sample(sign=r.sign, signer=r.signer, sequence=normalize_fn(r.extraction), video_path=r.video_path)
        for r in raw
    ]


def split_train_test(samples: Sequence[Sample]) -> Tuple[List[Sample], List[Sample]]:
    """Split único: treino = Articulador 1+3, teste = Articulador 2 (`dtw_prototipos.py` / Fase 0 LSAE)."""
    train = [s for s in samples if s.signer in SPLIT_TRAIN_SIGNERS]
    test = [s for s in samples if s.signer == SPLIT_TEST_SIGNER]
    return train, test


# ============================================================================
# V2 — normalização center-of-mass (adaptada de `dtw_prototipos.py::normalizar`)
# ============================================================================


def normalize_center_of_mass(result: HandExtractionResult) -> np.ndarray:
    """Variante experimental de `ml/features.py::normalize_hand_landmarks`.

    HIPÓTESE: `dtw_prototipos.py::normalizar()` centra cada frame pela MÉDIA
    de todos os pontos válidos de AMBAS as mãos juntas (`centro =
    validos.mean(axis=0)`) e escala pela norma média dos pontos centrados. O
    Ciclo 7 centra cada mão SEPARADAMENTE no próprio punho e escala pela
    distância punho→MCP daquela mão. A normalização por-mão descarta a
    posição relativa entre as duas mãos (cada uma vira seu próprio
    referencial); a center-of-mass preserva essa relação. Se parte do sinal
    estiver em ONDE uma mão está em relação à outra (comum em Libras — muitos
    sinais usam as duas mãos com papéis diferentes), esta normalização deveria
    ajudar.

    ADAPTAÇÃO ao layout de 128 features do Ciclo 7 (documentada, como pedido):
    o script original opera sobre um vetor (T, 126) já achatado (2 mãos fixas
    × 21 × 3, sem flag de presença — dataset legado sem essa informação).
    Aqui a mesma fórmula (subtrai a média de todos os pontos válidos, escala
    pela norma média dos pontos centrados) é aplicada sobre os PONTOS BRUTOS
    de cada frame (`HandDetection.points`, união de todas as mãos detectadas
    naquele frame) — matematicamente idêntica ao original quando as duas mãos
    estão presentes, e trivialmente correta quando só uma está (a "média de
    ambas as mãos" vira a média dos pontos daquela mão só, que é o único dado
    válido disponível; o script original faria o mesmo com sua própria
    definição de "válido" ali). Os flags de presença (índices 126/127) não
    existem no script original — não fazem parte do fator sendo testado — e
    são preservados sem alteração, exatamente como em `normalize_hand_landmarks`.

    Frame sem nenhuma mão detectada: fica zerado, igual à função de produção.
    """
    sequence = np.zeros((result.frame_count, VECTOR_SIZE), dtype=np.float32)
    for t, frame in enumerate(result.frames):
        all_points = [p for hand in frame.hands for p in hand.points]
        if not all_points:
            continue

        points = np.asarray(all_points, dtype=np.float32)  # (21 ou 42, 3)
        centro = points.mean(axis=0)
        centrado = points - centro
        escala = float(np.linalg.norm(centrado, axis=1).mean())
        normalizado = centrado / escala if escala > 1e-6 else centrado

        offset = 0
        for hand in frame.hands:
            n = len(hand.points)
            hand_vector = normalizado[offset : offset + n].reshape(-1)
            offset += n
            if hand.label == "Left":
                sequence[t, 0:63] = hand_vector
                sequence[t, 126] = 1.0
            elif hand.label == "Right":
                sequence[t, 63:126] = hand_vector
                sequence[t, 127] = 1.0
    return sequence


# ============================================================================
# V3 — reamostragem + DTW com banda de Sakoe-Chiba (adaptado de `dtw_prototipos.py`)
# ============================================================================


def resample_sequence(sequence: np.ndarray, length: int = RESAMPLE_LENGTH) -> np.ndarray:
    """Reamostra uma sequência (T, D) para `length` passos por interpolação linear.

    Mesma técnica de `dtw_prototipos.py::reamostrar()`: mapeia o eixo do
    tempo para [0,1] e interpola cada feature (coluna) independentemente.
    HIPÓTESE: junto com a banda de Sakoe-Chiba abaixo, reamostrar para um
    comprimento fixo evita que a banda (que limita |i-j|) corte alinhamentos
    válidos só porque duas execuções do mesmo sinal têm durações brutas muito
    diferentes — ao custo de descartar informação real de velocidade/duração.
    """
    t = len(sequence)
    if t == length:
        return sequence.astype(np.float32)
    if t == 0:
        return np.zeros((length, sequence.shape[1]), dtype=np.float32)
    origem = np.linspace(0.0, 1.0, t)
    destino = np.linspace(0.0, 1.0, length)
    return np.stack(
        [np.interp(destino, origem, sequence[:, c]) for c in range(sequence.shape[1])],
        axis=1,
    ).astype(np.float32)


def dtw_distance_banded(a: np.ndarray, b: np.ndarray, band: int = SAKOE_CHIBA_BAND) -> float:
    """Variante experimental de `ml/dtw.py::dtw_distance` com banda de Sakoe-Chiba.

    HIPÓTESE: limitar o alinhamento (célula (i,j) só é alcançável se
    |i-j| <= band) impede o DTW de "esticar" demais para compensar diferenças
    de ritmo entre sinalizantes — coisa que a versão exata e sem banda do
    Ciclo 7 permite livremente, e que pode estar aproximando sinais diferentes
    que só coincidem em algum trecho esticado. Adaptado de
    `dtw_prototipos.py::dtw()` (lá D=126, aqui D=128) — lógica idêntica,
    só o número de features de entrada muda.
    """
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return float("inf")

    custo = np.full((n + 1, m + 1), np.inf, dtype=np.float32)
    custo[0, 0] = 0.0
    for i in range(1, n + 1):
        inicio = max(1, i - band)
        fim = min(m, i + band)
        dif = b[inicio - 1 : fim] - a[i - 1]
        distancias = np.sqrt((dif * dif).sum(axis=1))
        for desloc, j in enumerate(range(inicio, fim + 1)):
            custo[i, j] = distancias[desloc] + min(
                custo[i - 1, j], custo[i, j - 1], custo[i - 1, j - 1]
            )
    return float(custo[n, m] / (n + m))


# ============================================================================
# Avaliação de split único (V1-V3) — `evaluate_leave_one_signer_out` de
# produção só sabe fazer LOSO 3-dobras; isto isola o fator "metodologia de split"
# ============================================================================


def _predict_generic(
    references: Sequence[Sample],
    query_sequence: np.ndarray,
    distance_fn: Callable[[np.ndarray, np.ndarray], float],
    k: int = 5,
) -> List[Tuple[str, float]]:
    """Mesma lógica de `ml/predict.py::predict`, parametrizada por `distance_fn`.

    Duplicada de propósito, não importada: `predict()` de produção é fixo em
    `dtw_distance` (exato, sem banda) — é exatamente o fator que V3 varia.
    Ver auto-crítica no relatório do Ciclo 9 sobre esta duplicação.
    """
    scored = sorted(
        ((distance_fn(query_sequence, ref.sequence), ref.sign) for ref in references),
        key=lambda pair: pair[0],
    )
    ranking: List[Tuple[str, float]] = []
    seen = set()
    for distance, sign in scored:
        if sign in seen:
            continue
        seen.add(sign)
        ranking.append((sign, distance))
        if len(ranking) >= k:
            break
    return ranking


def evaluate_single_split(
    train_samples: Sequence[Sample],
    test_samples: Sequence[Sample],
    distance_fn: Callable[[np.ndarray, np.ndarray], float] = dtw_distance,
    k: int = 5,
) -> Dict:
    """Split único (treino=Articulador 1+3, teste=Articulador 2).

    Mesmo split de `dtw_prototipos.py` / Fase 0 do LSAE. Isola o efeito da
    metodologia de avaliação: 1 dobra fixa (aqui) vs. a média de 3 dobras de
    `evaluate_leave_one_signer_out` (produção, V0).
    """
    correct1 = correct5 = 0
    n = len(test_samples)
    for query in test_samples:
        ranking = _predict_generic(train_samples, query.sequence, distance_fn, k=k)
        ranked_signs = [sign for sign, _ in ranking]
        correct1 += int(bool(ranked_signs) and ranked_signs[0] == query.sign)
        correct5 += int(query.sign in ranked_signs)
    return {
        "top1_accuracy": correct1 / n if n else 0.0,
        "top5_accuracy": correct5 / n if n else 0.0,
        "n_evaluated": n,
        "n_references": len(train_samples),
    }


# ============================================================================
# As 4 variantes — cada uma soma UMA mudança à anterior
# ============================================================================


@dataclass
class VariantResult:
    name: str
    description: str
    hypothesis: str
    top1: float
    top5: Optional[float]
    elapsed_s: float
    n_evaluated: int


def run_v0_baseline(raw: Sequence[RawSample]) -> VariantResult:
    """V0 = pipeline de produção do Ciclo 7, sem nenhuma mudança.

    `normalize_hand_landmarks` + `dtw_distance` + `evaluate_leave_one_signer_out`,
    todas de produção, inalteradas. Deve reproduzir 28,0%/49,3% (mesmos dados,
    mesmo código) — se não bater, é bug na extração deste experimento, não no
    fator sendo testado.
    """
    samples = _build_samples(raw, normalize_hand_landmarks)
    t0 = time.time()
    metrics = evaluate_leave_one_signer_out(samples)
    elapsed = time.time() - t0
    return VariantResult(
        name="V0",
        description="Baseline: pipeline de produção do Ciclo 7 (LOSO 3 dobras)",
        hypothesis="Confirma que esta extração reproduz o 28,0%/49,3% já documentado",
        top1=metrics["top1_accuracy"],
        top5=metrics["top5_accuracy"],
        elapsed_s=elapsed,
        n_evaluated=metrics["n_evaluated"],
    )


def run_v1_single_split(raw: Sequence[RawSample]) -> VariantResult:
    """V1 = V0, mas avaliação com split único em vez de LOSO 3 dobras."""
    samples = _build_samples(raw, normalize_hand_landmarks)
    train, test = split_train_test(samples)
    t0 = time.time()
    metrics = evaluate_single_split(train, test, distance_fn=dtw_distance)
    elapsed = time.time() - t0
    return VariantResult(
        name="V1",
        description="V0 + split único (treino=1+3, teste=2) em vez de LOSO 3 dobras",
        hypothesis="Isola o efeito da metodologia de split: 1 dobra fixa vs. média de 3",
        top1=metrics["top1_accuracy"],
        top5=metrics["top5_accuracy"],
        elapsed_s=elapsed,
        n_evaluated=metrics["n_evaluated"],
    )


def run_v2_center_of_mass(raw: Sequence[RawSample]) -> VariantResult:
    """V2 = V1 + normalização center-of-mass em vez de por-mão."""
    samples = _build_samples(raw, normalize_center_of_mass)
    train, test = split_train_test(samples)
    t0 = time.time()
    metrics = evaluate_single_split(train, test, distance_fn=dtw_distance)
    elapsed = time.time() - t0
    return VariantResult(
        name="V2",
        description="V1 + normalização center-of-mass (duas mãos juntas, não por-mão)",
        hypothesis="Centrar pelas duas mãos preserva a posição relativa entre elas",
        top1=metrics["top1_accuracy"],
        top5=metrics["top5_accuracy"],
        elapsed_s=elapsed,
        n_evaluated=metrics["n_evaluated"],
    )


def run_v3_banded_dtw(raw: Sequence[RawSample]) -> VariantResult:
    """V3 = V2 + DTW com banda de Sakoe-Chiba + reamostragem para comprimento fixo."""
    samples = _build_samples(raw, normalize_center_of_mass)
    resampled = [replace(s, sequence=resample_sequence(s.sequence)) for s in samples]
    train, test = split_train_test(resampled)

    def banded(a: np.ndarray, b: np.ndarray) -> float:
        return dtw_distance_banded(a, b, band=SAKOE_CHIBA_BAND)

    t0 = time.time()
    metrics = evaluate_single_split(train, test, distance_fn=banded)
    elapsed = time.time() - t0
    return VariantResult(
        name="V3",
        description=(
            f"V2 + DTW com banda Sakoe-Chiba (banda={SAKOE_CHIBA_BAND}) "
            f"+ reamostragem (comprimento={RESAMPLE_LENGTH})"
        ),
        hypothesis="Banda+reamostragem reduz o espaço de alinhamentos, evita 'esticar' demais",
        top1=metrics["top1_accuracy"],
        top5=metrics["top5_accuracy"],
        elapsed_s=elapsed,
        n_evaluated=metrics["n_evaluated"],
    )


# ============================================================================
# Orquestração
# ============================================================================


def print_table(results: Sequence[VariantResult]) -> None:
    print()
    print(f"{'Variante':<6} {'Top-1':>8} {'Top-5':>8} {'Tempo':>10}  Descrição")
    for r in results:
        top5 = f"{r.top5:.1%}" if r.top5 is not None else "—"
        print(f"{r.name:<6} {r.top1:>8.1%} {top5:>8} {r.elapsed_s:>9.1f}s  {r.description}")
    print()


def run_all(
    vocab_size: int = VOCAB_SIZE,
    videos_root: Path = DEFAULT_VLIBRASIL_ROOT,
    model_path: Optional[Path] = None,
) -> List[VariantResult]:
    """Extrai os dados brutos UMA VEZ e roda V0-V3 em sequência sobre eles."""
    print(f"Extraindo landmarks brutos ({vocab_size} sinais x 3 sinalizantes)...", flush=True)
    t0 = time.time()
    raw = load_raw_dataset(vocab_size, videos_root, model_path)
    print(f"  {len(raw)} amostras extraídas em {time.time() - t0:.0f}s", flush=True)

    results = [
        run_v0_baseline(raw),
        run_v1_single_split(raw),
        run_v2_center_of_mass(raw),
        run_v3_banded_dtw(raw),
    ]
    print_table(results)
    return results


if __name__ == "__main__":
    run_all()
