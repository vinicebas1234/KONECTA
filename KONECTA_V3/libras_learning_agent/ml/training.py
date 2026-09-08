"""O "treino" do Ciclo 7: avaliação cross-signer honesta + versionamento de modelo.

Não é treino no sentido de ajustar pesos — é DTW + kNN contra as próprias
amostras, abordagem já medida como muito superior a uma LSTM nesta escala de
dados (ver `KONECTA_V3/RECONHECIMENTO_RECOMENDACAO.md`, seção 5.1, e o
docstring de `libras_learning_agent/ml/__init__.py`).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from libras_learning_agent.core.config import Settings, get_settings
from libras_learning_agent.database.models import ModelVersion, TrainingRun
from libras_learning_agent.ml.dataset import Sample, save_references
from libras_learning_agent.ml.predict import predict


def leave_one_signer_out_splits(
    samples: Sequence[Sample],
) -> List[Tuple[str, List[Sample], List[Sample]]]:
    """Um split por sinalizante: `(sinalizante_testado, amostras_de_teste, referências)`.

    Exposta separadamente de `evaluate_leave_one_signer_out` de propósito: é
    exatamente aqui que vazamento de dado aconteceria — se uma amostra do
    sinalizante testado entrasse nas referências, a acurácia cross-signer
    ficaria artificialmente alta. `tests/test_ml_training.py` testa esta
    função diretamente por isso.
    """
    signers = sorted({s.signer for s in samples})
    return [
        (
            signer,
            [s for s in samples if s.signer == signer],
            [s for s in samples if s.signer != signer],
        )
        for signer in signers
    ]


def evaluate_leave_one_signer_out(samples: Sequence[Sample]) -> Dict:
    """Acurácia top-1/top-5 cross-signer: cada sinalizante testado só contra os outros dois.

    Para cada amostra de teste, `predict()` roda kNN por DTW contra as
    referências do fold (nunca do mesmo sinalizante) e devolve os 5 sinais
    mais próximos — top-1 e top-5 saem do mesmo ranking, sem custo adicional.
    """
    per_signer: Dict[str, Dict] = {}
    total_top1 = total_top5 = total_n = 0

    for signer, test_samples, reference_samples in leave_one_signer_out_splits(samples):
        correct1 = correct5 = 0
        for query in test_samples:
            ranking = predict(reference_samples, query.sequence, k=5)
            ranked_signs = [sign for sign, _ in ranking]
            correct1 += int(bool(ranked_signs) and ranked_signs[0] == query.sign)
            correct5 += int(query.sign in ranked_signs)

        n = len(test_samples)
        per_signer[signer] = {
            "top1_accuracy": correct1 / n if n else 0.0,
            "top5_accuracy": correct5 / n if n else 0.0,
            "n_samples": n,
            "n_references": len(reference_samples),
        }
        total_top1 += correct1
        total_top5 += correct5
        total_n += n

    return {
        "per_signer": per_signer,
        "top1_accuracy": total_top1 / total_n if total_n else 0.0,
        "top5_accuracy": total_top5 / total_n if total_n else 0.0,
        "n_evaluated": total_n,
        "n_signs": len({s.sign for s in samples}),
    }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_model_version(
    session: Session,
    samples: Sequence[Sample],
    eval_metrics: Dict,
    *,
    version: str,
    dataset_version: str = "vlibrasil_subset_v1",
    settings: Optional[Settings] = None,
) -> ModelVersion:
    """Salva as referências (todas as amostras, dos 3 sinalizantes) e registra `TrainingRun`+`ModelVersion`.

    `status="evaluated"`, nunca `"production"` — promoção é decisão humana
    futura, fora do escopo deste ciclo. `file_path` vive sob
    `settings.models_dir` (isolado de `KONECTA_V3/models/`, ver `core/config.py`).
    """
    settings = settings or get_settings()
    file_path = Path(settings.models_dir) / version / "references.npz"
    save_references(file_path, samples)

    now = _utcnow()
    session.add(
        TrainingRun(
            dataset_version=dataset_version,
            base_model="dtw_knn_prototype",
            status="completed",
            started_at=now,
            completed_at=now,
            metrics=eval_metrics,
        )
    )

    model_version = ModelVersion(
        version=version,
        dataset_version=dataset_version,
        signals_count=len({s.sign for s in samples}),
        metrics=eval_metrics,
        status="evaluated",
        file_path=str(file_path),
    )
    session.add(model_version)
    session.commit()
    session.refresh(model_version)
    return model_version
