"""Testes reais do Ciclo 13 (visão computacional — pose) do Libras Learning Agent.

Nada aqui é simulado: sobe um `PoseLandmarker` de verdade (baixa o `.task`
oficial do MediaPipe se preciso) e processa um vídeo REAL do V-LIBRASIL (UFPE)
frame a frame de verdade via OpenCV — não `KONECTA_V3/test_video.mp4`, que é
ruído puro (confirmado no Ciclo 1: "Frame N" escrito sobre estática colorida,
sem nenhuma pessoa). Ali `detection_rate` de pose também daria 0.0, o que não
provaria nada sobre o extrator. Aqui usamos
`Abacaxi_Articulador1.mp4` (mesmo vídeo já usado em `tests/test_ml_training.py`
do Ciclo 7/9): uma pessoa real sinalizando, corpo visível.

Dataset bruto, fora de `KONECTA_V3` — mesmo padrão de `ml/dataset.py`
(`DEFAULT_VLIBRASIL_ROOT`), só leitura:
    C:\\KONECTA\\Datasets\\videos UFPE (V-LIBRASIL)\\data\\<Sinal>\\<Sinal>_Articulador{1,2,3}.mp4
Este teste NÃO importa de `ml/dataset.py` de propósito — o extrator de pose é
isolado do pipeline de treino (ver docstring de `vision/pose_landmarks.py`).

O teste mais importante do arquivo é `test_determinism...`: mesmo espírito do
Ciclo 1 (`test_vision_hand_landmarks.py`) — pega a mesma classe de regressão
que `vision_lab/landmarks.py` tinha (`extract` devolvia `np.random.randn(...)`
em vez de rodar o MediaPipe de verdade). Um extrator real e determinístico dá
o mesmo resultado nas duas rodadas; ruído aleatório nunca daria. Prova (rodou
passando, depois com `np.random` de propósito — falhou —, depois desfez)
documentada no relatório do Ciclo 13.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from libras_learning_agent.vision.pose_landmarks import (
    ensure_pose_landmarker_model,
    extract_pose_landmarks,
)

# Fora de KONECTA_V3 de propósito, mesmo dataset bruto usado pelos Ciclos 7/9
# (ver docstring do módulo). Se não existir nesta máquina, os testes que
# dependem dele são pulados (`pytest.skip`) em vez de falhar.
VLIBRASIL_ROOT = Path(r"C:\KONECTA\Datasets\videos UFPE (V-LIBRASIL)")
TEST_VIDEO = VLIBRASIL_ROOT / "data" / "Abacaxi" / "Abacaxi_Articulador1.mp4"

# Faixa plausível para x/y/z normalizados de pose. Mais larga que a de mãos
# (Ciclo 1) de propósito: PoseLandmarker sempre estima os 33 pontos, mesmo
# quando pernas/pés estão fora do quadro (câmera enquadrando só tronco+braços,
# caso comum nos vídeos "Articulador" do V-LIBRASIL) — o modelo extrapola a
# posição com visibility/presence baixos em vez de omitir o ponto. Faixa real
# medida rodando contra Abacaxi_Articulador1.mp4 (172 frames, detection_rate
# 1.0): x em [0.311, 0.735], y em [0.237, 2.078] (pernas fora do quadro
# abaixo), z em [-1.174, 0.808]. Damos margem sobre o observado.
PLAUSIBLE_XY_RANGE = (-1.0, 3.0)
PLAUSIBLE_Z_RANGE = (-3.0, 3.0)
POSE_LANDMARK_COUNT = 33  # padrão fixo do MediaPipe Pose


def _skip_se_dataset_ausente() -> None:
    if not TEST_VIDEO.is_file():
        pytest.skip(f"dataset V-LIBRASIL ausente nesta máquina: {TEST_VIDEO}")


@pytest.fixture(scope="module")
def model_path() -> Path:
    return ensure_pose_landmarker_model()


@pytest.fixture(scope="module")
def extraction_result(model_path: Path):
    _skip_se_dataset_ausente()
    return extract_pose_landmarks(TEST_VIDEO, model_path=model_path)


# --------------------------------------------------------------------- 1 ---


def test_determinism_two_real_runs_match(model_path: Path) -> None:
    """O teste mais importante do ciclo — ver docstring do módulo.

    Roda a extração duas vezes sobre o mesmo vídeo real e compara frame a
    frame. Um extrator que inventasse números (`np.random.randn`) nunca
    passaria aqui.
    """
    _skip_se_dataset_ausente()
    r1 = extract_pose_landmarks(TEST_VIDEO, model_path=model_path)
    r2 = extract_pose_landmarks(TEST_VIDEO, model_path=model_path)

    assert r1.frame_count == r2.frame_count
    assert r1.fps == r2.fps
    assert r1.detection_rate == r2.detection_rate

    for f1, f2 in zip(r1.frames, r2.frames):
        assert f1.frame_id == f2.frame_id
        assert f1.timestamp_ms == f2.timestamp_ms
        assert len(f1.poses) == len(f2.poses), (
            f"frame {f1.frame_id}: número de poses detectadas divergiu entre "
            f"rodadas ({len(f1.poses)} vs {len(f2.poses)}) — extração não é "
            f"determinística"
        )
        for p1, p2 in zip(f1.poses, f2.poses):
            pts1, pts2 = np.array(p1.points), np.array(p2.points)
            assert np.allclose(pts1, pts2, atol=1e-5), (
                f"frame {f1.frame_id}: pontos divergem entre as duas rodadas "
                f"além da tolerância numérica — não é um extrator determinístico"
            )
            vis1, vis2 = np.array(p1.visibility), np.array(p2.visibility)
            pres1, pres2 = np.array(p1.presence), np.array(p2.presence)
            assert np.allclose(vis1, vis2, atol=1e-5)
            assert np.allclose(pres1, pres2, atol=1e-5)


# --------------------------------------------------------------------- 2 ---


def test_structure_frames_and_landmark_shape(extraction_result) -> None:
    """Estrutura do resultado + faixa plausível de x/y/z/visibility/presence.

    Vídeo real do V-LIBRASIL: espera-se `detection_rate` alto (pessoa visível
    o vídeo inteiro) — bem diferente do 0.0 medido no Ciclo 1 contra o vídeo
    de ruído. Documentado com o valor real no relatório do Ciclo 13.
    """
    assert extraction_result.frame_count > 0
    assert extraction_result.fps > 0
    assert extraction_result.detection_rate > 0.0, (
        "vídeo real com pessoa visível deveria ter pose detectada em pelo "
        "menos alguns frames — detection_rate 0.0 aqui seria sinal de "
        "extrator quebrado ou stub"
    )

    assert len(extraction_result.frames) == extraction_result.frame_count
    for i, frame in enumerate(extraction_result.frames):
        assert frame.frame_id == i
        assert frame.timestamp_ms >= 0
        assert isinstance(frame.poses, tuple)
        assert frame.detected == (len(frame.poses) > 0)
        assert len(frame.poses) <= 1, "num_poses=1: no máximo 1 pessoa por frame"

        for pose in frame.poses:
            assert len(pose.points) == POSE_LANDMARK_COUNT
            assert len(pose.visibility) == POSE_LANDMARK_COUNT
            assert len(pose.presence) == POSE_LANDMARK_COUNT
            assert len(pose.landmark_index) == POSE_LANDMARK_COUNT
            assert tuple(pose.landmark_index) == tuple(range(POSE_LANDMARK_COUNT))

            for x, y, z in pose.points:
                assert PLAUSIBLE_XY_RANGE[0] <= x <= PLAUSIBLE_XY_RANGE[1]
                assert PLAUSIBLE_XY_RANGE[0] <= y <= PLAUSIBLE_XY_RANGE[1]
                assert PLAUSIBLE_Z_RANGE[0] <= z <= PLAUSIBLE_Z_RANGE[1]
            for v in pose.visibility:
                assert 0.0 <= v <= 1.0
            for p in pose.presence:
                assert 0.0 <= p <= 1.0

    # timestamps estritamente crescentes (exigência do RunningMode.VIDEO)
    timestamps = [f.timestamp_ms for f in extraction_result.frames]
    assert timestamps == sorted(set(timestamps)), "timestamps devem ser estritamente crescentes"


# --------------------------------------------------------------------- 3 ---


def test_missing_video_raises_clear_error(model_path: Path) -> None:
    """Vídeo inexistente precisa dar erro claro, não travar/silenciar."""
    caminho_falso = VLIBRASIL_ROOT / "data" / "sinal_que_nao_existe_de_verdade.mp4"
    assert not caminho_falso.exists()

    with pytest.raises(FileNotFoundError, match="não encontrado"):
        extract_pose_landmarks(caminho_falso, model_path=model_path)
