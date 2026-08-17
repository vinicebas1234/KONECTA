"""Testes de processo do app_central.

Rodam o app de verdade num subprocesso, com camera falsa. Ficam fora do pytest
in-process de proposito: falhas de GUI no PyQt5 podem abortar o interpretador, e
um teste in-process morreria junto com o runner em vez de reportar falha.

Cobrem o que teste unitario nao alcanca:
- o app sobe e processa frames de ponta a ponta;
- sob carga, nao acumula fila nem processa frames velhos.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
TIMEOUT_S = 240  # o teste dos dois fluxos espera a fala sintetizada


def _rodar(roteiro: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    ambiente = {**os.environ, **(extra_env or {})}
    return subprocess.run(
        [sys.executable, str(RAIZ / "tests" / roteiro)],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_S,
        env=ambiente,
    )


@pytest.mark.slow
def test_app_sobe_e_processa_frames():
    """O app precisa sobreviver e processar frames — nao so' abrir a janela."""
    r = _rodar("smoke_app_central.py")
    assert "SMOKE_OK" in r.stdout, f"saida:\n{r.stdout}\n{r.stderr}"
    assert r.returncode == 0


@pytest.mark.slow
def test_nao_acumula_fila_sob_carga():
    """Camera mais rapida que o pipeline nao pode gerar atraso crescente.

    Falha se a contrapressao de _process_frame for removida.
    """
    r = _rodar("probe_backpressure.py")
    assert "PROBE_OK" in r.stdout, f"saida:\n{r.stdout}\n{r.stderr}"
    assert r.returncode == 0


@pytest.mark.slow
def test_dois_fluxos_no_mesmo_app():
    """Camera→sinal→videochamada e audio→texto→avatar, juntos.

    O audio nao e' simulado: o sintetizador do Windows fala e o loopback captura.
    Pulado quando nao ha saida de audio disponivel (CI sem placa de som).
    """
    r = _rodar("smoke_dois_fluxos.py", extra_env={"KONECTA_AUDIO_ATIVO": "true"})
    if "nenhuma fala foi transcrita" in r.stdout:
        pytest.skip("sem áudio capturável neste ambiente")
    assert "DOIS_FLUXOS_OK" in r.stdout, f"saida:\n{r.stdout}\n{r.stderr}"
    assert r.returncode == 0


@pytest.mark.slow
def test_latencia_reportada_bate_com_a_real():
    """A latencia mostrada tem de incluir a espera em fila, nao so' o pipeline."""
    r = _rodar("probe_latencia.py")
    assert "LATENCIA_OK" in r.stdout, f"saida:\n{r.stdout}\n{r.stderr}"
    assert r.returncode == 0
