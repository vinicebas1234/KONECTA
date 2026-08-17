"""Processo isolado que prevê sinais dinâmicos com o modelo temporal do SIGNLAB.

Existe por um motivo medido: **TensorFlow não carrega no mesmo processo que o
PyQt5** nesta máquina. A DLL falha na inicialização —
``ImportError: DLL load failed while importing _pywrap_tensorflow_internal`` —
e, pior, o MediaPipe passa a falhar junto, porque ele importa TensorFlow quando
o pacote está presente. O resultado é o app rodando sem reconhecer nada.

Comprovado: com TF instalado, o app processa 0 frames; sem TF, processa 655 em
25s. Pré-importar na thread principal não resolve — a incompatibilidade é do
processo, não da thread.

Por isso a divisão:

    processo da GUI   MediaPipe extrai landmarks (rápido, sem TF)
    este processo     Keras carrega a rede e prevê a janela

Protocolo pela entrada/saída padrão, uma requisição por vez:

    entrada:  8 bytes (uint64) com o nº de frames + frames × 128 float32
    saída:    uma linha JSON {"texto": "...", "confianca": 0.0} ou {"erro": "..."}
"""

from __future__ import annotations

import json
import struct
import sys
import warnings

import numpy as np

warnings.filterwarnings("ignore")

TAMANHO_VETOR = 128
_modelo = None
_labels: list = []


def _carregar(caminho: str):
    global _modelo, _labels
    if _modelo is None:
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
        from app_central.providers.export_signlab import carregar_export

        export = carregar_export(caminho)
        if not export.temporal:
            raise RuntimeError("modelo não é temporal; use o caminho in-process")
        _modelo = export.modelo
        _labels = export.labels
    return _modelo


def main() -> int:
    if len(sys.argv) < 2:
        return 2
    caminho = sys.argv[1]

    entrada = sys.stdin.buffer
    saida = sys.stdout

    while True:
        cabecalho = entrada.read(8)
        if len(cabecalho) < 8:
            return 0  # pai fechou: encerra limpo

        (n_frames,) = struct.unpack("<Q", cabecalho)
        dados = entrada.read(n_frames * TAMANHO_VETOR * 4)
        if len(dados) < n_frames * TAMANHO_VETOR * 4:
            return 0

        try:
            janela = np.frombuffer(dados, dtype=np.float32).reshape(1, n_frames, TAMANHO_VETOR)
            modelo = _carregar(caminho)
            probabilidades = modelo.predict(janela, verbose=0)[0]
            indice = int(np.argmax(probabilidades))
            nome = _labels[indice] if indice < len(_labels) else str(indice)
            resposta = {"texto": nome, "confianca": float(probabilidades[indice])}
        except Exception as erro:
            resposta = {"erro": f"{type(erro).__name__}: {erro}"}

        saida.write(json.dumps(resposta, ensure_ascii=False) + "\n")
        saida.flush()


if __name__ == "__main__":
    sys.exit(main())
