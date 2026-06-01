#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SISTEMA DE RECONHECIMENTO DE LIBRAS — TCC                     ║
║        Visão Computacional + Machine Learning + Interface (Tkinter)        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Melhorias aplicadas:
- Detecção robusta de TensorFlow (múltiplas tentativas + instalação automática)
- Download automático de hand_landmarker.task com progresso e validação
- Arquitetura LSTM dinâmica aprimorada (3 camadas BiLSTM + BatchNorm)
- Data augmentation para sequências dinâmicas
- Feedback visual de treino (progresso, métricas por época, ETA e gráfico)
- Validações, normalização aprimorada, logs detalhados e modo debug
"""

# ══════════════════════════════════════════════════════════════════════════════
# IMPORTAÇÕES
# ══════════════════════════════════════════════════════════════════════════════

import hashlib
import importlib
import os
import pickle
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import ttk, messagebox, scrolledtext

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MATPLOTLIB_DISPONIVEL = True
except Exception:
    MATPLOTLIB_DISPONIVEL = False


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES (PASTA BASE DO PROJETO)
# ══════════════════════════════════════════════════════════════════════════════

BASE_DIR = Path(os.environ.get("LIBRAS_BASE_DIR", Path(__file__).resolve().parent)).resolve()

DIR_DADOS = BASE_DIR / "dados_libras"
DIR_ESTATICOS = DIR_DADOS / "estaticos"
DIR_DINAMICOS = DIR_DADOS / "dinamicos"
DIR_MODELOS = BASE_DIR / "modelos"

for d in (DIR_DADOS, DIR_ESTATICOS, DIR_DINAMICOS, DIR_MODELOS):
    d.mkdir(parents=True, exist_ok=True)

# MediaPipe
MP_MAX_HANDS = 2
MP_DET_CONF = 0.7
MP_TRK_CONF = 0.5

# Sequências (dinâmico)
SEQUENCE_LENGTH = 30
MIN_DYNAMIC_FRAMES = 8

# Câmera
CAM_INDEX = 0
CAM_WIDTH = 640
CAM_HEIGHT = 480

# Features
FEATURES_PER_HAND = 21 * 3  # 63
TOTAL_FEATURES = FEATURES_PER_HAND * MP_MAX_HANDS  # 126

# Hand Landmarker
HAND_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
HAND_LANDMARKER_FILE = DIR_MODELOS / "hand_landmarker.task"
HAND_LANDMARKER_MIN_BYTES = 1_000_000
DOWNLOAD_CHUNK_SIZE = 256 * 1024

# Tema (Catppuccin Mocha)
COR_BG = "#1e1e2e"
COR_BG2 = "#313244"
COR_BG3 = "#45475a"
COR_FG = "#cdd6f4"
COR_ACCENT = "#89b4fa"
COR_GREEN = "#a6e3a1"
COR_RED = "#f38ba8"
COR_YELLOW = "#f9e2af"
COR_LAVENDER = "#b4befe"
COR_PEACH = "#fab387"


# ══════════════════════════════════════════════════════════════════════════════
# TENSORFLOW: DETECÇÃO E INSTALAÇÃO AUTOMÁTICA
# ══════════════════════════════════════════════════════════════════════════════

tf = None
TF_DISPONIVEL = False
TF_STATUS_MSG = "TensorFlow ainda não verificado"


def _tentar_importar_tensorflow(max_tentativas=3, atraso=0.5):
    """Tenta importar TensorFlow em múltiplas tentativas."""
    global tf

    ultimo_erro = None
    for tentativa in range(1, max_tentativas + 1):
        try:
            importlib.invalidate_caches()
            tf_local = importlib.import_module("tensorflow")
            _ = tf_local.keras.models.Sequential
            _ = tf_local.keras.layers.LSTM
            _ = tf_local.keras.callbacks.EarlyStopping
            tf = tf_local
            versao = getattr(tf, "__version__", "desconhecida")
            return True, f"✅ TensorFlow disponível (v{versao})"
        except Exception as exc:
            ultimo_erro = exc
            time.sleep(atraso)

    msg_erro = str(ultimo_erro) if ultimo_erro else "erro desconhecido"
    return False, f"❌ TensorFlow não disponível: {msg_erro}"


def verificar_tensorflow():
    global TF_DISPONIVEL, TF_STATUS_MSG
    TF_DISPONIVEL, TF_STATUS_MSG = _tentar_importar_tensorflow(max_tentativas=3)
    return TF_DISPONIVEL, TF_STATUS_MSG


def instalar_tensorflow(log_fn=None):
    """Instala TensorFlow via pip no Python atual e revalida import."""
    def _log(m):
        if log_fn:
            log_fn(m)

    _log("📦 Iniciando instalação do TensorFlow via pip...")
    cmd = [sys.executable, "-m", "pip", "install", "tensorflow", "--upgrade"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            return False, f"❌ Falha ao instalar TensorFlow.\n{err[:1200]}"

        ok, status = verificar_tensorflow()
        if ok:
            _log("✅ TensorFlow instalado com sucesso.")
            return True, status
        return False, f"⚠ TensorFlow instalado, mas import falhou: {status}"
    except Exception as exc:
        return False, f"❌ Erro inesperado ao instalar TensorFlow: {exc}"


verificar_tensorflow()


# ══════════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS GERAIS
# ══════════════════════════════════════════════════════════════════════════════

def agora_str():
    return datetime.now().strftime("%H:%M:%S")


def timestamp_arquivo():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_log(log_fn, msg):
    if log_fn:
        try:
            log_fn(msg)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# HAND LANDMARKER: DOWNLOAD + VALIDAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

def validar_hand_landmarker(path_task):
    """Valida se o arquivo existe, tamanho mínimo e se abre no MediaPipe."""
    path_task = Path(path_task)

    if not path_task.exists():
        return False, "Arquivo não existe"

    tamanho = path_task.stat().st_size
    if tamanho < HAND_LANDMARKER_MIN_BYTES:
        return False, f"Arquivo muito pequeno ({tamanho} bytes)"

    try:
        base_options = python.BaseOptions(model_asset_path=str(path_task))
        options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=1)
        tester = vision.HandLandmarker.create_from_options(options)
        tester.close()
        return True, f"OK ({tamanho} bytes)"
    except Exception as exc:
        return False, f"Falha ao abrir modelo no MediaPipe: {exc}"


def baixar_hand_landmarker(path_task, progress_cb=None, log_fn=None):
    """Baixa o hand_landmarker.task com barra de progresso e hash SHA256."""
    path_task = Path(path_task)
    path_task.parent.mkdir(parents=True, exist_ok=True)

    _safe_log(log_fn, "⬇ Iniciando download do hand_landmarker.task...")

    req = urllib.request.Request(HAND_LANDMARKER_URL, headers={"User-Agent": "Mozilla/5.0"})
    sha = hashlib.sha256()

    tmp_fd, tmp_path = tempfile.mkstemp(prefix="hand_landmarker_", suffix=".part", dir=str(path_task.parent))
    os.close(tmp_fd)

    baixados = 0
    total = 0
    t0 = time.time()

    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(tmp_path, "wb") as out:
            content_length = resp.headers.get("Content-Length")
            total = int(content_length) if content_length and content_length.isdigit() else 0

            while True:
                chunk = resp.read(DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                out.write(chunk)
                sha.update(chunk)
                baixados += len(chunk)

                if progress_cb:
                    elapsed = max(time.time() - t0, 1e-6)
                    velocidade = baixados / elapsed
                    pct = (baixados / total * 100.0) if total > 0 else 0.0
                    progress_cb(baixados, total, pct, velocidade)

        os.replace(tmp_path, path_task)
    except urllib.error.URLError as exc:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise RuntimeError(f"Erro de rede ao baixar hand_landmarker.task: {exc}")
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    digest = sha.hexdigest()
    _safe_log(log_fn, f"🔐 SHA256 do arquivo baixado: {digest}")

    ok, detalhe = validar_hand_landmarker(path_task)
    if not ok:
        try:
            path_task.unlink(missing_ok=True)
        except Exception:
            pass
        raise RuntimeError(f"Arquivo baixado inválido: {detalhe}")

    _safe_log(log_fn, f"✅ hand_landmarker.task pronto ({detalhe})")
    return {"bytes": baixados, "total": total, "sha256": digest}


def garantir_hand_landmarker(path_task, progress_cb=None, log_fn=None):
    """Garante que o modelo existe; baixa automaticamente se necessário."""
    ok, detalhe = validar_hand_landmarker(path_task)
    if ok:
        _safe_log(log_fn, f"✅ Modelo hand_landmarker já disponível ({detalhe})")
        return "ok"

    _safe_log(log_fn, f"⚠ Modelo ausente/inválido: {detalhe}")
    baixar_hand_landmarker(path_task, progress_cb=progress_cb, log_fn=log_fn)
    return "baixado"


# ══════════════════════════════════════════════════════════════════════════════
# DETECTOR DE MÃOS (MediaPipe)
# ══════════════════════════════════════════════════════════════════════════════

class DetectorMaos:
    """Detector de mãos e extrator de features (landmarks normalizados)."""

    def __init__(self, model_path=None, debug=False, log_fn=None):
        self.debug = bool(debug)
        self.log_fn = log_fn
        self.model_path = str(model_path or HAND_LANDMARKER_FILE)

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Modelo não encontrado: {self.model_path}. "
                f"Faça download para {DIR_MODELOS}"
            )

        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=MP_MAX_HANDS,
            min_hand_detection_confidence=MP_DET_CONF,
            min_tracking_confidence=MP_TRK_CONF,
        )
        self.detector = vision.HandLandmarker.create_from_options(options)

        self.mp_hands = mp.tasks.vision.HandLandmarksConnections
        self.mp_draw = mp.tasks.vision.drawing_utils
        self.mp_style = mp.tasks.vision.drawing_styles

    def _debug(self, msg):
        if self.debug:
            _safe_log(self.log_fn, f"[DEBUG Detector] {msg}")

    def processar(self, frame_bgr):
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        return self.detector.detect(mp_image)

    def desenhar(self, frame_bgr, result):
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        annotated = frame_rgb.copy()

        if result.hand_landmarks:
            for hand_landmarks in result.hand_landmarks:
                self.mp_draw.draw_landmarks(
                    annotated,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_style.get_default_hand_landmarks_style(),
                    self.mp_style.get_default_hand_connections_style(),
                )

        return cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)

    @staticmethod
    def _normalizar_mao(pts):
        """Normalização robusta: centraliza no pulso e escala pela distância palma."""
        pts = pts.astype(np.float32).copy()
        center = pts[0].copy()
        pts -= center

        # Escala por distância entre pulso(0) e base dedo médio(9)
        ref = np.linalg.norm(pts[9] - pts[0])
        if ref < 1e-6:
            ref = np.max(np.abs(pts))
        if ref < 1e-6:
            ref = 1.0
        pts /= float(ref)

        # Clamping para robustez
        pts = np.clip(pts, -3.0, 3.0)
        return pts

    def extrair_features(self, result):
        """Retorna vetor 126 (2 mãos). Se não houver mão: zeros."""
        feats = np.zeros(TOTAL_FEATURES, dtype=np.float32)

        if not result.hand_landmarks:
            return feats

        for idx, hand in enumerate(result.hand_landmarks):
            if idx >= MP_MAX_HANDS:
                break
            pts = np.array([[lm.x, lm.y, lm.z] for lm in hand], dtype=np.float32)
            pts = self._normalizar_mao(pts)

            start = idx * FEATURES_PER_HAND
            end = start + FEATURES_PER_HAND
            feats[start:end] = pts.flatten()

        return feats

    def liberar(self):
        try:
            self.detector.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# GERENCIADOR DE DADOS
# ══════════════════════════════════════════════════════════════════════════════

class GerenciadorDados:
    """Cria pastas, salva amostras e carrega dataset híbrido (local + público)."""

    def __init__(self):
        for d in [BASE_DIR, DIR_DADOS, DIR_ESTATICOS, DIR_DINAMICOS, DIR_MODELOS]:
            os.makedirs(d, exist_ok=True)

    def _pasta_tipo(self, tipo):
        return DIR_ESTATICOS if tipo == "estatico" else DIR_DINAMICOS

    def _pasta_classe(self, tipo, rotulo):
        return os.path.join(self._pasta_tipo(tipo), rotulo)

    def _pasta_origem(self, tipo, rotulo, origem):
        pasta = os.path.join(self._pasta_classe(tipo, rotulo), origem)
        os.makedirs(pasta, exist_ok=True)
        return pasta

    def garantir_classe(self, tipo, rotulo):
        pasta = self._pasta_classe(tipo, rotulo)
        os.makedirs(pasta, exist_ok=True)
        return pasta

    def _proximo_indice(self, pasta, prefixo):
        nums = []
        for nome in os.listdir(pasta):
            if nome.endswith(".npy") and nome.startswith(prefixo):
                base = nome[:-4]
                try:
                    nums.append(int(base.split("_")[-1]))
                except ValueError:
                    continue
        return (max(nums) + 1) if nums else 0

    def salvar_estatico(self, rotulo, features):
        pasta = self._pasta_origem("estatico", rotulo, "local")
        idx = self._proximo_indice(pasta, "local")
        np.save(os.path.join(pasta, f"local_{idx:04d}.npy"), np.array(features, dtype=np.float32))

    def salvar_dinamico(self, rotulo, sequencia):
        pasta = self._pasta_origem("dinamico", rotulo, "local")
        idx = self._proximo_indice(pasta, "local")
        np.save(os.path.join(pasta, f"local_{idx:04d}.npy"), np.array(sequencia, dtype=np.float32))

    def _detectar_origem_arquivo(self, caminho_arquivo):
        pasta_pai = os.path.basename(os.path.dirname(caminho_arquivo)).lower()
        nome = os.path.basename(caminho_arquivo).lower()

        if pasta_pai == "local" or nome.startswith("local_"):
            return "local"
        if pasta_pai == "public" or nome.startswith("public_"):
            return "public"
        return "local"

    def _listar_arquivos_npy(self, pasta_classe):
        arquivos = []

        for nome in sorted(os.listdir(pasta_classe)):
            caminho = os.path.join(pasta_classe, nome)
            if os.path.isfile(caminho) and nome.endswith(".npy"):
                arquivos.append(caminho)

        for sub in ("local", "public"):
            subpasta = os.path.join(pasta_classe, sub)
            if not os.path.isdir(subpasta):
                continue
            for nome in sorted(os.listdir(subpasta)):
                caminho = os.path.join(subpasta, nome)
                if os.path.isfile(caminho) and nome.endswith(".npy"):
                    arquivos.append(caminho)

        return arquivos

    def _carregar_por_tipo(self, tipo):
        base = self._pasta_tipo(tipo)
        X, y, meta = [], [], []

        if not os.path.exists(base):
            return np.array(X, dtype=object), np.array(y), meta

        for rotulo in sorted(os.listdir(base)):
            pasta_classe = os.path.join(base, rotulo)
            if not os.path.isdir(pasta_classe):
                continue

            for caminho in self._listar_arquivos_npy(pasta_classe):
                try:
                    arr = np.load(caminho, allow_pickle=False)
                except Exception:
                    continue

                origem = self._detectar_origem_arquivo(caminho)
                X.append(arr)
                y.append(rotulo)
                meta.append({"rotulo": rotulo, "origem": origem, "arquivo": caminho})

        return np.array(X, dtype=object), np.array(y), meta

    def carregar_estaticos(self):
        return self._carregar_por_tipo("estatico")

    def carregar_dinamicos(self):
        return self._carregar_por_tipo("dinamico")

    def listar_classes(self):
        out = {"estatico": {}, "dinamico": {}}
        for tipo in ("estatico", "dinamico"):
            base = self._pasta_tipo(tipo)
            if not os.path.exists(base):
                continue

            for rotulo in sorted(os.listdir(base)):
                pasta = os.path.join(base, rotulo)
                if not os.path.isdir(pasta):
                    continue
                out[tipo][rotulo] = len(self._listar_arquivos_npy(pasta))
        return out

    def deletar_classe(self, tipo, rotulo):
        import shutil
        pasta = self._pasta_classe(tipo, rotulo)
        if os.path.exists(pasta):
            shutil.rmtree(pasta)


# ══════════════════════════════════════════════════════════════════════════════
# GERENCIADOR DE MODELOS
# ══════════════════════════════════════════════════════════════════════════════

class GerenciadorModelos:
    """Treino, inferência e persistência dos modelos estático/dinâmico."""

    def __init__(self):
        self.modelo_estatico = None
        self.encoder_estatico = None

        self.modelo_dinamico = None
        self.encoder_dinamico = None
        self.norm_media_din = None
        self.norm_std_din = None

        self._carregar_estatico()
        self._carregar_dinamico()

    # ──────────────────────────────────────────────────────────────────────────
    # UTIL
    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _normalizar_rotulos_prioritarios(rotulos):
        if not rotulos:
            return set()
        if isinstance(rotulos, str):
            itens = rotulos.replace(";", ",").split(",")
        else:
            itens = list(rotulos)
        return {str(item).strip().upper() for item in itens if str(item).strip()}

    @staticmethod
    def _validar_dataset(y):
        cont = Counter(y)
        if not cont:
            return "❌ Nenhuma amostra encontrada."
        if len(cont) < 2:
            return "❌ É preciso ter pelo menos 2 classes diferentes para treinar."

        menores = [rot for rot, qtd in cont.items() if qtd < 2]
        if menores:
            return (
                "❌ Cada classe precisa de pelo menos 2 amostras. Ajuste: "
                + ", ".join(f"{rot} ({cont[rot]})" for rot in sorted(menores))
            )
        return None

    @staticmethod
    def _calcular_pesos_amostras(y, meta, rotulos_prioritarios=None, peso_local=3.0, reforco_local_padrao=1.15):
        prioridades = GerenciadorModelos._normalizar_rotulos_prioritarios(rotulos_prioritarios)
        pesos = []

        for rotulo, info in zip(y, meta):
            origem = str(info.get("origem", "public")).lower()
            peso = 1.0

            if origem == "local":
                peso *= float(reforco_local_padrao)
                if rotulo.upper() in prioridades:
                    peso *= float(peso_local)

            pesos.append(peso)

        return np.array(pesos, dtype=np.float32), prioridades

    @staticmethod
    def _resumo_origens(meta):
        cont = Counter(str(item.get("origem", "desconhecida")).lower() for item in meta)
        partes = [f"{origem}: {qtd}" for origem, qtd in sorted(cont.items())]
        return ", ".join(partes) if partes else "sem origem"

    @staticmethod
    def _pad_or_crop_sequence(seq, target_len=SEQUENCE_LENGTH):
        seq = np.asarray(seq, dtype=np.float32)
        if seq.ndim != 2:
            raise ValueError("Sequência dinâmica inválida (esperado 2D).")
        if seq.shape[1] != TOTAL_FEATURES:
            raise ValueError(f"Sequência dinâmica com {seq.shape[1]} features (esperado {TOTAL_FEATURES}).")

        n = seq.shape[0]
        if n == target_len:
            return seq
        if n > target_len:
            return seq[-target_len:]

        # Padding com último frame (ou zeros se vazio)
        if n == 0:
            return np.zeros((target_len, TOTAL_FEATURES), dtype=np.float32)
        pad_count = target_len - n
        pad_frame = seq[-1:]
        pad = np.repeat(pad_frame, pad_count, axis=0)
        return np.concatenate([seq, pad], axis=0)

    @staticmethod
    def _validar_sequencias_dinamicas(X, y, meta, log=None):
        x_ok, y_ok, m_ok = [], [], []
        descartadas = 0

        for seq, rot, info in zip(X, y, meta):
            try:
                arr = np.asarray(seq, dtype=np.float32)
                if arr.ndim != 2:
                    descartadas += 1
                    continue
                if arr.shape[1] != TOTAL_FEATURES:
                    descartadas += 1
                    continue
                if arr.shape[0] < MIN_DYNAMIC_FRAMES:
                    descartadas += 1
                    continue

                arr = GerenciadorModelos._pad_or_crop_sequence(arr, SEQUENCE_LENGTH)
                x_ok.append(arr)
                y_ok.append(rot)
                m_ok.append(info)
            except Exception:
                descartadas += 1

        if log:
            log(f"✅ Sequências válidas: {len(x_ok)} | ❌ descartadas: {descartadas}")

        return np.array(x_ok, dtype=np.float32), np.array(y_ok), m_ok

    @staticmethod
    def _normalizar_dinamico_train_test(Xtr, Xte):
        media = Xtr.mean(axis=(0, 1), keepdims=True)
        std = Xtr.std(axis=(0, 1), keepdims=True)
        std = np.where(std < 1e-6, 1.0, std)

        Xtr_n = (Xtr - media) / std
        Xte_n = (Xte - media) / std

        return Xtr_n.astype(np.float32), Xte_n.astype(np.float32), media.astype(np.float32), std.astype(np.float32)

    @staticmethod
    def _aplicar_norm(seq, media, std):
        if media is None or std is None:
            return seq
        return ((seq - media.squeeze(0).squeeze(0)) / std.squeeze(0).squeeze(0)).astype(np.float32)

    @staticmethod
    def _espelhar_horizontal(seq):
        out = seq.copy()
        for hand_idx in range(MP_MAX_HANDS):
            start = hand_idx * FEATURES_PER_HAND
            x_idx = np.arange(start, start + FEATURES_PER_HAND, 3)
            out[:, x_idx] *= -1.0
        return out

    @staticmethod
    def _rotacionar_xy(seq, ang_deg):
        out = seq.copy()
        ang = np.deg2rad(ang_deg)
        c, s = np.cos(ang), np.sin(ang)

        for hand_idx in range(MP_MAX_HANDS):
            start = hand_idx * FEATURES_PER_HAND
            x_idx = np.arange(start, start + FEATURES_PER_HAND, 3)
            y_idx = np.arange(start + 1, start + FEATURES_PER_HAND, 3)

            x = out[:, x_idx]
            y = out[:, y_idx]
            out[:, x_idx] = x * c - y * s
            out[:, y_idx] = x * s + y * c

        return out

    @staticmethod
    def _variacao_temporal(seq, fator):
        n, f = seq.shape
        novo_n = max(MIN_DYNAMIC_FRAMES, int(round(n * fator)))
        t_old = np.linspace(0.0, 1.0, n)
        t_new = np.linspace(0.0, 1.0, novo_n)

        out = np.empty((novo_n, f), dtype=np.float32)
        for i in range(f):
            out[:, i] = np.interp(t_new, t_old, seq[:, i])

        return GerenciadorModelos._pad_or_crop_sequence(out, SEQUENCE_LENGTH)

    @staticmethod
    def _augmentar_uma_sequencia(seq):
        out = seq.copy().astype(np.float32)

        # 1) Ruído gaussiano leve
        ruido = np.random.normal(loc=0.0, scale=0.01, size=out.shape).astype(np.float32)
        out = out + ruido

        # 2) Variação temporal
        fator = float(np.random.uniform(0.9, 1.1))
        out = GerenciadorModelos._variacao_temporal(out, fator)

        # 3) Espelhamento horizontal (50%)
        if np.random.rand() < 0.5:
            out = GerenciadorModelos._espelhar_horizontal(out)

        # 4) Pequena rotação
        ang = float(np.random.uniform(-8.0, 8.0))
        out = GerenciadorModelos._rotacionar_xy(out, ang)

        return out.astype(np.float32)

    @staticmethod
    def _aumentar_dataset_dinamico(X, y, w, fator=1):
        if fator <= 0:
            return X, y, w

        X_aug = [*X]
        y_aug = [*y]
        w_aug = [*w]

        for seq, rot, peso in zip(X, y, w):
            for _ in range(fator):
                X_aug.append(GerenciadorModelos._augmentar_uma_sequencia(seq))
                y_aug.append(rot)
                w_aug.append(float(peso) * 0.9)

        return np.array(X_aug, dtype=np.float32), np.array(y_aug), np.array(w_aug, dtype=np.float32)

    # ──────────────────────────────────────────────────────────────────────────
    # ESTÁTICO (RandomForest)
    # ──────────────────────────────────────────────────────────────────────────
    def treinar_estatico(self, X, y, meta, rotulos_prioritarios=None, peso_local=3.0, log=None):
        if len(X) == 0:
            return "❌ Nenhuma amostra estática encontrada."

        erro = self._validar_dataset(y)
        if erro:
            return erro

        X = np.asarray(X, dtype=np.float32)
        if X.ndim != 2 or X.shape[1] != TOTAL_FEATURES:
            return f"❌ Formato inválido para estático. Esperado (N, {TOTAL_FEATURES})."

        pesos, prioridades = self._calcular_pesos_amostras(y, meta, rotulos_prioritarios, peso_local)
        enc = LabelEncoder()
        y_enc = enc.fit_transform(y)

        Xtr, Xte, ytr, yte, wtr, _, _, _ = train_test_split(
            X, y_enc, pesos, meta, test_size=0.2, random_state=42, stratify=y_enc
        )

        if log:
            log("🔄 Treinando RandomForest (estático)...")
            log(f"📚 Dataset híbrido: {self._resumo_origens(meta)}")
            log(
                f"🎯 Sinais locais priorizados: {', '.join(sorted(prioridades)) if prioridades else '(nenhum)'}"
                f" | peso extra: {peso_local:.2f}x"
            )

        mdl = RandomForestClassifier(n_estimators=300, max_depth=25, random_state=42, n_jobs=-1)
        mdl.fit(Xtr, ytr, sample_weight=wtr)

        pred = mdl.predict(Xte)
        acc = accuracy_score(yte, pred)
        report = classification_report(yte, pred, target_names=enc.classes_, zero_division=0)

        self.modelo_estatico = mdl
        self.encoder_estatico = enc

        with open(DIR_MODELOS / "modelo_estatico.pkl", "wb") as f:
            pickle.dump(mdl, f)
        with open(DIR_MODELOS / "encoder_estatico.pkl", "wb") as f:
            pickle.dump(enc, f)

        return (
            "✅ MODELO ESTÁTICO TREINADO\n"
            + f"Acurácia: {acc:.2%}\n"
            + f"Prioridades locais: {', '.join(sorted(prioridades)) if prioridades else '(nenhuma)'}\n"
            + "─" * 50
            + "\n"
            + report
        )

    def prever_estatico(self, features):
        if self.modelo_estatico is None or self.encoder_estatico is None:
            return None, 0.0

        try:
            x = np.asarray(features, dtype=np.float32).reshape(1, -1)
            proba = self.modelo_estatico.predict_proba(x)[0]
            i = int(np.argmax(proba))
            return self.encoder_estatico.classes_[i], float(proba[i])
        except Exception:
            return None, 0.0

    def _carregar_estatico(self):
        m = DIR_MODELOS / "modelo_estatico.pkl"
        e = DIR_MODELOS / "encoder_estatico.pkl"
        if m.exists() and e.exists():
            with open(m, "rb") as f:
                self.modelo_estatico = pickle.load(f)
            with open(e, "rb") as f:
                self.encoder_estatico = pickle.load(f)

    # ──────────────────────────────────────────────────────────────────────────
    # DINÂMICO (LSTM)
    # ──────────────────────────────────────────────────────────────────────────
    def _criar_modelo_dinamico(self, n_classes):
        model = tf.keras.Sequential([
            tf.keras.layers.Input(shape=(SEQUENCE_LENGTH, TOTAL_FEATURES)),

            tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(128, return_sequences=True)),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dropout(0.30),

            tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(256, return_sequences=True)),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dropout(0.30),

            tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(256, return_sequences=False)),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dropout(0.35),

            tf.keras.layers.Dense(128, activation="relu"),
            tf.keras.layers.Dropout(0.25),
            tf.keras.layers.Dense(n_classes, activation="softmax"),
        ])

        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
            loss="categorical_crossentropy",
            metrics=["accuracy"],
        )
        return model

    def _plotar_historico(self, hist):
        if not MATPLOTLIB_DISPONIVEL:
            return None

        hist_path = DIR_MODELOS / f"grafico_treino_dinamico_{timestamp_arquivo()}.png"
        try:
            loss = hist.history.get("loss", [])
            val_loss = hist.history.get("val_loss", [])
            acc = hist.history.get("accuracy", [])
            val_acc = hist.history.get("val_accuracy", [])

            fig, axs = plt.subplots(1, 2, figsize=(12, 4))

            axs[0].plot(loss, label="loss")
            axs[0].plot(val_loss, label="val_loss")
            axs[0].set_title("Loss")
            axs[0].set_xlabel("Época")
            axs[0].grid(alpha=0.2)
            axs[0].legend()

            axs[1].plot(acc, label="accuracy")
            axs[1].plot(val_acc, label="val_accuracy")
            axs[1].set_title("Accuracy")
            axs[1].set_xlabel("Época")
            axs[1].grid(alpha=0.2)
            axs[1].legend()

            plt.tight_layout()
            plt.savefig(hist_path, dpi=140)
            plt.close(fig)
            return str(hist_path)
        except Exception:
            return None

    def treinar_dinamico(
        self,
        X,
        y,
        meta,
        rotulos_prioritarios=None,
        peso_local=3.0,
        log=None,
        progresso_epoca_cb=None,
    ):
        ok_tf, status_tf = verificar_tensorflow()
        if not ok_tf:
            return f"❌ TensorFlow não instalado/disponível.\n{status_tf}"
        if len(X) == 0:
            return "❌ Nenhuma amostra dinâmica encontrada."

        erro = self._validar_dataset(y)
        if erro:
            return erro

        # Validação de sequências
        Xv, yv, metav = self._validar_sequencias_dinamicas(X, y, meta, log=log)
        if len(Xv) == 0:
            return "❌ Nenhuma sequência dinâmica válida após validação."

        erro2 = self._validar_dataset(yv)
        if erro2:
            return erro2

        pesos, prioridades = self._calcular_pesos_amostras(yv, metav, rotulos_prioritarios, peso_local)

        enc = LabelEncoder()
        y_enc = enc.fit_transform(yv)
        n_classes = len(enc.classes_)

        Xtr, Xte, ytr_s, yte_s, wtr, _, _, _ = train_test_split(
            Xv, y_enc, pesos, metav, test_size=0.2, random_state=42, stratify=y_enc
        )

        # Normalização aprimorada (fit no treino)
        Xtr, Xte, media, std = self._normalizar_dinamico_train_test(Xtr, Xte)
        self.norm_media_din = media
        self.norm_std_din = std

        # Data augmentation (somente treino)
        Xtr_aug, ytr_aug, wtr_aug = self._aumentar_dataset_dinamico(Xtr, ytr_s, wtr, fator=1)

        ytr = tf.keras.utils.to_categorical(ytr_aug, n_classes)
        yte = tf.keras.utils.to_categorical(yte_s, n_classes)

        if log:
            log("🔄 Treinando LSTM (dinâmico)...")
            log(f"📚 Dataset híbrido: {self._resumo_origens(metav)}")
            log(
                f"🎯 Sinais locais priorizados: {', '.join(sorted(prioridades)) if prioridades else '(nenhum)'}"
                f" | peso extra: {peso_local:.2f}x"
            )
            log(f"🧪 Treino original: {len(Xtr)} | com augmentation: {len(Xtr_aug)}")
            log(f"📐 Shape treino: {Xtr_aug.shape} | validação: {Xte.shape}")

        model = self._criar_modelo_dinamico(n_classes)

        chk_path = DIR_MODELOS / "modelo_dinamico_best.keras"

        class EpochProgressCallback(tf.keras.callbacks.Callback):
            def __init__(self, total_epochs, log_fn=None, progress_fn=None):
                super().__init__()
                self.total_epochs = total_epochs
                self.log_fn = log_fn
                self.progress_fn = progress_fn
                self.t0 = None
                self.epoch_times = []

            def on_train_begin(self, logs=None):
                self.t0 = time.time()

            def on_epoch_begin(self, epoch, logs=None):
                self._ep_start = time.time()

            def on_epoch_end(self, epoch, logs=None):
                logs = logs or {}
                dur = time.time() - self._ep_start
                self.epoch_times.append(dur)

                media_ep = float(np.mean(self.epoch_times)) if self.epoch_times else dur
                faltam = max(self.total_epochs - (epoch + 1), 0)
                eta = media_ep * faltam

                loss = float(logs.get("loss", 0.0))
                acc = float(logs.get("accuracy", 0.0))
                val_loss = float(logs.get("val_loss", 0.0))
                val_acc = float(logs.get("val_accuracy", 0.0))

                if self.log_fn:
                    self.log_fn(
                        f"📈 Época {epoch + 1}/{self.total_epochs} | "
                        f"loss={loss:.4f} acc={acc:.4f} | "
                        f"val_loss={val_loss:.4f} val_acc={val_acc:.4f} | "
                        f"ETA ~ {eta/60:.1f} min"
                    )

                if self.progress_fn:
                    self.progress_fn(epoch + 1, self.total_epochs, logs, eta)

        callbacks = [
            tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=18, restore_best_weights=True),
            tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-6, verbose=0),
            tf.keras.callbacks.ModelCheckpoint(
                filepath=str(chk_path),
                monitor="val_loss",
                save_best_only=True,
                save_weights_only=False,
                verbose=0,
            ),
            EpochProgressCallback(total_epochs=150, log_fn=log, progress_fn=progresso_epoca_cb),
        ]

        hist = model.fit(
            Xtr_aug,
            ytr,
            epochs=150,
            batch_size=32,
            validation_data=(Xte, yte),
            callbacks=callbacks,
            sample_weight=wtr_aug,
            verbose=0,
        )

        # Carrega melhor checkpoint, se existir
        if chk_path.exists():
            try:
                model = tf.keras.models.load_model(chk_path)
            except Exception:
                pass

        _, acc = model.evaluate(Xte, yte, verbose=0)
        pred = np.argmax(model.predict(Xte, verbose=0), axis=1)
        report = classification_report(yte_s, pred, target_names=enc.classes_, zero_division=0)

        self.modelo_dinamico = model
        self.encoder_dinamico = enc

        model.save(DIR_MODELOS / "modelo_dinamico.keras")
        with open(DIR_MODELOS / "encoder_dinamico.pkl", "wb") as f:
            pickle.dump(enc, f)

        np.savez_compressed(
            DIR_MODELOS / "normalizacao_dinamico.npz",
            media=self.norm_media_din,
            std=self.norm_std_din,
        )

        grafico = self._plotar_historico(hist)

        msg = (
            "✅ MODELO DINÂMICO TREINADO\n"
            + f"Acurácia: {acc:.2%} | Épocas executadas: {len(hist.history.get('loss', []))}\n"
            + f"Prioridades locais: {', '.join(sorted(prioridades)) if prioridades else '(nenhuma)'}\n"
        )
        if grafico:
            msg += f"📉 Gráfico salvo em: {grafico}\n"
        else:
            msg += "📉 Gráfico não gerado (matplotlib indisponível).\n"

        msg += "─" * 50 + "\n" + report
        return msg

    def prever_dinamico(self, sequencia):
        if self.modelo_dinamico is None or self.encoder_dinamico is None:
            return None, 0.0

        try:
            seq = np.asarray(sequencia, dtype=np.float32)
            if seq.ndim != 2 or seq.shape[1] != TOTAL_FEATURES:
                return None, 0.0

            seq = self._pad_or_crop_sequence(seq, SEQUENCE_LENGTH)
            seq = self._aplicar_norm(seq, self.norm_media_din, self.norm_std_din)
            x = seq.reshape(1, SEQUENCE_LENGTH, TOTAL_FEATURES)

            proba = self.modelo_dinamico.predict(x, verbose=0)[0]
            i = int(np.argmax(proba))
            return self.encoder_dinamico.classes_[i], float(proba[i])
        except Exception:
            return None, 0.0

    def _carregar_dinamico(self):
        ok_tf, _ = verificar_tensorflow()
        if not ok_tf:
            return

        m = DIR_MODELOS / "modelo_dinamico.keras"
        e = DIR_MODELOS / "encoder_dinamico.pkl"
        n = DIR_MODELOS / "normalizacao_dinamico.npz"

        if m.exists() and e.exists():
            try:
                self.modelo_dinamico = tf.keras.models.load_model(m)
                with open(e, "rb") as f:
                    self.encoder_dinamico = pickle.load(f)
            except Exception:
                self.modelo_dinamico = None
                self.encoder_dinamico = None

        if n.exists():
            try:
                data = np.load(n)
                self.norm_media_din = data["media"].astype(np.float32)
                self.norm_std_din = data["std"].astype(np.float32)
            except Exception:
                self.norm_media_din = None
                self.norm_std_din = None


# ══════════════════════════════════════════════════════════════════════════════
# APP (Tkinter)
# ══════════════════════════════════════════════════════════════════════════════

class LibrasApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("🤟 Libras OCR — TCC")
        self.geometry("1280x820")
        self.minsize(1100, 700)
        self.configure(bg=COR_BG)

        self.dados = GerenciadorDados()
        self.modelos = GerenciadorModelos()
        self.detector = None

        # Estado
        self.camera = None
        self.camera_rodando = False
        self.coletando = False
        self.reconhecendo = False

        # Coleta
        self.tipo_coleta = None  # estatico/dinamico
        self.rotulo_coleta = ""
        self.amostras_coletadas = 0
        self.amostras_alvo = 0
        self.seq_buffer = []

        # Reconhecimento
        self.hold_pred = ""
        self.hold_start = 0.0
        self.seq_rec = []

        # Debug/diagnóstico
        self.last_log_rec = 0.0

        self._aplicar_estilo()
        self._ui()
        self._atualizar_status_tensorflow()
        self._iniciar_camera()
        self.protocol("WM_DELETE_WINDOW", self._fechar)

    # ──────────────────────────────────────────────────────────────────────────
    # UI / TEMA
    # ──────────────────────────────────────────────────────────────────────────
    def _aplicar_estilo(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=COR_BG, foreground=COR_FG, font=("Segoe UI", 10))
        style.configure("TFrame", background=COR_BG)
        style.configure("TLabel", background=COR_BG, foreground=COR_FG)
        style.configure("TButton", background=COR_BG2, foreground=COR_FG, padding=8, font=("Segoe UI", 10, "bold"))
        style.map("TButton", background=[("active", COR_BG3)], foreground=[("active", COR_ACCENT)])
        style.configure("TNotebook", background=COR_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=COR_BG2, foreground=COR_FG, padding=[12, 6], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", COR_BG3)], foreground=[("selected", COR_ACCENT)])
        style.configure("TLabelframe", background=COR_BG, foreground=COR_ACCENT)
        style.configure("TLabelframe.Label", background=COR_BG, foreground=COR_ACCENT, font=("Segoe UI", 11, "bold"))
        style.configure("Accent.TButton", background=COR_ACCENT, foreground=COR_BG, font=("Segoe UI", 11, "bold"))
        style.map("Accent.TButton", background=[("active", COR_LAVENDER)])
        style.configure("Danger.TButton", background=COR_RED, foreground=COR_BG, font=("Segoe UI", 10, "bold"))
        style.map("Danger.TButton", background=[("active", "#e06080")])
        style.configure("Green.TButton", background=COR_GREEN, foreground=COR_BG, font=("Segoe UI", 10, "bold"))
        style.map("Green.TButton", background=[("active", "#80d080")])
        style.configure("Horizontal.TProgressbar", background=COR_ACCENT, troughcolor=COR_BG2)

    def _ui(self):
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Esquerda: câmera
        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))

        ttk.Label(left, text="📷 Câmera", font=("Segoe UI", 14, "bold"), foreground=COR_ACCENT).pack(pady=(0, 5))

        self.canvas = tk.Canvas(left, width=CAM_WIDTH, height=CAM_HEIGHT, bg="#000", highlightthickness=2, highlightbackground=COR_BG3)
        self.canvas.pack()

        self.lbl_cam = ttk.Label(left, text="⏳ Iniciando câmera...", foreground=COR_YELLOW)
        self.lbl_cam.pack(pady=5)

        self.lbl_pred = ttk.Label(left, text="—", font=("Segoe UI", 36, "bold"), foreground=COR_GREEN)
        self.lbl_pred.pack(pady=5)

        self.prog = ttk.Progressbar(left, orient="horizontal", length=CAM_WIDTH, mode="determinate", style="Horizontal.TProgressbar")
        self.prog.pack(pady=5)
        self.lbl_prog = ttk.Label(left, text="", foreground=COR_PEACH)
        self.lbl_prog.pack()

        # Direita: abas
        right = ttk.Frame(main)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.nb = ttk.Notebook(right)
        self.nb.pack(fill=tk.BOTH, expand=True)

        self._aba_coleta()
        self._aba_treino()
        self._aba_rec()

        # Inferior: texto
        bottom = ttk.LabelFrame(self, text="📝 Texto Traduzido", padding=10)
        bottom.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.txt = scrolledtext.ScrolledText(
            bottom,
            height=3,
            bg=COR_BG2,
            fg=COR_FG,
            font=("Consolas", 14),
            insertbackground=COR_FG,
            wrap=tk.WORD,
        )
        self.txt.pack(fill=tk.X, side=tk.LEFT, expand=True)

        btns = ttk.Frame(bottom)
        btns.pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(btns, text="🗑 Limpar", style="Danger.TButton", command=lambda: self.txt.delete("1.0", tk.END)).pack(pady=2)
        ttk.Button(btns, text="⬅ Apagar", command=self._apagar_ultimo).pack(pady=2)
        ttk.Button(btns, text="␣ Espaço", command=lambda: self.txt.insert(tk.END, " ")).pack(pady=2)

    # ──────────────────────────────────────────────────────────────────────────
    # ABAS
    # ──────────────────────────────────────────────────────────────────────────
    def _aba_coleta(self):
        aba = ttk.Frame(self.nb, padding=15)
        self.nb.add(aba, text="📦 Coleta")

        box = ttk.LabelFrame(aba, text="Ensinar novo sinal", padding=10)
        box.pack(fill=tk.X)

        ttk.Label(box, text="Nome do sinal/letra/número (ex: A, B, 1, OLA, OBRIGADO):").pack(anchor=tk.W)
        self.entry_rotulo = ttk.Entry(box, font=("Segoe UI", 12))
        self.entry_rotulo.pack(fill=tk.X, pady=(2, 8))

        ttk.Label(box, text="Quantidade de amostras:").pack(anchor=tk.W)
        self.var_qtd = tk.IntVar(value=50)
        f = ttk.Frame(box)
        f.pack(fill=tk.X, pady=(2, 0))
        for v in (30, 50, 100, 200):
            ttk.Radiobutton(f, text=str(v), variable=self.var_qtd, value=v).pack(side=tk.LEFT, padx=5)

        act = ttk.Frame(aba)
        act.pack(fill=tk.X, pady=10)
        self.btn_start_collect = ttk.Button(act, text="▶ Iniciar coleta (vai perguntar tipo)", style="Accent.TButton", command=self._iniciar_coleta)
        self.btn_start_collect.pack(side=tk.LEFT, padx=5)
        self.btn_stop_collect = ttk.Button(act, text="⏹ Parar", style="Danger.TButton", command=self._parar_coleta, state=tk.DISABLED)
        self.btn_stop_collect.pack(side=tk.LEFT, padx=5)

        classes = ttk.LabelFrame(aba, text="Classes cadastradas", padding=10)
        classes.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.box_classes = scrolledtext.ScrolledText(classes, bg=COR_BG2, fg=COR_FG, font=("Consolas", 10), state=tk.DISABLED)
        self.box_classes.pack(fill=tk.BOTH, expand=True)

        tools = ttk.Frame(classes)
        tools.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(tools, text="🔄 Atualizar", command=self._atualizar_classes).pack(side=tk.LEFT, padx=5)

        ttk.Label(tools, text="Deletar rótulo:").pack(side=tk.LEFT, padx=(15, 2))
        self.entry_del = ttk.Entry(tools, width=12)
        self.entry_del.pack(side=tk.LEFT)

        self.var_del_tipo = tk.StringVar(value="estatico")
        ttk.Radiobutton(tools, text="Estático", variable=self.var_del_tipo, value="estatico").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(tools, text="Dinâmico", variable=self.var_del_tipo, value="dinamico").pack(side=tk.LEFT, padx=5)

        ttk.Button(tools, text="🗑", style="Danger.TButton", command=self._deletar).pack(side=tk.LEFT, padx=5)

        self._atualizar_classes()

    def _config_treino_hibrido(self):
        rotulos = self.entry_prioritarios.get().strip().upper()
        peso_local = float(self.var_peso_local.get())
        return rotulos, peso_local

    def _aba_treino(self):
        aba = ttk.Frame(self.nb, padding=15)
        self.nb.add(aba, text="🧠 Treino")

        cfg = ttk.LabelFrame(aba, text="Treino híbrido (público + local)", padding=10)
        cfg.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(cfg, text="Sinais locais prioritários (separe por vírgula):").pack(anchor=tk.W)
        self.entry_prioritarios = ttk.Entry(cfg, font=("Segoe UI", 11))
        self.entry_prioritarios.insert(0, "")
        self.entry_prioritarios.pack(fill=tk.X, pady=(2, 8))

        ttk.Label(cfg, text="Peso extra para amostras locais desses sinais:").pack(anchor=tk.W)
        self.var_peso_local = tk.DoubleVar(value=3.0)
        ttk.Scale(cfg, from_=1.0, to=6.0, variable=self.var_peso_local, orient="horizontal").pack(fill=tk.X)
        self.lbl_peso_local = ttk.Label(cfg, text="3.00x", foreground=COR_PEACH)
        self.lbl_peso_local.pack(anchor=tk.E)
        self.var_peso_local.trace_add("write", lambda *_: self.lbl_peso_local.configure(text=f"{self.var_peso_local.get():.2f}x"))

        self.var_debug = tk.BooleanVar(value=False)
        ttk.Checkbutton(cfg, text="Modo debug (logs detalhados)", variable=self.var_debug).pack(anchor=tk.W, pady=(8, 0))

        ttk.Label(
            cfg,
            text="Ex.: OLA,OBRIGADO. Coletas locais novas ficam em /local e importadas podem ficar em /public.",
            foreground=COR_YELLOW,
        ).pack(anchor=tk.W, pady=(8, 0))

        self.lbl_tf_status = ttk.Label(cfg, text="TensorFlow: verificando...", foreground=COR_YELLOW)
        self.lbl_tf_status.pack(anchor=tk.W, pady=(10, 2))

        self.btn_instalar_tf = ttk.Button(cfg, text="📦 Instalar TensorFlow", style="Danger.TButton", command=self._instalar_tensorflow_ui)
        self.btn_instalar_tf.pack(anchor=tk.W)

        bar = ttk.Frame(aba)
        bar.pack(fill=tk.X, pady=(0, 10))

        self.btn_treinar_est = ttk.Button(bar, text="🏋 Treinar Estático", style="Accent.TButton", command=self._treinar_estatico)
        self.btn_treinar_est.pack(side=tk.LEFT, padx=5)

        self.btn_treinar_din = ttk.Button(bar, text="🏋 Treinar Dinâmico", style="Green.TButton", command=self._treinar_dinamico)
        self.btn_treinar_din.pack(side=tk.LEFT, padx=5)

        self.prog_treino = ttk.Progressbar(bar, orient="horizontal", length=260, mode="determinate", style="Horizontal.TProgressbar")
        self.prog_treino.pack(side=tk.LEFT, padx=(10, 5))

        self.lbl_treino_status = ttk.Label(bar, text="", foreground=COR_PEACH)
        self.lbl_treino_status.pack(side=tk.LEFT)

        self.log = scrolledtext.ScrolledText(aba, bg=COR_BG2, fg=COR_FG, font=("Consolas", 10), state=tk.DISABLED)
        self.log.pack(fill=tk.BOTH, expand=True)

    def _aba_rec(self):
        aba = ttk.Frame(self.nb, padding=15)
        self.nb.add(aba, text="🔍 Reconhecer")

        mode = ttk.LabelFrame(aba, text="Modo", padding=10)
        mode.pack(fill=tk.X, pady=(0, 10))

        self.var_modo = tk.StringVar(value="estatico")
        ttk.Radiobutton(mode, text="🖐 Estático", variable=self.var_modo, value="estatico").pack(anchor=tk.W)
        ttk.Radiobutton(mode, text="👋 Dinâmico", variable=self.var_modo, value="dinamico").pack(anchor=tk.W)
        ttk.Radiobutton(mode, text="🤟 Ambos", variable=self.var_modo, value="ambos").pack(anchor=tk.W)

        cfg = ttk.LabelFrame(aba, text="Parâmetros", padding=10)
        cfg.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(cfg, text="Limiar de confiança:").pack(anchor=tk.W)
        self.var_conf = tk.DoubleVar(value=0.7)
        ttk.Scale(cfg, from_=0.3, to=0.99, variable=self.var_conf, orient="horizontal").pack(fill=tk.X)
        self.lbl_conf = ttk.Label(cfg, text="0.70", foreground=COR_PEACH)
        self.lbl_conf.pack(anchor=tk.E)
        self.var_conf.trace_add("write", lambda *_: self.lbl_conf.configure(text=f"{self.var_conf.get():.2f}"))

        ttk.Label(cfg, text="Tempo de confirmação (seg):").pack(anchor=tk.W, pady=(8, 0))
        self.var_hold = tk.DoubleVar(value=1.0)
        ttk.Scale(cfg, from_=0.3, to=3.0, variable=self.var_hold, orient="horizontal").pack(fill=tk.X)
        self.lbl_hold = ttk.Label(cfg, text="1.00s", foreground=COR_PEACH)
        self.lbl_hold.pack(anchor=tk.E)
        self.var_hold.trace_add("write", lambda *_: self.lbl_hold.configure(text=f"{self.var_hold.get():.2f}s"))

        bar = ttk.Frame(aba)
        bar.pack(fill=tk.X, pady=10)
        self.btn_start_rec = ttk.Button(bar, text="▶ Iniciar", style="Accent.TButton", command=self._iniciar_rec)
        self.btn_start_rec.pack(side=tk.LEFT, padx=5)
        self.btn_stop_rec = ttk.Button(bar, text="⏹ Parar", style="Danger.TButton", command=self._parar_rec, state=tk.DISABLED)
        self.btn_stop_rec.pack(side=tk.LEFT, padx=5)

        self.lbl_info = ttk.Label(aba, text="ℹ Treine os modelos antes de reconhecer.", foreground=COR_YELLOW)
        self.lbl_info.pack(pady=10)

    # ──────────────────────────────────────────────────────────────────────────
    # UTIL
    # ──────────────────────────────────────────────────────────────────────────
    def _log(self, s):
        linha = f"[{agora_str()}] {s}"
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, linha + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _debug(self, s):
        if self.var_debug.get():
            self._log(f"[DEBUG] {s}")

    def _apagar_ultimo(self):
        c = self.txt.get("1.0", tk.END).rstrip("\n")
        if c:
            self.txt.delete("1.0", tk.END)
            self.txt.insert("1.0", c[:-1])

    def _atualizar_status_tensorflow(self):
        ok, status = verificar_tensorflow()
        self.lbl_tf_status.configure(text=f"TensorFlow: {status}", foreground=COR_GREEN if ok else COR_RED)

        if ok:
            self.btn_instalar_tf.configure(state=tk.DISABLED)
            self.btn_treinar_din.configure(state=tk.NORMAL)
        else:
            self.btn_instalar_tf.configure(state=tk.NORMAL)
            self.btn_treinar_din.configure(state=tk.DISABLED)

    def _instalar_tensorflow_ui(self):
        self.btn_instalar_tf.configure(state=tk.DISABLED)
        self._log("📦 Solicitação de instalação do TensorFlow...")

        def job():
            ok, msg = instalar_tensorflow(log_fn=lambda m: self.after(0, self._log, m))
            self.after(0, self._log, msg)

            def finish():
                self._atualizar_status_tensorflow()
                if ok:
                    self.modelos._carregar_dinamico()
                    messagebox.showinfo("TensorFlow", "✅ TensorFlow instalado e pronto para treino dinâmico.")
                else:
                    messagebox.showwarning("TensorFlow", msg)

            self.after(0, finish)

        threading.Thread(target=job, daemon=True).start()

    # ──────────────────────────────────────────────────────────────────────────
    # POPUP TIPO
    # ──────────────────────────────────────────────────────────────────────────
    def _perguntar_tipo(self):
        win = tk.Toplevel(self)
        win.title("Tipo do sinal")
        win.configure(bg=COR_BG)
        win.resizable(False, False)
        win.grab_set()

        ttk.Label(win, text="Esse sinal é ESTÁTICO ou DINÂMICO?", font=("Segoe UI", 11, "bold"), foreground=COR_ACCENT).pack(padx=16, pady=(14, 6))

        var = tk.StringVar(value="estatico")
        fr = ttk.Frame(win)
        fr.pack(padx=16, pady=6)
        ttk.Radiobutton(fr, text="🖐 Estático (mão parada: letras/números)", variable=var, value="estatico").pack(anchor=tk.W)
        ttk.Radiobutton(fr, text="👋 Dinâmico (movimento: palavras/sinais)", variable=var, value="dinamico").pack(anchor=tk.W)

        out = {"value": None}

        def ok():
            out["value"] = var.get()
            win.destroy()

        def cancel():
            out["value"] = None
            win.destroy()

        bt = ttk.Frame(win)
        bt.pack(pady=(6, 14))
        ttk.Button(bt, text="OK", style="Accent.TButton", command=ok).pack(side=tk.LEFT, padx=6)
        ttk.Button(bt, text="Cancelar", style="Danger.TButton", command=cancel).pack(side=tk.LEFT, padx=6)

        self.wait_window(win)
        return out["value"]

    # ──────────────────────────────────────────────────────────────────────────
    # COLETA
    # ──────────────────────────────────────────────────────────────────────────
    def _iniciar_coleta(self):
        rotulo = self.entry_rotulo.get().strip().upper()
        if not rotulo:
            messagebox.showwarning("Aviso", "Digite o nome do sinal (rótulo).")
            return

        tipo = self._perguntar_tipo()
        if tipo is None:
            return

        ok_tf, _ = verificar_tensorflow()
        if tipo == "dinamico" and not ok_tf:
            messagebox.showwarning(
                "Aviso",
                "TensorFlow não instalado. A coleta dinâmica pode salvar, mas o treino dinâmico ficará desativado.",
            )

        self.dados.garantir_classe(tipo, rotulo)
        pasta = self.dados._pasta_origem(tipo, rotulo, "local")

        self.tipo_coleta = tipo
        self.rotulo_coleta = rotulo
        self.amostras_alvo = int(self.var_qtd.get())
        self.amostras_coletadas = 0
        self.seq_buffer = []
        self.coletando = True

        self.btn_start_collect.configure(state=tk.DISABLED)
        self.btn_stop_collect.configure(state=tk.NORMAL)

        self.prog["maximum"] = self.amostras_alvo
        self.prog["value"] = 0
        self.lbl_prog.configure(text=f"📦 Coletando '{rotulo}' ({tipo}) em: {pasta}")
        self._log(f"📦 Coleta iniciada | rótulo={rotulo} | tipo={tipo} | alvo={self.amostras_alvo}")

    def _parar_coleta(self):
        self.coletando = False
        self.btn_start_collect.configure(state=tk.NORMAL)
        self.btn_stop_collect.configure(state=tk.DISABLED)
        self.lbl_prog.configure(text=f"⏹ Coleta parada — {self.amostras_coletadas} amostras")
        self._atualizar_classes()
        self._log(f"⏹ Coleta parada manualmente em {self.amostras_coletadas} amostras")

    def _finalizar_coleta(self):
        self.coletando = False
        self.btn_start_collect.configure(state=tk.NORMAL)
        self.btn_stop_collect.configure(state=tk.DISABLED)
        self.lbl_prog.configure(
            text=f"✅ Coleta concluída: {self.rotulo_coleta} ({self.tipo_coleta}) — {self.amostras_coletadas} amostras"
        )
        self._atualizar_classes()
        self._log(f"✅ Coleta finalizada | {self.rotulo_coleta} ({self.tipo_coleta}) | {self.amostras_coletadas} amostras")
        messagebox.showinfo(
            "Concluído",
            f"✅ {self.amostras_coletadas} amostras salvas para '{self.rotulo_coleta}' ({self.tipo_coleta}).",
        )

    def _atualizar_classes(self):
        d = self.dados.listar_classes()
        self.box_classes.configure(state=tk.NORMAL)
        self.box_classes.delete("1.0", tk.END)

        self.box_classes.insert(tk.END, "═══ ESTÁTICOS ═══\n")
        if d["estatico"]:
            for k, v in d["estatico"].items():
                self.box_classes.insert(tk.END, f"  🖐 {k:15s} → {v} amostras\n")
        else:
            self.box_classes.insert(tk.END, "  (nenhum)\n")

        self.box_classes.insert(tk.END, "\n═══ DINÂMICOS ═══\n")
        if d["dinamico"]:
            for k, v in d["dinamico"].items():
                self.box_classes.insert(tk.END, f"  👋 {k:15s} → {v} amostras\n")
        else:
            self.box_classes.insert(tk.END, "  (nenhum)\n")

        self.box_classes.configure(state=tk.DISABLED)

    def _deletar(self):
        rot = self.entry_del.get().strip().upper()
        if not rot:
            messagebox.showwarning("Aviso", "Digite o rótulo para deletar.")
            return
        tipo = self.var_del_tipo.get()
        if messagebox.askyesno("Confirmar", f"Deletar '{rot}' ({tipo})?"):
            self.dados.deletar_classe(tipo, rot)
            self.entry_del.delete(0, tk.END)
            self._atualizar_classes()
            self._log(f"🗑 Classe removida: {rot} ({tipo})")

    # ──────────────────────────────────────────────────────────────────────────
    # TREINO
    # ──────────────────────────────────────────────────────────────────────────
    def _set_progresso_treino(self, epoca, total, logs, eta):
        self.prog_treino["maximum"] = total
        self.prog_treino["value"] = epoca

        acc = float(logs.get("accuracy", 0.0))
        val_acc = float(logs.get("val_accuracy", 0.0))
        self.lbl_treino_status.configure(
            text=f"Época {epoca}/{total} | acc={acc:.3f} val_acc={val_acc:.3f} | ETA {eta/60:.1f} min"
        )

    def _treino_inicio_ui(self, dinamico=False):
        self.btn_treinar_est.configure(state=tk.DISABLED)
        self.btn_treinar_din.configure(state=tk.DISABLED)
        self.prog_treino["value"] = 0
        self.lbl_treino_status.configure(text="Treinando...")
        if dinamico:
            self.prog_treino["maximum"] = 150

    def _treino_fim_ui(self):
        self.btn_treinar_est.configure(state=tk.NORMAL)
        self._atualizar_status_tensorflow()
        self.lbl_treino_status.configure(text="Treino finalizado")

    def _treinar_estatico(self):
        rotulos_prioritarios, peso_local = self._config_treino_hibrido()

        def job():
            try:
                X, y, meta = self.dados.carregar_estaticos()
                self.after(0, self._log, f"📊 Estáticos: {len(X)} amostras")
                r = self.modelos.treinar_estatico(
                    X,
                    y,
                    meta,
                    rotulos_prioritarios=rotulos_prioritarios,
                    peso_local=peso_local,
                    log=lambda s: self.after(0, self._log, s),
                )
                self.after(0, self._log, r)
            except Exception as exc:
                self.after(0, self._log, f"❌ Erro no treino estático: {exc}")
                self.after(0, self._debug, traceback.format_exc())
            finally:
                self.after(0, self._treino_fim_ui)

        self._log("\n" + "═" * 60)
        self._log("🏋 Treinamento ESTÁTICO")
        self._log("═" * 60)
        self._treino_inicio_ui(dinamico=False)
        threading.Thread(target=job, daemon=True).start()

    def _treinar_dinamico(self):
        rotulos_prioritarios, peso_local = self._config_treino_hibrido()

        ok_tf, status = verificar_tensorflow()
        if not ok_tf:
            messagebox.showwarning("TensorFlow", f"Treino dinâmico indisponível.\n{status}")
            self._atualizar_status_tensorflow()
            return

        def job():
            try:
                X, y, meta = self.dados.carregar_dinamicos()
                self.after(0, self._log, f"📊 Dinâmicos: {len(X)} amostras")

                r = self.modelos.treinar_dinamico(
                    X,
                    y,
                    meta,
                    rotulos_prioritarios=rotulos_prioritarios,
                    peso_local=peso_local,
                    log=lambda s: self.after(0, self._log, s),
                    progresso_epoca_cb=lambda ep, total, logs, eta: self.after(
                        0, self._set_progresso_treino, ep, total, logs, eta
                    ),
                )
                self.after(0, self._log, r)
            except Exception as exc:
                self.after(0, self._log, f"❌ Erro no treino dinâmico: {exc}")
                self.after(0, self._debug, traceback.format_exc())
            finally:
                self.after(0, self._treino_fim_ui)

        self._log("\n" + "═" * 60)
        self._log("🏋 Treinamento DINÂMICO")
        self._log("═" * 60)
        self._treino_inicio_ui(dinamico=True)
        threading.Thread(target=job, daemon=True).start()

    # ──────────────────────────────────────────────────────────────────────────
    # RECONHECIMENTO
    # ──────────────────────────────────────────────────────────────────────────
    def _iniciar_rec(self):
        modo = self.var_modo.get()
        if modo in ("estatico", "ambos") and self.modelos.modelo_estatico is None:
            messagebox.showwarning("Aviso", "Treine o modelo estático primeiro.")
            return
        if modo in ("dinamico", "ambos") and self.modelos.modelo_dinamico is None:
            messagebox.showwarning("Aviso", "Treine o modelo dinâmico primeiro.")
            return

        self.reconhecendo = True
        self.hold_pred = ""
        self.hold_start = 0.0
        self.seq_rec = []

        self.btn_start_rec.configure(state=tk.DISABLED)
        self.btn_stop_rec.configure(state=tk.NORMAL)
        self.lbl_info.configure(text="🔍 Reconhecimento ativo...", foreground=COR_GREEN)
        self._log(f"🔍 Reconhecimento iniciado | modo={modo} | limiar={self.var_conf.get():.2f}")

    def _parar_rec(self):
        self.reconhecendo = False
        self.btn_start_rec.configure(state=tk.NORMAL)
        self.btn_stop_rec.configure(state=tk.DISABLED)
        self.lbl_info.configure(text="⏹ Reconhecimento parado.", foreground=COR_YELLOW)
        self.lbl_pred.configure(text="—")
        self._log("⏹ Reconhecimento pausado")

    def _confirmar_pred(self, pred, conf):
        self._set_pred_label(pred, conf)

        now = time.time()
        hold = float(self.var_hold.get())

        if pred == self.hold_pred:
            if now - self.hold_start >= hold:
                self.txt.insert(tk.END, pred)
                self.txt.see(tk.END)
                self.hold_pred = ""
                self.hold_start = 0.0
                self._debug(f"Predição confirmada: {pred} ({conf:.2%})")
        else:
            self.hold_pred = pred
            self.hold_start = now

    def _set_pred_label(self, pred, conf):
        if conf > 0:
            self.lbl_pred.configure(text=f"{pred} ({conf:.0%})", foreground=COR_GREEN if conf >= 0.8 else COR_YELLOW)
        else:
            self.lbl_pred.configure(text=pred, foreground=COR_FG)

    # ──────────────────────────────────────────────────────────────────────────
    # CÂMERA
    # ──────────────────────────────────────────────────────────────────────────
    def _cb_download_hand(self, baixados, total, pct, velocidade):
        def ui_update():
            self.prog["maximum"] = 100
            self.prog["value"] = min(max(pct, 0.0), 100.0)
            if total > 0:
                mb_b = baixados / (1024 * 1024)
                mb_t = total / (1024 * 1024)
                mb_s = velocidade / (1024 * 1024)
                self.lbl_cam.configure(
                    text=f"⬇ Baixando hand_landmarker.task... {pct:.1f}% ({mb_b:.1f}/{mb_t:.1f} MB) {mb_s:.2f} MB/s",
                    foreground=COR_YELLOW,
                )
            else:
                self.lbl_cam.configure(text=f"⬇ Baixando hand_landmarker.task... {baixados} bytes", foreground=COR_YELLOW)

        self.after(0, ui_update)

    def _inicializar_detector(self):
        try:
            self.lbl_cam.configure(text="🔎 Verificando hand_landmarker.task...", foreground=COR_YELLOW)
            self._log("🔎 Verificando arquivo hand_landmarker.task...")
            resultado = garantir_hand_landmarker(
                HAND_LANDMARKER_FILE,
                progress_cb=self._cb_download_hand,
                log_fn=lambda s: self.after(0, self._log, s),
            )

            if resultado == "baixado":
                self._log("✅ hand_landmarker.task baixado automaticamente.")

            self.detector = DetectorMaos(
                model_path=HAND_LANDMARKER_FILE,
                debug=self.var_debug.get(),
                log_fn=lambda s: self.after(0, self._log, s),
            )
            self.prog["value"] = 0
            return True
        except Exception as exc:
            self._log(f"❌ Falha ao inicializar detector: {exc}")
            self._debug(traceback.format_exc())
            self.lbl_cam.configure(text=f"❌ Erro detector: {exc}", foreground=COR_RED)
            return False

    def _iniciar_camera(self):
        if self.detector is None:
            ok = self._inicializar_detector()
            if not ok:
                return

        self.camera = cv2.VideoCapture(CAM_INDEX)
        if not self.camera.isOpened():
            self.lbl_cam.configure(text="❌ Câmera não encontrada", foreground=COR_RED)
            return

        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)

        self.camera_rodando = True
        self.lbl_cam.configure(text="✅ Câmera ativa", foreground=COR_GREEN)

        threading.Thread(target=self._loop_camera, daemon=True).start()

    def _loop_camera(self):
        """Loop: captura -> MediaPipe -> coleta/reconhecimento -> exibição."""
        while self.camera_rodando:
            try:
                ok, frame = self.camera.read()
                if not ok:
                    time.sleep(0.02)
                    continue

                frame = cv2.flip(frame, 1)
                res = self.detector.processar(frame)
                feats = self.detector.extrair_features(res)
                frame = self.detector.desenhar(frame, res)

                tem_mao = bool(res.hand_landmarks)

                # COLETA
                if self.coletando:
                    if tem_mao:
                        if self.tipo_coleta == "estatico":
                            self.dados.salvar_estatico(self.rotulo_coleta, feats)
                            self.amostras_coletadas += 1
                        else:
                            self.seq_buffer.append(feats)
                            if len(self.seq_buffer) >= SEQUENCE_LENGTH:
                                seq = np.array(self.seq_buffer[-SEQUENCE_LENGTH:], dtype=np.float32)
                                if seq.shape[0] >= MIN_DYNAMIC_FRAMES:
                                    self.dados.salvar_dinamico(self.rotulo_coleta, seq)
                                    self.amostras_coletadas += 1
                                self.seq_buffer = []

                        self.after(0, lambda: self._atualizar_progresso_overlay())

                        if self.amostras_coletadas >= self.amostras_alvo:
                            self.after(0, self._finalizar_coleta)

                # RECONHECIMENTO
                if self.reconhecendo:
                    lim = float(self.var_conf.get())
                    modo = self.var_modo.get()

                    pred, conf = None, 0.0

                    if tem_mao:
                        if modo in ("estatico", "ambos"):
                            p, c = self.modelos.prever_estatico(feats)
                            if p and c >= lim:
                                pred, conf = p, c

                        if modo in ("dinamico", "ambos"):
                            self.seq_rec.append(feats)
                            if len(self.seq_rec) >= SEQUENCE_LENGTH:
                                seq = np.array(self.seq_rec[-SEQUENCE_LENGTH:], dtype=np.float32)
                                p, c = self.modelos.prever_dinamico(seq)
                                if p and c >= lim and c > conf:
                                    pred, conf = p, c

                        if pred:
                            self.after(0, lambda p=pred, c=conf: self._confirmar_pred(p, c))
                        else:
                            self.after(0, lambda: self._set_pred_label("...", 0.0))

                        if self.var_debug.get() and (time.time() - self.last_log_rec) > 2.0:
                            self.last_log_rec = time.time()
                            self.after(0, self._log, f"[DEBUG] Reconhecimento ativo | modo={modo} | seq_len={len(self.seq_rec)}")
                    else:
                        self.seq_rec = []
                        self.after(0, lambda: self._set_pred_label("—", 0.0))

                if self.coletando:
                    color = (0, 255, 0) if tem_mao else (0, 0, 255)
                    cv2.putText(
                        frame,
                        f"Coleta: {self.rotulo_coleta} ({self.tipo_coleta}) {self.amostras_coletadas}/{self.amostras_alvo}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.75,
                        color,
                        2,
                    )

                self.after(0, lambda fr=frame: self._exibir(fr))
                time.sleep(0.02)
            except Exception as exc:
                self.after(0, self._log, f"⚠ Erro no loop da câmera: {exc}")
                self.after(0, self._debug, traceback.format_exc())
                time.sleep(0.05)

    def _atualizar_progresso_overlay(self):
        self.prog["maximum"] = self.amostras_alvo
        self.prog["value"] = self.amostras_coletadas
        self.lbl_prog.configure(
            text=f"📦 Coletando '{self.rotulo_coleta}' ({self.tipo_coleta}) — {self.amostras_coletadas}/{self.amostras_alvo}"
        )

    def _exibir(self, frame):
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            imgtk = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)
            self.canvas._imgtk = imgtk
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────────
    # FECHAR
    # ──────────────────────────────────────────────────────────────────────────
    def _fechar(self):
        self.camera_rodando = False
        self.coletando = False
        self.reconhecendo = False

        try:
            if self.camera and self.camera.isOpened():
                self.camera.release()
        except Exception:
            pass

        try:
            if self.detector:
                self.detector.liberar()
        except Exception:
            pass

        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    ok_tf, status_tf = verificar_tensorflow()

    print("=" * 70)
    print("🤟 Libras OCR — TCC")
    print("Base do projeto:", BASE_DIR)
    print("TensorFlow:", status_tf)
    print("Dados:", DIR_DADOS)
    print("Modelos:", DIR_MODELOS)
    print("Hand task:", HAND_LANDMARKER_FILE)
    print("=" * 70)

    app = LibrasApp()
    app.mainloop()
