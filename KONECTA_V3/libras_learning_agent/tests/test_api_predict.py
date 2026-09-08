"""Testes reais do Ciclo 11 (POST /api/libras/predict) do Libras Learning Agent.

Sem mock do pipeline de visão: vídeos reais do V-LIBRASIL, extração real via
MediaPipe, DTW real. Mesmo espírito de `test_ml_training.py` (extração cara
feita uma vez, fixture `module`-scoped, vocabulário pequeno de 5 sinais) e de
`test_api_models.py` (SQLite temporário real por teste, `TestClient` sobe o
`app` de verdade).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import libras_learning_agent.api.app as api_app_module
from libras_learning_agent.api.app import app, get_session
from libras_learning_agent.core.config import Settings
from libras_learning_agent.database.db import Base
from libras_learning_agent.database.models import ModelVersion
from libras_learning_agent.ml.dataset import DEFAULT_VLIBRASIL_ROOT, Sample, discover_vocabulary, load_dataset
from libras_learning_agent.ml.training import build_model_version
from libras_learning_agent.vision.hand_landmarks import ensure_hand_landmarker_model

SMALL_VOCAB_SIZE = 5  # mesmo vocabulário pequeno do Ciclo 7 (5 sinais x 3 sinalizantes)


def _sqlite_url(path: Path) -> str:
    return "sqlite:///" + str(path).replace("\\", "/")


def _fail_if_called(*_args, **_kwargs):
    raise AssertionError("extract_hand_landmarks não deveria ter sido chamado aqui")


# --------------------------------------------------------------------- fixtures: dataset real ---


@pytest.fixture(scope="module")
def model_path() -> Path:
    return ensure_hand_landmarker_model()


@pytest.fixture(scope="module")
def small_vocabulary():
    return discover_vocabulary(DEFAULT_VLIBRASIL_ROOT, min_signs=SMALL_VOCAB_SIZE, max_signs=SMALL_VOCAB_SIZE)


@pytest.fixture(scope="module")
def small_samples(small_vocabulary, model_path) -> list[Sample]:
    """15 amostras reais (5 sinais x 3 sinalizantes), extraídas uma única vez e
    reaproveitadas por todos os testes deste arquivo — só as chamadas HTTP a
    /predict extraem vídeo de novo, de propósito (é o pipeline da própria
    rota sendo exercitado ponta a ponta, não um atalho).
    """
    samples = load_dataset(small_vocabulary, model_path=model_path)
    assert len(samples) == SMALL_VOCAB_SIZE * 3
    return samples


@pytest.fixture(scope="module")
def outside_vocab_video(small_vocabulary) -> Path:
    """Vídeo de um sinal FORA do vocabulário das referências — a consulta "totalmente alheia"."""
    wider = discover_vocabulary(
        DEFAULT_VLIBRASIL_ROOT, min_signs=SMALL_VOCAB_SIZE + 1, max_signs=SMALL_VOCAB_SIZE + 1
    )
    extra_signs = [s for s in wider if s not in small_vocabulary]
    assert extra_signs, "vocabulário maior não trouxe nenhum sinal fora do pequeno"
    return wider[extra_signs[0]]["1"]


# --------------------------------------------------------------------- fixtures: API/banco ---


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(_sqlite_url(tmp_path / "api_predict.db"), connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


@pytest.fixture
def client(session: Session):
    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_production_model(session: Session, tmp_path: Path, samples, *, version: str) -> ModelVersion:
    """Constrói um `ModelVersion` de verdade (`ml/training.build_model_version`,
    mesmo caminho do Ciclo 7) e promove pra "production" DIRETO no banco —
    escolha deliberada: a rota HTTP `POST /models/{id}/promote` já está
    coberta em `test_api_models.py`; aqui o que se testa é `/predict`, então
    ir direto ao banco mantém o teste focado e mais rápido.
    """
    settings = Settings(_env_file=None, models_dir=str(tmp_path / "models"))
    model = build_model_version(session, samples, {}, version=version, settings=settings)
    model.status = "production"
    session.add(model)
    session.commit()
    session.refresh(model)
    return model


def _upload(client: TestClient, video_path: Path, *, k: int | None = None, filename: str | None = None):
    content = video_path.read_bytes()
    params = {} if k is None else {"k": k}
    files = {"file": (filename or video_path.name, content, "video/mp4")}
    return client.post("/api/libras/predict", params=params, files=files)


# --------------------------------------------------------------------- 1: sem modelo em produção ---


def test_predict_without_production_model_returns_409(client: TestClient, small_vocabulary) -> None:
    video = next(iter(small_vocabulary.values()))["1"]
    response = _upload(client, video)
    assert response.status_code == 409
    assert "promov" in response.json()["detail"].lower()


# --------------------------------------------------------------------- 2: só "production" conta ---


def test_predict_ignores_evaluated_model_uses_only_production(
    session: Session, client: TestClient, tmp_path: Path, small_samples, small_vocabulary
) -> None:
    """A regra mais fácil de esquecer (mesma do Ciclo 8): só "production" conta,
    nunca "evaluated" mesmo que mais recente.

    Achado na revisão: a primeira versão deste teste criava o "evaluated"
    quebrado ANTES do "production" -- então "production" também era "o mais
    recente", e um bug real (usar `order_by(created_at.desc())` em vez de
    `where(status == "production")`) passaria batido por coincidência de
    ordem, não porque a regra estivesse certa. Confirmado ao vivo: substituí
    a query por `order_by(created_at.desc())` de propósito e este teste
    continuou passando -- só falhou depois de inverter a ordem de criação
    abaixo (o "evaluated" quebrado é criado por ÚLTIMO, então "mais recente"
    e "production" deixam de coincidir). O `ModelVersion` "evaluated" aponta
    pra um `.npz` que NÃO existe -- se a rota usasse ele por engano em vez do
    "production", a chamada quebraria (arquivo ausente), então este teste
    prova a escolha certa por construção, não só inspecionando o id devolvido.
    """
    production = _make_production_model(session, tmp_path, small_samples, version="model_production_v001")

    broken = ModelVersion(
        version="model_evaluated_broken",
        dataset_version="vlibrasil_subset_v1",
        signals_count=SMALL_VOCAB_SIZE,
        metrics={},
        status="evaluated",
        file_path=str(tmp_path / "does_not_exist" / "references.npz"),
    )
    session.add(broken)
    session.commit()

    video = next(iter(small_vocabulary.values()))["1"]
    response = _upload(client, video)
    assert response.status_code == 200
    body = response.json()
    assert body["model_version_id"] == production.id
    assert body["model_version"] == "model_production_v001"


# --------------------------------------------------------------------- 3: qualidade do ranking ---


def test_predict_same_sign_different_signer_ranks_well(
    monkeypatch: pytest.MonkeyPatch, session: Session, client: TestClient, tmp_path: Path, small_samples, small_vocabulary
) -> None:
    """Consulta que DEVERIA aparecer bem ranqueada: mesmo sinal, sinalizante
    FORA das referências (leave-one-signer-out, mesmo espírito do Ciclo 7).

    Também prova limpeza do arquivo temporário no caminho de SUCESSO (o
    caminho de erro é provado em `test_predict_invalid_video_content_...`).
    """
    references = [s for s in small_samples if s.signer in ("1", "2")]  # sinalizante 3 fica de fora
    model = _make_production_model(session, tmp_path, references, version="model_loso_v001")

    target_sign = sorted(small_vocabulary.keys())[0]
    query_video = small_vocabulary[target_sign]["3"]

    removed_paths: list[str] = []
    original_remove = api_app_module.os.remove

    def _spy_remove(path):
        assert api_app_module.os.path.exists(path), f"removendo algo que já não existe: {path}"
        removed_paths.append(path)
        original_remove(path)

    monkeypatch.setattr(api_app_module.os, "remove", _spy_remove)

    response = _upload(client, query_video)
    assert response.status_code == 200
    body = response.json()
    assert body["model_version_id"] == model.id
    assert body["frame_count"] > 0
    assert 0.0 <= body["detection_rate"] <= 1.0

    ranking = body["ranking"]
    assert 1 <= len(ranking) <= 5
    ranked_signs = [item["sign"] for item in ranking]
    assert target_sign in ranked_signs, (
        f"sinal correto {target_sign!r} nem apareceu no top-{len(ranking)}: {ranked_signs}"
    )
    position = ranked_signs.index(target_sign) + 1
    print(
        f"\n[Ciclo 11] consulta '{target_sign}' (sinalizante 3, fora das referências) "
        f"rankeada na posição {position}/{len(ranking)}. Ranking completo: {ranking}"
    )

    assert len(removed_paths) == 1, "arquivo temporário deveria ter sido removido exatamente uma vez"
    assert not api_app_module.os.path.exists(removed_paths[0]), "arquivo temporário ainda existe após a resposta"


def test_predict_unrelated_sign_returns_ranking_from_vocabulary_only(
    session: Session, client: TestClient, tmp_path: Path, small_samples, small_vocabulary, outside_vocab_video: Path
) -> None:
    """Consulta totalmente alheia ao vocabulário das referências: a rota
    responde normalmente (não é obrigada a "acertar" nada), o ranking só
    contém sinais que existem nas referências, ordenado por distância.
    """
    _make_production_model(session, tmp_path, small_samples, version="model_full_v001")

    response = _upload(client, outside_vocab_video)
    assert response.status_code == 200
    body = response.json()
    ranking = body["ranking"]
    assert len(ranking) == SMALL_VOCAB_SIZE  # k=5 default, vocabulário tem exatamente 5 sinais

    vocabulary_signs = set(small_vocabulary.keys())
    for item in ranking:
        assert item["sign"] in vocabulary_signs
        assert item["distance"] >= 0.0
    distances = [item["distance"] for item in ranking]
    assert distances == sorted(distances), "ranking deveria vir ordenado por distância"
    print(f"\n[Ciclo 11] consulta alheia ao vocabulário -> ranking: {ranking}")


# --------------------------------------------------------------------- 4: determinismo + k ---


def test_predict_is_deterministic_and_k_is_configurable(
    session: Session, client: TestClient, tmp_path: Path, small_samples, small_vocabulary
) -> None:
    _make_production_model(session, tmp_path, small_samples, version="model_det_v001")
    video = next(iter(small_vocabulary.values()))["2"]

    first = _upload(client, video)
    second = _upload(client, video)
    assert first.status_code == second.status_code == 200
    assert first.json()["ranking"] == second.json()["ranking"], (
        "duas chamadas com o mesmo vídeo deram rankings diferentes -- pipeline não é determinístico"
    )

    limited = _upload(client, video, k=2)
    assert limited.status_code == 200
    assert len(limited.json()["ranking"]) <= 2


# --------------------------------------------------------------------- 5: entrada inválida ---


def test_predict_wrong_extension_returns_400_without_calling_extraction(
    monkeypatch: pytest.MonkeyPatch, session: Session, client: TestClient, tmp_path: Path, small_samples
) -> None:
    _make_production_model(session, tmp_path, small_samples, version="model_ext_v001")
    monkeypatch.setattr(api_app_module, "extract_hand_landmarks", _fail_if_called)

    response = client.post("/api/libras/predict", files={"file": ("nota.txt", b"nao sou um video", "text/plain")})
    assert response.status_code == 400


def test_predict_oversized_upload_returns_413_without_calling_extraction(
    monkeypatch: pytest.MonkeyPatch, session: Session, client: TestClient, tmp_path: Path, small_samples
) -> None:
    _make_production_model(session, tmp_path, small_samples, version="model_size_v001")
    monkeypatch.setattr(api_app_module, "extract_hand_landmarks", _fail_if_called)

    big_content = b"0" * (api_app_module.MAX_UPLOAD_BYTES + 1)
    response = client.post("/api/libras/predict", files={"file": ("grande.mp4", big_content, "video/mp4")})
    assert response.status_code == 413


def test_predict_invalid_video_content_returns_400_and_cleans_temp_file(
    monkeypatch: pytest.MonkeyPatch, session: Session, client: TestClient, tmp_path: Path, small_samples
) -> None:
    """Upload que não é vídeo de verdade (extensão .mp4, conteúdo texto) -> 400
    claro (nunca 500), e o arquivo temporário some mesmo no caminho de erro.
    """
    _make_production_model(session, tmp_path, small_samples, version="model_invalid_v001")

    removed_paths: list[str] = []
    original_remove = api_app_module.os.remove

    def _spy_remove(path):
        assert api_app_module.os.path.exists(path), f"removendo algo que já não existe: {path}"
        removed_paths.append(path)
        original_remove(path)

    monkeypatch.setattr(api_app_module.os, "remove", _spy_remove)

    response = client.post(
        "/api/libras/predict", files={"file": ("falso.mp4", b"isto nao e um video de verdade", "video/mp4")}
    )
    assert response.status_code == 400
    assert "inv" in response.json()["detail"].lower()  # "Vídeo inválido: ..."

    assert len(removed_paths) == 1, "arquivo temporário deveria ter sido removido exatamente uma vez"
    assert not api_app_module.os.path.exists(removed_paths[0]), "arquivo temporário ainda existe após o erro"
