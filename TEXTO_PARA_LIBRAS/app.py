"""Texto para Libras: digite um texto — ou deixe o áudio do PC — virar sinal."""

import json
import socket
import subprocess
import sys
import threading
from pathlib import Path

import uvicorn
from PyQt5.QtCore import QThread, QUrl, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from server import PORTA
from server import app as servidor

RAIZ = Path(__file__).parent
LOG = RAIZ / "logs" / "audio.log"


def porta_ocupada() -> bool:
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", PORTA)) == 0


def iniciar_servidor() -> None:
    """Sobe o servidor embutido, a menos que já haja um na porta."""
    if porta_ocupada():
        return
    threading.Thread(
        target=uvicorn.run,
        args=(servidor,),
        kwargs={"host": "127.0.0.1", "port": PORTA, "log_level": "warning"},
        daemon=True,
    ).start()


class Escuta(QThread):
    """Roda a transcrição do áudio do PC num processo à parte.

    Fica separado do processo da GUI de propósito: o Whisper segura a CPU por
    centenas de ms por vez e travaria a animação do avatar se dividisse o GIL.
    O script publica em POST /publicar sozinho — aqui só lemos o log dele.
    """

    estado = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.processo = None

    def run(self) -> None:
        self.estado.emit("carregando modelo de voz…")
        self.processo = subprocess.Popen(
            [sys.executable, "-u", str(RAIZ / "transcricao_tempo_real.py")],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(RAIZ),
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        LOG.parent.mkdir(exist_ok=True)
        with open(LOG, "w", encoding="utf-8") as log:
            for linha in self.processo.stdout:
                log.write(linha)
                log.flush()
                self.estado.emit(linha.rstrip())
        codigo = self.processo.wait()
        self.estado.emit(f"[escuta] processo encerrou (codigo {codigo})")

    def parar(self) -> None:
        if self.processo and self.processo.poll() is None:
            self.processo.terminate()


class JanelaAvatar(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Texto para Libras")
        self.resize(900, 760)

        self.navegador = QWebEngineView()
        self.navegador.loadFinished.connect(self._pagina_carregada)

        self.entrada = QLineEdit()
        self.entrada.setPlaceholderText("carregando avatar…")
        self.entrada.returnPressed.connect(self.sinalizar)
        self.entrada.setEnabled(False)

        self.botao = QPushButton("Sinalizar")
        self.botao.clicked.connect(self.sinalizar)
        self.botao.setEnabled(False)

        self.audio_label = QLabel("Áudio do PC: iniciando…")
        self.audio_label.setStyleSheet("color: gray;")

        barra = QHBoxLayout()
        barra.addWidget(self.entrada)
        barra.addWidget(self.botao)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addLayout(barra)
        layout.addWidget(self.navegador)
        layout.addWidget(self.audio_label)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.navegador.load(QUrl(f"http://127.0.0.1:{PORTA}/"))

        self.escuta = Escuta()
        self.escuta.estado.connect(self._estado_audio)
        self.escuta.start()

    def _pagina_carregada(self, ok: bool) -> None:
        self.entrada.setPlaceholderText(
            "Digite o texto e pressione Enter…" if ok else "erro ao carregar a página"
        )
        self.entrada.setEnabled(ok)
        self.botao.setEnabled(ok)
        if ok:
            self.entrada.setFocus()

    def _estado_audio(self, linha: str) -> None:
        if "[modelo] pronto" in linha:
            texto = "ouvindo o áudio do computador"
        elif "[modelo] carregando" in linha or "carregando modelo" in linha:
            texto = "carregando modelo de voz… (demora na 1ª vez)"
        elif linha.startswith("[captura]"):
            texto = linha.replace("[captura] usando loopback de:", "capturando de:")
        elif linha.startswith("[legenda]"):
            texto = linha.replace("[legenda]", "ouvi:")
        else:
            return
        self.audio_label.setText(f"Áudio do PC: {texto}")

    def sinalizar(self) -> None:
        texto = self.entrada.text().strip()
        if not texto:
            return
        # traduzir() enfileira sozinho se o avatar ainda não terminou de carregar.
        self.navegador.page().runJavaScript(f"window.traduzir({json.dumps(texto)})")
        self.entrada.selectAll()

    def closeEvent(self, evento) -> None:
        self.escuta.parar()
        evento.accept()


def main() -> None:
    iniciar_servidor()
    aplicacao = QApplication(sys.argv)
    janela = JanelaAvatar()
    janela.show()
    sys.exit(aplicacao.exec_())


if __name__ == "__main__":
    main()
