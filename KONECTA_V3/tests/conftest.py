"""Fixtures e mocks compartilhados da suíte de testes do app_central.

Garante que a raiz do projeto esteja no ``sys.path`` para que o pacote
``app_central.*`` seja importável independente do diretório de execução.
"""

# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,unused-argument,C1803,too-few-public-methods,redefined-outer-name,no-member,no-name-in-module

import os
import sys
from pathlib import Path

import numpy as np
import pytest

# Cada janela de teste subiria um Chromium para o avatar embutido. A suite
# cria dezenas delas: pesado e instavel. O avatar nao e' o que os testes cobrem.
os.environ.setdefault("KONECTA_SEM_AVATAR", "1")
# A trava de instancia unica existe para o usuario nao abrir duas janelas
# disputando a camera. Nos testes ela faria cada subprocesso encerrar sem
# testar nada sempre que o app estivesse aberto.
os.environ.setdefault("KONECTA_SEM_TRAVA", "1")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True, scope="session")
def _sem_rede_de_verdade():
    """Impede que a checagem de motores abra sockets reais.

    Ao subir, a janela pergunta a cada motor se ele responde. O motor de
    texto→Libras faz isso batendo em 127.0.0.1:8300, que nao esta no ar durante
    os testes. Cada tentativa deixa uma operacao pendente no Proactor do
    Windows e, somadas as dezenas de janelas que a suite cria, o processo do
    pytest nao encerrava ao fim — a suite completa passava e depois travava.

    Teste nao deve depender de rede: aqui a checagem responde 'indisponivel'
    sem tocar em socket.
    """
    from app_central.providers.http_texto_sinais import TextoParaSinaisHTTP

    original = TextoParaSinaisHTTP.disponivel

    async def _sem_socket(self):
        return False

    TextoParaSinaisHTTP.disponivel = _sem_socket
    yield
    TextoParaSinaisHTTP.disponivel = original


@pytest.fixture
def sample_frame() -> np.ndarray:
    """Frame BGR sintético de 640x480."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def small_frame() -> np.ndarray:
    """Frame pequeno (barato) para testes de codificação."""
    return np.zeros((48, 64, 3), dtype=np.uint8)


@pytest.fixture
def pipeline_config() -> dict:
    """Configuração padrão usada para instanciar o pipeline."""
    return {
        "konecta_model_path": "models/v1",
        "claude_api_key": None,
        "claude_model": "claude-3-5-sonnet-20241022",
    }


@pytest.fixture
def fake_classifier_proba():
    """Classifier com ``predict_proba`` e ``classes_`` (caminho de proba)."""

    class _FakeClassifier:
        classes_ = np.array(["B", "OLA"])

        def predict_proba(self, features):
            return np.array([[0.2, 0.8]])

        def predict(self, features):
            return np.array(["OLA"])

    return _FakeClassifier()


@pytest.fixture
def fake_classifier_predict():
    """Classifier somente com ``predict`` (sem proba)."""

    class _FakeClassifier:
        def predict(self, features):
            return np.array(["OLA"])

    return _FakeClassifier()


@pytest.fixture
def fake_hand_landmarks():
    """21 landmarks MediaPipe-like (x, y, z) para montar o resultado de mão."""

    class _Point:
        def __init__(self, x, y, z):
            self.x = x
            self.y = y
            self.z = z

    return [
        _Point(i / 21.0, (i % 5) / 5.0, 0.01 * i) for i in range(21)
    ]


@pytest.fixture
def fake_hands(fake_hand_landmarks):
    """Detector MediaPipe fake que sempre encontra uma mão."""

    class _Hand:
        def __init__(self, landmarks):
            self.landmark = landmarks

    class _Results:
        def __init__(self, hand):
            self.multi_hand_landmarks = [hand] if hand is not None else None

    class _FakeHands:
        def __init__(self):
            self._landmarks = fake_hand_landmarks
            self._present = True
            self.closed = False

        def process(self, frame_rgb):
            hand = _Hand(self._landmarks) if self._present else None
            return _Results(hand)

        def close(self):
            self.closed = True

    return _FakeHands()
