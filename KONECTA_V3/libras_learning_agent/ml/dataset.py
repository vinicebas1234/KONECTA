"""Descoberta do vocabulário e carregamento do dataset V-LIBRASIL (UFPE).

Dataset bruto, fora de `KONECTA_V3` — este módulo só LÊ de lá, nunca escreve:

    C:\\KONECTA\\Datasets\\videos UFPE (V-LIBRASIL)\\data\\<Sinal>\\<Sinal>_Articulador{1,2,3}.mp4

3 sinalizantes fixos (Articulador1/2/3), nem todo sinal tem os 3 vídeos.
`discover_vocabulary` escolhe um subvocabulário pequeno e determinístico (ordem
alfabética das pastas), só com sinais que têm os 3 — evita buracos no split
cross-signer do Ciclo 7.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

from libras_learning_agent.ml.features import normalize_hand_landmarks
from libras_learning_agent.vision.hand_landmarks import extract_hand_landmarks

logger = logging.getLogger(__name__)

# Fora de KONECTA_V3 de propósito: dataset público bruto, não é código do
# projeto nem SIGNLAB. Só leitura — ver docstring do módulo.
DEFAULT_VLIBRASIL_ROOT = Path(r"C:\KONECTA\Datasets\videos UFPE (V-LIBRASIL)")
SIGNERS = ("1", "2", "3")  # Articulador1/2/3


@dataclass(frozen=True, eq=False)
class Sample:
    """Uma amostra rotulada: sinal + sinalizante + sequência normalizada (T, 128).

    `eq=False` de propósito: o campo `sequence` é `np.ndarray`, e o `__eq__`
    padrão de dataclass gerado por `eq=True` levantaria `ValueError` (array
    ambíguo) na primeira vez que alguém comparasse duas amostras ou usasse
    `in`/`set()` sobre uma lista delas. Comparação vira identidade de objeto,
    que é o que faz sentido aqui (compare `.sign`/`.signer` explicitamente
    quando precisar de igualdade por conteúdo).
    """

    sign: str
    signer: str  # "1", "2" ou "3"
    sequence: np.ndarray
    # None quando a amostra veio de um artefato salvo (ver training.save_references),
    # não de uma extração nova a partir do vídeo original.
    video_path: Optional[Path] = None


def discover_vocabulary(
    videos_root: Path, min_signs: int = 20, max_signs: int = 30
) -> Dict[str, Dict[str, Path]]:
    """Escolhe até `max_signs` sinais (ordem alfabética) com os 3 articuladores presentes.

    Determinístico: mesma entrada sempre devolve o mesmo vocabulário. Levanta
    erro se menos de `min_signs` sinais completos existirem — melhor falhar
    alto do que treinar/avaliar sobre um vocabulário menor que o pedido sem avisar.
    """
    data_dir = Path(videos_root) / "data"
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Diretório de dados do V-LIBRASIL não encontrado: {data_dir}")

    vocabulary: Dict[str, Dict[str, Path]] = {}
    sign_dirs = sorted((d for d in data_dir.iterdir() if d.is_dir()), key=lambda d: d.name)
    for sign_dir in sign_dirs:
        videos = {
            signer: sign_dir / f"{sign_dir.name}_Articulador{signer}.mp4" for signer in SIGNERS
        }
        if all(path.is_file() for path in videos.values()):
            vocabulary[sign_dir.name] = videos
        if len(vocabulary) >= max_signs:
            break

    if len(vocabulary) < min_signs:
        raise RuntimeError(
            f"Só {len(vocabulary)} sinais com os 3 articuladores encontrados em {data_dir} "
            f"(mínimo pedido: {min_signs})"
        )
    return vocabulary


def load_dataset(
    vocabulary: Dict[str, Dict[str, Path]], *, model_path: Optional[Path] = None
) -> List[Sample]:
    """Extrai (Ciclo 1) + normaliza (`ml/features.py`) todos os vídeos do vocabulário.

    Sequencial, de propósito: mesmo estilo do resto do Ciclo 1/vision — simples
    e correto. Para o volume real (dezenas de vídeos) o custo é dominado pelo
    MediaPipe por vídeo (segundos), documentado no relatório do Ciclo 7; quem
    quiser acelerar mais pode paralelizar por fora, sem mudar este contrato.
    """
    total = sum(len(videos) for videos in vocabulary.values())
    samples: List[Sample] = []
    done = 0
    t_start = time.time()
    for sign, by_signer in vocabulary.items():
        for signer, video_path in sorted(by_signer.items()):
            result = extract_hand_landmarks(video_path, model_path=model_path)
            sequence = normalize_hand_landmarks(result)
            samples.append(Sample(sign=sign, signer=signer, sequence=sequence, video_path=video_path))
            done += 1
            logger.info(
                "[%d/%d] %s (signer %s): %d frames, detection_rate=%.3f",
                done, total, sign, signer, result.frame_count, result.detection_rate,
            )
    logger.info("load_dataset: %d amostras em %.1fs", len(samples), time.time() - t_start)
    return samples


def save_references(file_path: Path, samples: Sequence[Sample]) -> None:
    """Salva todas as sequências normalizadas num único `.npz`.

    Formato escolhido: `.npz` com uma chave `seq_<i>` por amostra, não uma
    única matriz — T varia por amostra (sequência "ragged"), e o `.npz`
    guarda cada chave com sua própria forma sem precisar preencher com zeros
    (que disfarçaria "sinal curto" de "sinal com padding"). `signs`/`signers`
    ficam em arrays paralelos de string (sem `allow_pickle`).
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "signs": np.array([s.sign for s in samples]),
        "signers": np.array([s.signer for s in samples]),
    }
    for i, sample in enumerate(samples):
        payload[f"seq_{i}"] = sample.sequence.astype(np.float32)
    np.savez_compressed(file_path, **payload)


def load_references(file_path: Path) -> List[Sample]:
    """Lê de volta o que `save_references` gravou."""
    data = np.load(Path(file_path))
    signs, signers = data["signs"], data["signers"]
    return [
        Sample(sign=str(signs[i]), signer=str(signers[i]), sequence=data[f"seq_{i}"])
        for i in range(len(signs))
    ]
