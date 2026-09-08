"""Testes reais do Ciclo 1 (visão computacional) do Libras Learning Agent.

Nada aqui é simulado: sobe um `HandLandmarker` de verdade (baixa o `.task`
oficial do MediaPipe se preciso), processa `KONECTA_V3/test_video.mp4` frame a
frame de verdade via OpenCV, e persiste em um SQLite temporário real.

Rodar de dentro da venv própria do LLA — ver o relatório do Ciclo 1 para o
comando exato usado.

O teste mais importante do arquivo é `test_determinism...`: é o desenhado
especificamente para pegar a regressão descrita em
`KONECTA_V3/ANALISE_E_PLANO_GAUNTLET.md` (seção 5.10) — `vision_lab/landmarks.py`
que nunca chamou o MediaPipe e devolvia `np.random.randn(228)`. Um extrator
real e determinístico dá o mesmo resultado nas duas rodadas; ruído aleatório
nunca daria. Ver o relatório do Ciclo 1 para a prova (rodou passando, depois
rodou falhando de propósito com `np.random`, depois desfez).

Nota sobre `test_video.mp4`: é ruído puro (frames com "Frame N" escrito sobre
estática colorida — confirmado abrindo os frames), não um vídeo de Libras.
`detection_rate` real medido é 0.0 em todos os 30 frames — o que é o
comportamento CORRETO de um detector real (a versão antiga, fake, não tinha
esse conceito: sempre "detectava" porque simplesmente inventava números).
Por isso `test_structure...` também vira uma checagem de regressão: um stub
que fabrica landmarks incondicionalmente NUNCA chegaria a `detection_rate == 0`
neste vídeo.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from libras_learning_agent.core.config import Settings
from libras_learning_agent.database.db import Base
from libras_learning_agent.database.models import LandmarkSample, Signal
from libras_learning_agent.vision.hand_landmarks import (
    ensure_hand_landmarker_model,
    extract_hand_landmarks,
)
from libras_learning_agent.vision.storage import load_landmarks_file, save_hand_extraction

PACKAGE_DIR = Path(__file__).resolve().parents[1]  # libras_learning_agent/
REPO_ROOT = PACKAGE_DIR.parent  # KONECTA_V3/
TEST_VIDEO = REPO_ROOT / "test_video.mp4"

# Faixa real observada rodando o mesmo HandLandmarker (mesmo modelo, mesma
# API) contra uma foto real de mão (não faz parte deste vídeo de teste, que é
# ruído puro — ver docstring do módulo): x em [0.116, 0.923], y em
# [0.081, 0.897], score 0.93. Documentado no relatório do Ciclo 1 com o output
# real colado. Aqui damos margem para landmarks parcialmente fora do quadro,
# que a própria documentação do MediaPipe permite.
PLAUSIBLE_XY_RANGE = (-0.5, 1.5)
PLAUSIBLE_Z_RANGE = (-2.0, 2.0)


def _sqlite_url(path: Path) -> str:
    return "sqlite:///" + str(path).replace("\\", "/")


@pytest.fixture(scope="module")
def model_path() -> Path:
    return ensure_hand_landmarker_model()


@pytest.fixture(scope="module")
def extraction_result(model_path: Path):
    assert TEST_VIDEO.is_file(), f"vídeo de teste ausente: {TEST_VIDEO}"
    return extract_hand_landmarks(TEST_VIDEO, model_path=model_path)


# --------------------------------------------------------------------- 1 ---


def test_determinism_two_real_runs_match(model_path: Path) -> None:
    """O teste mais importante do ciclo — ver docstring do módulo.

    Roda a extração duas vezes sobre o mesmo vídeo real e compara frame a
    frame. Prova gravada no relatório do Ciclo 1: este teste passa com a
    implementação real e FALHA quando a extração é trocada por
    `np.random.randn(...)`.
    """
    r1 = extract_hand_landmarks(TEST_VIDEO, model_path=model_path)
    r2 = extract_hand_landmarks(TEST_VIDEO, model_path=model_path)

    assert r1.frame_count == r2.frame_count == 30
    assert r1.fps == r2.fps
    assert r1.detection_rate == r2.detection_rate

    for f1, f2 in zip(r1.frames, r2.frames):
        assert f1.frame_id == f2.frame_id
        assert f1.timestamp_ms == f2.timestamp_ms
        assert len(f1.hands) == len(f2.hands), (
            f"frame {f1.frame_id}: número de mãos detectadas divergiu entre "
            f"rodadas ({len(f1.hands)} vs {len(f2.hands)}) — extração não é "
            f"determinística"
        )
        for h1, h2 in zip(f1.hands, f2.hands):
            assert h1.label == h2.label
            pts1, pts2 = np.array(h1.points), np.array(h2.points)
            assert np.allclose(pts1, pts2, atol=1e-5), (
                f"frame {f1.frame_id}: pontos divergem entre as duas rodadas "
                f"além da tolerância numérica — não é um extrator determinístico"
            )


# --------------------------------------------------------------------- 2 ---


def test_structure_frames_and_landmark_shape(extraction_result) -> None:
    """Estrutura do resultado + faixa plausível de x/y/z quando há detecção.

    `test_video.mp4` é ruído puro (ver docstring do módulo): `detection_rate`
    real medido é 0.0 — comportamento correto de um detector de verdade, e já
    uma checagem de regressão por si: um stub que fabrica landmarks
    incondicionalmente teria `detection_rate == 1.0` aqui, nunca `0.0`.
    """
    assert extraction_result.frame_count == 30
    assert extraction_result.fps == 30.0
    assert extraction_result.detection_rate == 0.0  # ruído puro: nenhuma mão de verdade

    assert len(extraction_result.frames) == extraction_result.frame_count
    for i, frame in enumerate(extraction_result.frames):
        assert frame.frame_id == i
        assert frame.timestamp_ms >= 0
        assert isinstance(frame.hands, tuple)
        assert frame.detected == (len(frame.hands) > 0)

        for hand in frame.hands:
            assert hand.label in ("Left", "Right")
            assert 0.0 <= hand.score <= 1.0
            assert len(hand.points) == 21, "HandLandmarker sempre devolve 21 pontos por mão"
            for x, y, z in hand.points:
                assert PLAUSIBLE_XY_RANGE[0] <= x <= PLAUSIBLE_XY_RANGE[1]
                assert PLAUSIBLE_XY_RANGE[0] <= y <= PLAUSIBLE_XY_RANGE[1]
                assert PLAUSIBLE_Z_RANGE[0] <= z <= PLAUSIBLE_Z_RANGE[1]

    # timestamps estritamente crescentes (exigência do RunningMode.VIDEO)
    timestamps = [f.timestamp_ms for f in extraction_result.frames]
    assert timestamps == sorted(set(timestamps)), "timestamps devem ser estritamente crescentes"


# --------------------------------------------------------------------- 3 ---


def test_persist_and_read_back_landmark_sample(tmp_path: Path, extraction_result) -> None:
    """Extrai (fixture), persiste e confirma que dá pra ler de volta.

    `LandmarkSample.signal_id` é FK não-nula — cria um `Signal` de teste
    primeiro, mesmo padrão usado em `tests/test_foundation.py` (Ciclo 0).
    """
    settings = Settings(
        _env_file=None,
        data_dir=str(tmp_path / "data"),
        database_url=_sqlite_url(tmp_path / "ciclo1_test.db"),
    )
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    try:
        with Session(engine) as session:
            signal = Signal(concept="TESTE_CICLO1")
            session.add(signal)
            session.commit()
            session.refresh(signal)
            signal_id = signal.id  # capturado dentro da sessão: fora dela o objeto expira

            sample = save_hand_extraction(
                extraction_result, signal_id=signal_id, session=session, settings=settings
            )
            sample_id = sample.id
            file_path = Path(sample.file_path)

            assert sample_id
            assert file_path.is_file(), f"arquivo de landmarks não foi criado: {file_path}"
            assert file_path.parent == (tmp_path / "data" / "landmarks")

            payload = load_landmarks_file(file_path)
            assert payload["frame_count"] == extraction_result.frame_count
            assert len(payload["frames"]) == extraction_result.frame_count
            assert payload["detection_rate"] == extraction_result.detection_rate

        # sessão nova: prova que a linha sobrevive fora do escopo que a criou
        with Session(engine) as session2:
            row = session2.get(LandmarkSample, sample_id)
            assert row is not None
            assert row.signal_id == signal_id
            assert row.frame_count == extraction_result.frame_count
            assert row.fps == extraction_result.fps
            assert row.quality_score == extraction_result.detection_rate
            assert row.file_path == str(file_path)
    finally:
        engine.dispose()


# --------------------------------------------------------------------- 4 ---


def test_missing_video_raises_clear_error(model_path: Path) -> None:
    """Vídeo inexistente precisa dar erro claro, não travar/silenciar."""
    caminho_falso = REPO_ROOT / "video_que_nao_existe_de_verdade.mp4"
    assert not caminho_falso.exists()

    with pytest.raises(FileNotFoundError, match="não encontrado"):
        extract_hand_landmarks(caminho_falso, model_path=model_path)
