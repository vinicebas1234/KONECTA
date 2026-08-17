"""Testes do leitor de export do SIGNLAB e da logica de estabilizacao do V1."""

import glob
import json
import zipfile

import joblib
import numpy as np
import pytest

from app_central.core.estabilizador import Estabilizador
from app_central.providers.export_signlab import (
    TAMANHO_VETOR,
    ExportInvalido,
    carregar_export,
)

MODELOS_SIGNLAB = sorted(glob.glob("C:/KONECTA/SIGNLAB/projects/*/models/*.joblib"))


class ModeloBobo:
    """Classificador de mentira, no nivel do modulo para o joblib serializar."""

    n_features_in_ = TAMANHO_VETOR

    def predict(self, x):
        return [0] * len(x)


def _bundle():
    return {
        "model": ModeloBobo(),
        "class_names": {0: "OI", 1: "TCHAU"},
        "feature_config": {"length": TAMANHO_VETOR},
    }


def _metadata(temporal=False, **extra):
    dados = {
        "app": "SIGNLAB",
        "version": "1.0.0",
        "experiment_id": 1,
        "model_type": "video" if temporal else "image",
        "model_file": "model.keras" if temporal else "model.joblib",
        "metrics": {"accuracy": 0.9},
        "classes": {"0": "OI", "1": "TCHAU"},
        "feature_config": {"length": TAMANHO_VETOR},
    }
    dados.update(extra)
    return dados


# ------------------------------------------------------------- export


def test_carrega_zip_exportado(tmp_path):
    """O formato que o SIGNLAB realmente entrega: um .zip por experimento."""
    modelo = tmp_path / "model.joblib"
    joblib.dump(_bundle(), modelo)
    zip_path = tmp_path / "signlab_experimento_1.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(modelo, "model.joblib")
        zf.writestr("metadata.json", json.dumps(_metadata()))

    export = carregar_export(zip_path)
    assert export.temporal is False
    assert export.nome_da_classe(0) == "OI"
    assert export.metricas["accuracy"] == 0.9


def test_carrega_pasta_descompactada(tmp_path):
    joblib.dump(_bundle(), tmp_path / "model.joblib")
    (tmp_path / "metadata.json").write_text(json.dumps(_metadata()), encoding="utf-8")
    assert carregar_export(tmp_path).nome_da_classe(1) == "TCHAU"


def test_carrega_joblib_cru(tmp_path):
    """Formato que ja circulava antes do export existir."""
    caminho = tmp_path / "exp_1.joblib"
    joblib.dump(_bundle(), caminho)
    assert carregar_export(caminho).nome_da_classe(0) == "OI"


def test_zip_corrompido_e_recusado(tmp_path):
    ruim = tmp_path / "ruim.zip"
    ruim.write_bytes(b"isto nao e um zip")
    with pytest.raises(ExportInvalido, match="zip"):
        carregar_export(ruim)


def test_zip_sem_modelo_e_recusado(tmp_path):
    zip_path = tmp_path / "vazio.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("metadata.json", json.dumps(_metadata()))
    with pytest.raises(ExportInvalido, match="nenhum model"):
        carregar_export(zip_path)


def test_temporal_sem_labels_e_recusado(tmp_path):
    """Sem labels a saida softmax viraria indice sem nome - pior que falhar."""
    (tmp_path / "model.keras").write_bytes(b"fake")
    (tmp_path / "metadata.json").write_text(
        json.dumps(_metadata(temporal=True)), encoding="utf-8"
    )
    with pytest.raises(ExportInvalido):
        carregar_export(tmp_path)


def test_layout_incompativel_e_recusado(tmp_path):
    bundle = _bundle()
    bundle["feature_config"] = {"length": 64}
    joblib.dump(bundle, tmp_path / "model.joblib")
    with pytest.raises(ExportInvalido, match="features"):
        carregar_export(tmp_path / "model.joblib")


def test_arquivo_inexistente():
    with pytest.raises(ExportInvalido, match="não encontrado"):
        carregar_export("C:/nao/existe.zip")


@pytest.mark.skipif(not MODELOS_SIGNLAB, reason="sem modelo real do SIGNLAB")
def test_modelo_real_do_signlab_carrega():
    export = carregar_export(MODELOS_SIGNLAB[0])
    assert export.temporal is False
    assert len(export.classes) >= 1


# ------------------------------------------------------------- estabilizador


def test_confianca_baixa_nao_confirma():
    e = Estabilizador(limiar_confianca=0.7, tempo_hold_s=0.0)
    assert e.avaliar("OI", 0.5, agora=0.0) is None


def test_precisa_segurar_para_confirmar():
    """Sem hold, a 15fps sairiam dezenas de palavras por segundo."""
    e = Estabilizador(limiar_confianca=0.7, tempo_hold_s=1.0)
    assert e.avaliar("OI", 0.9, agora=0.0) is None
    assert e.avaliar("OI", 0.9, agora=0.5) is None
    c = e.avaliar("OI", 0.9, agora=1.1)
    assert c is not None and c.texto == "OI"


def test_trocar_de_sinal_reinicia_a_contagem():
    e = Estabilizador(limiar_confianca=0.7, tempo_hold_s=1.0)
    e.avaliar("OI", 0.9, agora=0.0)
    e.avaliar("TCHAU", 0.9, agora=0.9)  # troca: recomeca
    assert e.avaliar("TCHAU", 0.9, agora=1.5) is None
    assert e.avaliar("TCHAU", 0.9, agora=2.0) is not None


def test_frame_ruim_no_meio_nao_zera_o_progresso():
    """Um frame fraco no meio de um sinal estavel nao pode obrigar a recomecar."""
    e = Estabilizador(limiar_confianca=0.7, tempo_hold_s=1.0)
    e.avaliar("OI", 0.9, agora=0.0)
    e.avaliar("", 0.0, agora=0.5)  # frame ruim
    assert e.avaliar("OI", 0.9, agora=1.1) is not None


def test_nao_repete_o_mesmo_sinal_seguidas_vezes():
    """Mao parada nao deve escrever a mesma palavra varias vezes."""
    e = Estabilizador(limiar_confianca=0.7, tempo_hold_s=0.5)
    assert e.avaliar("OI", 0.9, agora=0.0) is None
    assert e.avaliar("OI", 0.9, agora=0.6) is not None
    for t in (1.2, 1.8, 2.4):
        e.avaliar("OI", 0.9, agora=t)
    assert e.historico == ["OI"]


def test_maos_fora_de_quadro_permitem_repetir():
    """Tirar a mao e refazer o sinal e' intencao de repetir."""
    e = Estabilizador(limiar_confianca=0.7, tempo_hold_s=0.5)
    e.avaliar("OI", 0.9, agora=0.0)
    e.avaliar("OI", 0.9, agora=0.6)
    e.sem_maos()
    e.avaliar("OI", 0.9, agora=2.0)
    assert e.avaliar("OI", 0.9, agora=2.6) is not None
    assert e.historico == ["OI", "OI"]


def test_monta_o_texto_acumulado():
    """Como no V1, confirmar exige um segundo frame com a mesma predicao."""
    e = Estabilizador(limiar_confianca=0.7, tempo_hold_s=0.0)
    for palavra in ("EU", "QUERER", "AGUA"):
        e.avaliar(palavra, 0.9, agora=0.0)  # vira candidato
        e.avaliar(palavra, 0.9, agora=0.1)  # confirma
    assert e.texto_acumulado() == "EU QUERER AGUA"


def test_limpar_zera_tudo():
    e = Estabilizador(tempo_hold_s=0.0)
    e.avaliar("OI", 0.9, agora=0.0)
    e.limpar()
    assert e.historico == []
