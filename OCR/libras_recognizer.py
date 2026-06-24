#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SISTEMA DE RECONHECIMENTO DE LIBRAS — TCC                     ║
║        Visão Computacional + Machine Learning + Interface (Tkinter)        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Melhorias aplicadas:
- Detecção robusta de TensorFlow (múltiplas tentativas + instalação automática)
- MediaPipe Holistic: captura completa de mãos (126) + pose corporal (99) + rosto (1404) = 1629 features
- Normalização independente por região (mãos → pulso, pose → quadril/ombros, rosto → nariz/bochechas)
- Arquitetura LSTM dinâmica aprimorada (3 camadas BiLSTM + BatchNorm)
- Data augmentation para sequências dinâmicas (espelhamento, rotação, variação temporal)
- Feedback visual de treino (progresso, métricas por época, ETA e gráfico)
- Validações, normalização aprimorada, logs detalhados e modo debug
"""

# ══════════════════════════════════════════════════════════════════════════════
# IMPORTAÇÕES
# ══════════════════════════════════════════════════════════════════════════════

import importlib
import os
import pickle
import subprocess
import sys
import threading
import time
import traceback
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
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import LabelEncoder

try:
    from dtaidistance import dtw
    DTW_DISPONIVEL = True
except ImportError:
    DTW_DISPONIVEL = False


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
MP_DET_CONF = 0.7
MP_TRK_CONF = 0.5

# Sequências (dinâmico)
SEQUENCE_LENGTH = 30
MIN_DYNAMIC_FRAMES = 8

# Câmera
CAM_INDEX = 0
CAM_WIDTH = 640
CAM_HEIGHT = 480

# Features — MediaPipe Holistic otimizado para LIBRAS (mãos + pose apenas)
# Rosto é custoso demais (1404 features) com pouco valor discriminativo para sinais
FEATURES_MAO      = 21 * 3    # 63 por mão (x,y,z × 21 landmarks)
FEATURES_MAOS     = FEATURES_MAO * 2  # 126 (mão direita + esquerda)
FEATURES_POSE     = 33 * 3    # 99  (x,y,z × 33 landmarks de pose)
TOTAL_FEATURES    = FEATURES_MAOS + FEATURES_POSE  # 225 — otimizado para velocidade e escala

# Índices de início de cada bloco
IDX_POSE_START = FEATURES_MAOS  # 126

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
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "tensorflow==2.16.1",
        "numpy==1.26.4",
        "ml-dtypes==0.3.2",
        "--no-cache-dir"
    ]

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
# DETECTOR HOLISTIC (MediaPipe) — mãos + pose + rosto
# ══════════════════════════════════════════════════════════════════════════════

class DetectorHolistic:
    """Captura completa via MediaPipe Holistic: mãos (126) + pose (99) + rosto (1404) = 1629 features."""

    def __init__(self, debug=False, log_fn=None):
        self.debug = bool(debug)
        self.log_fn = log_fn

        self.holistic = mp.solutions.holistic.Holistic(
            static_image_mode=False,
            model_complexity=1,        # 0=leve, 1=médio, 2=pesado
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=MP_DET_CONF,
            min_tracking_confidence=MP_TRK_CONF,
        )

        self.mp_draw  = mp.solutions.drawing_utils
        self.mp_style = mp.solutions.drawing_styles
        self.mp_hol   = mp.solutions.holistic

    def _debug(self, msg):
        if self.debug:
            _safe_log(self.log_fn, f"[DEBUG Holistic] {msg}")

    def processar(self, frame_bgr):
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False
        result = self.holistic.process(frame_rgb)
        frame_rgb.flags.writeable = True
        return result

    def desenhar(self, frame_bgr, result):
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        ann = frame_rgb.copy()

        # Pose corporal
        if result.pose_landmarks:
            self.mp_draw.draw_landmarks(
                ann,
                result.pose_landmarks,
                self.mp_hol.POSE_CONNECTIONS,
                self.mp_style.get_default_pose_landmarks_style(),
            )

        # Mão direita
        if result.right_hand_landmarks:
            self.mp_draw.draw_landmarks(
                ann,
                result.right_hand_landmarks,
                self.mp_hol.HAND_CONNECTIONS,
                self.mp_style.get_default_hand_landmarks_style(),
                self.mp_style.get_default_hand_connections_style(),
            )

        # Mão esquerda
        if result.left_hand_landmarks:
            self.mp_draw.draw_landmarks(
                ann,
                result.left_hand_landmarks,
                self.mp_hol.HAND_CONNECTIONS,
                self.mp_style.get_default_hand_landmarks_style(),
                self.mp_style.get_default_hand_connections_style(),
            )

        return cv2.cvtColor(ann, cv2.COLOR_RGB2BGR)

    # ── Normalizações por região ───────────────────────────────────────────────

    @staticmethod
    def _normalizar_mao(pts):
        """Centraliza no pulso (lm 0) e escala pela distância palma→dedo médio (lm 9)."""
        pts = pts.astype(np.float32).copy()
        pts -= pts[0]
        ref = np.linalg.norm(pts[9])
        if ref < 1e-6:
            ref = float(np.max(np.abs(pts))) or 1.0
        pts /= ref
        return np.clip(pts, -3.0, 3.0)

    @staticmethod
    def _normalizar_pose(pts):
        """Centraliza no centro dos quadris (lm 23+24) e escala pela largura dos ombros (lm 11-12)."""
        pts = pts.astype(np.float32).copy()
        centro = (pts[23] + pts[24]) / 2.0 if len(pts) > 24 else pts[0]
        pts -= centro
        ref = np.linalg.norm(pts[11] - pts[12]) if len(pts) > 12 else 0.0
        if ref < 1e-6:
            ref = float(np.max(np.abs(pts))) or 1.0
        pts /= ref
        return np.clip(pts, -5.0, 5.0)


    # ── Extração de features ──────────────────────────────────────────────────

    # Mão dominante usada por quem está na câmera ("direita" ou "esquerda").
    # A mão dominante sempre vai para o slot [0:63] (dominante) e a
    # auxiliar para [63:126], garantindo compatibilidade entre destros e canhotos.
    mao_dominante: str = "direita"

    def extrair_features(self, result):
        """Retorna vetor 225: [dominante(63) | auxiliar(63) | pose(99)].

        Otimizado para LIBRAS: mãos + contexto postural. Sem rosto (custoso, pouco discriminativo).
        """
        feats = np.zeros(TOTAL_FEATURES, dtype=np.float32)

        if self.mao_dominante == "esquerda":
            lm_dom = result.left_hand_landmarks
            lm_aux = result.right_hand_landmarks
        else:
            lm_dom = result.right_hand_landmarks
            lm_aux = result.left_hand_landmarks

        # Mão dominante [0:63]
        if lm_dom:
            pts = np.array([[lm.x, lm.y, lm.z] for lm in lm_dom.landmark], dtype=np.float32)
            feats[0:FEATURES_MAO] = self._normalizar_mao(pts).flatten()

        # Mão auxiliar [63:126]
        if lm_aux:
            pts = np.array([[lm.x, lm.y, lm.z] for lm in lm_aux.landmark], dtype=np.float32)
            feats[FEATURES_MAO:FEATURES_MAOS] = self._normalizar_mao(pts).flatten()

        # Pose [126:225]
        if result.pose_landmarks:
            pts = np.array([[lm.x, lm.y, lm.z] for lm in result.pose_landmarks.landmark], dtype=np.float32)
            feats[IDX_POSE_START:] = self._normalizar_pose(pts).flatten()

        return feats

    def tem_mao(self, result):
        """Retorna True se qualquer mão foi detectada."""
        return result.right_hand_landmarks is not None or result.left_hand_landmarks is not None

    def liberar(self):
        try:
            self.holistic.close()
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

    # Pastas internas que não representam sinais reais e devem ser ignoradas
    _PASTAS_RESERVADAS = {"DATA", "TEMP", "BACKUP", "TEST", "RAW", "TMP", "DEBUG"}

    def _carregar_por_tipo(self, tipo):
        base = self._pasta_tipo(tipo)
        X, y, meta = [], [], []

        if not os.path.exists(base):
            return np.array(X, dtype=object), np.array(y), meta

        for rotulo in sorted(os.listdir(base)):
            pasta_classe = os.path.join(base, rotulo)
            if not os.path.isdir(pasta_classe):
                continue
            if rotulo.upper() in self._PASTAS_RESERVADAS:
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

    # Limiar: abaixo disso usa RF em vez de rede neural
    _MIN_AMOSTRAS_LSTM = 10

    def __init__(self):
        self.modelo_estatico = None
        self.encoder_estatico = None

        # Modelo dinâmico por rede neural (LSTM/GRU) — para muitas amostras
        self.modelo_dinamico = None
        self.encoder_dinamico = None
        self.norm_media_din = None
        self.norm_std_din = None

        # Modelo dinâmico por RandomForest — para poucas amostras (≥ 3 basta)
        self.modelo_dinamico_rf = None
        self.encoder_dinamico_rf = None

        # Modelo dinâmico por DTW (Dynamic Time Warping)
        self.X_train_dtw = None  # sequências completas
        self.y_train_dtw = None  # labels encoded
        self.encoder_dtw = None
        self.dtw_matrix = None   # cache de distâncias

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
        """Inverte coordenada X em mãos e pose."""
        out = seq.copy()
        blocos = [
            (0,              FEATURES_MAOS),
            (IDX_POSE_START, FEATURES_POSE),
        ]
        for start, length in blocos:
            x_idx = np.arange(start, start + length, 3)
            out[:, x_idx] *= -1.0
        return out

    @staticmethod
    def _rotacionar_xy(seq, ang_deg):
        """Rotaciona par (X,Y) em mãos e pose."""
        out = seq.copy()
        ang = np.deg2rad(ang_deg)
        c, s = np.cos(ang), np.sin(ang)

        blocos = [
            (0,              FEATURES_MAOS),
            (IDX_POSE_START, FEATURES_POSE),
        ]
        for start, length in blocos:
            x_idx = np.arange(start,     start + length, 3)
            y_idx = np.arange(start + 1, start + length, 3)
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
    def _validar_amostra_dinamica(seq):
        """Valida qualidade da amostra durante coleta.

        Retorna: (válida: bool, motivo: str, qualidade: float 0-1)
        """
        seq = np.asarray(seq, dtype=np.float32)
        n_frames = len(seq)

        # Critério 1: Mínimo de frames
        if n_frames < MIN_DYNAMIC_FRAMES:
            score = n_frames / MIN_DYNAMIC_FRAMES
            return False, f"movimento insuficiente ({n_frames}/<{MIN_DYNAMIC_FRAMES} frames)", score

        # Critério 2: Movimento significativo (variance média)
        movimento = np.std(seq, axis=0).mean()
        if movimento < 0.008:
            score = movimento / 0.015
            return False, f"muito estático (variância {movimento:.4f})", score

        # Critério 3: Detecção de "glitches" (picos anormais)
        try:
            diffs = np.linalg.norm(np.diff(seq, axis=0), axis=1)
            media_diff = np.mean(diffs)
            std_diff = np.std(diffs)
            outliers = np.sum(diffs > media_diff + 3*std_diff)

            if outliers > n_frames * 0.2:
                score = 1.0 - (outliers / n_frames)
                return False, f"movimento irregular ({outliers} picos anormais)", score
        except:
            pass

        # Qualidade final (0-1, baseado em tamanho e movimento)
        qualidade = min(1.0, (n_frames / SEQUENCE_LENGTH) * (movimento / 0.05))
        qualidade = np.clip(qualidade, 0.5, 1.0)  # mínimo 50%

        return True, "✅ OK", qualidade

    @staticmethod
    def _calcular_diversidade(lista_sequencias):
        """Calcula similaridade média entre últimas N sequências.

        Retorna: (diversidade: float 0-1, alerta: str ou None)
        """
        if len(lista_sequencias) < 2:
            return 1.0, None

        # Usar últimas 5 ou quantas tiver
        ultimas = lista_sequencias[-5:]

        # Calcular similaridade coseno pairwise
        similaridades = []
        for i in range(len(ultimas) - 1):
            v1 = ultimas[i].flatten()
            v2 = ultimas[i+1].flatten()

            # Normalizar
            v1 = v1 / (np.linalg.norm(v1) + 1e-6)
            v2 = v2 / (np.linalg.norm(v2) + 1e-6)

            # Coseno (0 = diferentes, 1 = idênticos)
            sim = np.dot(v1, v2)
            similaridades.append(sim)

        sim_media = np.mean(similaridades)
        diversidade = 1.0 - sim_media  # 0 = idêntico, 1 = diferente

        alerta = None
        if diversidade < 0.08:
            alerta = "⚠️  Últimas amostras MUITO similares — mude velocidade/posição"
        elif diversidade < 0.15:
            alerta = "⚠️  Últimas amostras similares — considere variar mais"

        return diversidade, alerta

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
    def treinar_estatico(self, X, y, meta, rotulos_prioritarios=None, peso_local=3.0, min_amostras_por_classe=2, log=None):
        if len(X) == 0:
            return "❌ Nenhuma amostra estática encontrada."

        # Filtrar classes com poucas amostras
        min_n = max(2, int(min_amostras_por_classe))
        cont_cls = Counter(y)
        validas = {c for c, q in cont_cls.items() if q >= min_n}
        if len(validas) < len(cont_cls) and log:
            ignoradas = len(cont_cls) - len(validas)
            log(f"⚠ Filtrando {ignoradas} classe(s) com menos de {min_n} amostras.")
        X_f = [x for x, yl in zip(X, y) if yl in validas]
        y_f = [yl for yl in y if yl in validas]
        meta_f = [m for m, yl in zip(meta, y) if yl in validas]
        X, y, meta = X_f, np.array(y_f), meta_f

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
            try:
                with open(m, "rb") as f:
                    mdl = pickle.load(f)

                n_feat = getattr(mdl, "n_features_in_", None)
                if n_feat is not None and n_feat != TOTAL_FEATURES:
                    print(
                        f"⚠ Modelo estático incompatível ({n_feat} features, esperado {TOTAL_FEATURES}). "
                        "Treine novamente."
                    )
                    return

                self.modelo_estatico = mdl
                with open(e, "rb") as f:
                    self.encoder_estatico = pickle.load(f)

            except Exception as exc:
                print(f"Erro ao carregar modelo estático: {exc}")
                print("O modelo estático será ignorado. Treine novamente pela interface.")
                self.modelo_estatico = None
                self.encoder_estatico = None


    # ──────────────────────────────────────────────────────────────────────────
    # DINÂMICO — features temporais (usadas pelo RF e pelo KNN)
    # ──────────────────────────────────────────────────────────────────────────

    # Pesos por bloco: mãos são essenciais em LIBRAS, pose fornece contexto
    _PESOS_BLOCO = np.concatenate([
        np.full(FEATURES_MAOS, 2.0),  # mãos: essencial
        np.full(FEATURES_POSE, 1.0),  # pose: contexto
    ]).astype(np.float32)

    @staticmethod
    def _extrair_features_seq(seq):
        """Converte sequência (N×1629) em vetor fixo ponderado para KNN.

        Divide em 3 segmentos temporais + velocidade média, depois aplica
        pesos por bloco (mãos > pose > rosto) para que o KNN coseno foque
        no que realmente discrimina os sinais.
        Resultado: 1629×4 = 6516 features ponderadas.
        """
        seq = GerenciadorModelos._pad_or_crop_sequence(
            np.asarray(seq, dtype=np.float32), SEQUENCE_LENGTH
        )
        n3 = SEQUENCE_LENGTH // 3
        seg1 = seq[:n3].mean(axis=0)
        seg2 = seq[n3: 2 * n3].mean(axis=0)
        seg3 = seq[2 * n3:].mean(axis=0)
        vel  = np.diff(seq, axis=0).mean(axis=0)

        feat = np.concatenate([seg1, seg2, seg3, vel]).astype(np.float32)
        # Repete os pesos para cobrir os 4 segmentos
        pesos = np.tile(GerenciadorModelos._PESOS_BLOCO, 4)
        return feat * pesos

    @staticmethod
    def _calcular_similarity_matrix(X_train, y_train, encoder, dtw_matrix, log=None):
        """Gera matriz de similaridade média entre pares de sinais.

        Retorna DataFrame com distâncias médias e acurácia pairwise.
        """
        try:
            import pandas as pd
        except ImportError:
            return None

        classes = encoder.classes_
        n_classes = len(classes)

        # Matriz de distâncias médias
        sim_matrix = np.zeros((n_classes, n_classes))
        acc_matrix = np.zeros((n_classes, n_classes))

        y_enc = y_train

        for i in range(n_classes):
            for j in range(n_classes):
                # Amostras da classe i e j
                mask_i = y_enc == i
                mask_j = y_enc == j
                idx_i = np.where(mask_i)[0]
                idx_j = np.where(mask_j)[0]

                if len(idx_i) == 0 or len(idx_j) == 0:
                    continue

                # Distância média entre pares
                dists = []
                for ii in idx_i:
                    for jj in idx_j:
                        if ii != jj:
                            d = dtw_matrix[ii, jj] if dtw_matrix is not None else 0
                            dists.append(d)

                if dists:
                    sim_matrix[i, j] = np.mean(dists)
                    # Acurácia: quantos pares da mesma classe estão mais próximos que da classe j
                    if i == j:
                        acc_matrix[i, j] = 1.0
                    else:
                        same_class_dist = [dtw_matrix[ii1, ii2] for ii1 in idx_i for ii2 in idx_i if ii1 < ii2]
                        if same_class_dist and dists:
                            mean_same = np.mean(same_class_dist)
                            mean_diff = np.mean(dists)
                            acc_matrix[i, j] = 1.0 / (1.0 + mean_diff / (mean_same + 1e-6))

        df = pd.DataFrame(
            sim_matrix,
            index=classes,
            columns=classes
        )

        if log:
            log(f"✅ Matriz de similaridade gerada ({n_classes}×{n_classes})")

        return df

    def _treinar_dinamico_dtw(self, Xv, yv, metav, pesos, prioridades, enc, n_classes, log):
        """DTW k=1 para sinais dinâmicos — compara sequências completas.

        Vantagem sobre agregação: robusta a variação de velocidade.
        Funciona com 10-20 amostras/classe.
        """
        if not DTW_DISPONIVEL:
            if log:
                log("⚠️  dtaidistance não instalado — usando KNN agregado")
            return self._treinar_dinamico_rf(Xv, yv, metav, pesos, prioridades, enc, n_classes, log)

        if log:
            log("🔍 Modo DTW-KNN ativado (sequências temporais completas)")
            log(f"📦 Armazenando {len(Xv)} sequências de {n_classes} sinais...")

        # Guardar sequências inteiras (não agregadas)
        self.X_train_dtw = np.array(Xv, dtype=np.float32)
        self.y_train_dtw = enc.transform(yv)
        self.encoder_dtw = enc

        # Calcular matriz de DTW (computacionalmente custoso, feito 1x)
        if log:
            log(f"📐 Calculando matriz DTW {len(Xv)}×{len(Xv)} (pode levar alguns segundos)...")

        n_seq = len(Xv)
        self.dtw_matrix = np.zeros((n_seq, n_seq), dtype=np.float32)

        for i in range(n_seq):
            for j in range(i + 1, n_seq):
                try:
                    d = dtw.distance(
                        Xv[i].astype(np.float64),
                        Xv[j].astype(np.float64)
                    )
                    self.dtw_matrix[i, j] = d
                    self.dtw_matrix[j, i] = d
                except Exception as e:
                    if log:
                        log(f"⚠️  Erro DTW({i},{j}): {e}")
                    self.dtw_matrix[i, j] = np.inf
                    self.dtw_matrix[j, i] = np.inf

            if log and (i + 1) % 10 == 0:
                log(f"  ... {i + 1}/{n_seq} sequências processadas")

        # Validação: acurácia via LOO (Leave-One-Out) aproximado
        corretos = 0
        for i in range(n_seq):
            # Encontra vizinho mais próximo (excluindo ele mesmo)
            dists = self.dtw_matrix[i].copy()
            dists[i] = np.inf
            idx_viz = np.argmin(dists)

            if self.y_train_dtw[idx_viz] == self.y_train_dtw[i]:
                corretos += 1

        acc_loo = corretos / n_seq if n_seq > 0 else 0.0

        # Gerar matriz de similaridade e relatório
        if log:
            log("📊 Gerando análise de similaridade (qual pares são confundíveis)...")

        # Relatório estruturado
        self.gerar_relatorio_similarity(log=log)

        # Salvar matriz em CSV também (para visualização rápida)
        sim_df = self._calcular_similarity_matrix(
            Xv, yv, enc, self.dtw_matrix, log=log
        )

        if sim_df is not None:
            sim_path = DIR_MODELOS / f"similarity_matrix_dtw_{timestamp_arquivo()}.csv"
            try:
                sim_df.to_csv(sim_path)
                if log:
                    log(f"💾 Matriz CSV salva: {sim_path}")
            except:
                pass

        if log:
            log(f"✅ DTW-KNN PRONTO")
            log(f"📊 Acurácia LOO: {acc_loo:.1%} | Sequências: {n_seq} | Classes: {n_classes}")
            log(f"🎯 Prioridades: {', '.join(sorted(prioridades)) if prioridades else '(nenhuma)'}")

        return (
            "✅ MODELO DINÂMICO (DTW) TREINADO\n"
            f"Acurácia LOO: {acc_loo:.1%} | Sequências: {n_seq} | Classes: {n_classes}\n"
            f"Prioridades: {', '.join(sorted(prioridades)) if prioridades else '(nenhuma)'}\n"
            "─" * 50 + "\n"
            "Pronto para reconhecer com DTW (robusto a variação de velocidade).\n"
            "📊 Veja similarity_matrix_dtw_*.csv para análise de confusões.\n"
        )

    def gerar_relatorio_similarity(self, log=None):
        """Gera relatório estruturado da similarity matrix para análise."""
        if self.X_train_dtw is None or self.dtw_matrix is None:
            return None

        import json

        classes = self.encoder_dtw.classes_
        n_classes = len(classes)

        relatorio = {
            "timestamp": datetime.now().isoformat(),
            "total_sequencias": len(self.X_train_dtw),
            "total_classes": n_classes,
            "analise_pairwise": {},
            "classe_mais_isolada": None,
            "classe_mais_confundivel": None,
            "pares_confundíveis": []
        }

        # Análise por classe
        for i in range(n_classes):
            mask_i = self.y_train_dtw == i
            idx_i = np.where(mask_i)[0]

            # Distância média intra-classe (coesão)
            intra_dists = []
            for ii1 in idx_i:
                for ii2 in idx_i:
                    if ii1 < ii2:
                        intra_dists.append(self.dtw_matrix[ii1, ii2])

            intra_mean = np.mean(intra_dists) if intra_dists else np.inf

            # Distância média inter-classe (para a classe mais próxima)
            inter_dists_min = []
            for j in range(n_classes):
                if i == j:
                    continue
                mask_j = self.y_train_dtw == j
                idx_j = np.where(mask_j)[0]

                for ii in idx_i:
                    for jj in idx_j:
                        if ii != jj:
                            inter_dists_min.append(self.dtw_matrix[ii, jj])

            inter_mean = np.mean(inter_dists_min) if inter_dists_min else np.inf

            # Score de isolamento (quanto maior, mais isolado)
            isolamento = inter_mean / (intra_mean + 1e-6) if intra_mean < np.inf else 0

            relatorio["analise_pairwise"][classes[i]] = {
                "amostras": len(idx_i),
                "coesao_intra": float(intra_mean),
                "distancia_inter_min": float(inter_mean),
                "isolamento": float(isolamento)
            }

        # Identificar classes extremas
        isolamentos = [v["isolamento"] for v in relatorio["analise_pairwise"].values()]
        if isolamentos:
            relatorio["classe_mais_isolada"] = max(
                relatorio["analise_pairwise"].items(),
                key=lambda x: x[1]["isolamento"]
            )[0]
            relatorio["classe_mais_confundivel"] = min(
                relatorio["analise_pairwise"].items(),
                key=lambda x: x[1]["isolamento"]
            )[0]

        # Encontrar pares confundíveis
        for i in range(n_classes):
            for j in range(i + 1, n_classes):
                mask_i = self.y_train_dtw == i
                mask_j = self.y_train_dtw == j
                idx_i = np.where(mask_i)[0]
                idx_j = np.where(mask_j)[0]

                dists = []
                for ii in idx_i:
                    for jj in idx_j:
                        dists.append(self.dtw_matrix[ii, jj])

                dist_media = np.mean(dists) if dists else np.inf

                # Confundível se < 0.5 (escala normalizada)
                if dist_media < 0.5:
                    relatorio["pares_confundíveis"].append({
                        "sinal_1": classes[i],
                        "sinal_2": classes[j],
                        "distancia_media": float(dist_media),
                        "risco": "ALTO" if dist_media < 0.3 else "MÉDIO"
                    })

        # Ordenar pares confundíveis
        relatorio["pares_confundíveis"].sort(key=lambda x: x["distancia_media"])

        # Salvar relatório
        rel_path = DIR_MODELOS / f"similarity_report_dtw_{timestamp_arquivo()}.json"
        with open(rel_path, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, indent=2, ensure_ascii=False)

        if log:
            log(f"📄 Relatório salvo: {rel_path}")
            log(f"✅ Classe mais isolada: {relatorio['classe_mais_isolada']}")
            log(f"⚠️  Classe mais confundível: {relatorio['classe_mais_confundivel']}")
            if relatorio["pares_confundíveis"]:
                log(f"🔴 {len(relatorio['pares_confundíveis'])} pares confundíveis detectados")

        return relatorio

    def prever_dinamico_dtw(self, sequencia):
        """Predição via DTW k=1 (vizinho mais próximo por distância DTW)."""
        if self.X_train_dtw is None or self.encoder_dtw is None:
            return None, 0.0

        try:
            seq = self._pad_or_crop_sequence(sequencia, SEQUENCE_LENGTH).astype(np.float64)

            # Calcular DTW com cada sequência de treino
            distancias = []
            for x_train in self.X_train_dtw:
                d = dtw.distance(seq, x_train.astype(np.float64))
                distancias.append(d)

            distancias = np.array(distancias)
            idx_viz = np.argmin(distancias)
            d_min = distancias[idx_viz]

            # Confiança: inversa da distância normalizada
            d_max = np.max(distancias)
            d_media = np.median(distancias)

            if d_max == d_min:
                confianca = 1.0
            else:
                # Escalar: d_min é 1.0, d_media é 0.5
                confianca = 1.0 - (d_min / d_media) if d_media > 0 else 0.5
                confianca = np.clip(confianca, 0.0, 1.0)

            rotulo = self.encoder_dtw.classes_[self.y_train_dtw[idx_viz]]
            return rotulo, confianca
        except Exception:
            return None, 0.0

    def _treinar_dinamico_rf(self, Xv, yv, metav, pesos, prioridades, enc, n_classes, log):
        """KNN k=1 para sinais dinâmicos com poucas amostras.

        Com 3 amostras/classe, classificadores tradicionais não generalizam.
        KNN k=1 usa similaridade de cosseno para encontrar o template mais
        parecido — funciona bem mesmo com 1-3 exemplos por classe.
        Treina em TODAS as amostras (sem split) para maximizar cobertura.
        """
        if log:
            log("🔍 Modo KNN ativado (poucas amostras/classe — busca pelo template mais similar).")
            log(f"📦 Armazenando {len(Xv)} templates de {n_classes} sinais...")

        X_feat = np.array([self._extrair_features_seq(s) for s in Xv], dtype=np.float32)
        y_enc = enc.transform(yv)

        # k=1: retorna o sinal mais parecido. Cosine é robusto para features de alta dimensão.
        mdl = KNeighborsClassifier(n_neighbors=1, metric="cosine", algorithm="brute", n_jobs=-1)
        mdl.fit(X_feat, y_enc)

        # Avaliação leave-one-out rápida (só possível com todos os dados)
        corretos = 0
        for i in range(len(X_feat)):
            # Ignora o próprio exemplo (simula LOO)
            dists, idxs = mdl.kneighbors(X_feat[i:i+1], n_neighbors=min(4, len(X_feat)))
            vizinhos = [(d, y_enc[j]) for d, j in zip(dists[0], idxs[0]) if j != i]
            if vizinhos and vizinhos[0][1] == y_enc[i]:
                corretos += 1
        acc_loo = corretos / len(X_feat) if X_feat.size else 0.0

        self.modelo_dinamico_rf = mdl
        self.encoder_dinamico_rf = enc

        with open(DIR_MODELOS / "modelo_dinamico_rf.pkl", "wb") as f:
            pickle.dump(mdl, f)
        with open(DIR_MODELOS / "encoder_dinamico_rf.pkl", "wb") as f:
            pickle.dump(enc, f)

        return (
            "✅ MODELO DINÂMICO (KNN) TREINADO\n"
            f"Acurácia LOO: {acc_loo:.2%} | Classes: {n_classes} | Templates: {len(Xv)}\n"
            f"Prioridades locais: {', '.join(sorted(prioridades)) if prioridades else '(nenhuma)'}\n"
            "─" * 50 + "\n"
            "Pronto para reconhecer. Faça o sinal e retire a mão da câmera.\n"
        )

    def prever_dinamico_rf(self, sequencia):
        """Predição via KNN k=1 (similaridade de cosseno com templates armazenados)."""
        if self.modelo_dinamico_rf is None or self.encoder_dinamico_rf is None:
            return None, 0.0
        try:
            feat = self._extrair_features_seq(sequencia).reshape(1, -1)
            dist, idx = self.modelo_dinamico_rf.kneighbors(feat, n_neighbors=1)
            distancia = float(dist[0][0])   # distância cosseno: 0 = idêntico, 2 = oposto
            y_pred = int(self.modelo_dinamico_rf._y[idx[0][0]])
            rotulo = self.encoder_dinamico_rf.classes_[y_pred]
            # Converte distância em confiança: dist=0 → conf=1.0, dist=1 → conf=0.0
            confianca = max(0.0, 1.0 - distancia)
            return rotulo, confianca
        except Exception:
            return None, 0.0

    def _carregar_dinamico_rf(self):
        m = DIR_MODELOS / "modelo_dinamico_rf.pkl"
        e = DIR_MODELOS / "encoder_dinamico_rf.pkl"
        if m.exists() and e.exists():
            try:
                with open(m, "rb") as f:
                    mdl = pickle.load(f)

                n_feat = getattr(mdl, "n_features_in_", None)
                feat_esperado = TOTAL_FEATURES * 4  # _extrair_features_seq: 4 segmentos
                if n_feat is not None and n_feat != feat_esperado:
                    print(
                        f"⚠ Modelo dinâmico KNN incompatível ({n_feat} features, esperado {feat_esperado}). "
                        "Treine novamente."
                    )
                    return

                self.modelo_dinamico_rf = mdl
                with open(e, "rb") as f:
                    self.encoder_dinamico_rf = pickle.load(f)
            except Exception as exc:
                print(f"Erro ao carregar modelo dinâmico KNN: {exc}")
                self.modelo_dinamico_rf = None
                self.encoder_dinamico_rf = None

    # ──────────────────────────────────────────────────────────────────────────
    # DINÂMICO (LSTM)
    # ──────────────────────────────────────────────────────────────────────────
    def _criar_modelo_dinamico(self, n_classes, n_amostras=0):
        """Arquitetura adaptativa: modelo simpler quando há muitas classes e poucas amostras."""
        amostras_por_classe = n_amostras / max(n_classes, 1)

        if n_classes > 50 or amostras_por_classe < 10:
            # Dataset com muitas classes / poucas amostras por classe:
            # modelo leve com GRU para evitar overfitting severo.
            model = tf.keras.Sequential([
                tf.keras.layers.Input(shape=(SEQUENCE_LENGTH, TOTAL_FEATURES)),

                tf.keras.layers.GRU(128, return_sequences=True),
                tf.keras.layers.Dropout(0.40),

                tf.keras.layers.GRU(64, return_sequences=False),
                tf.keras.layers.Dropout(0.40),

                tf.keras.layers.Dense(128, activation="relu"),
                tf.keras.layers.Dropout(0.35),
                tf.keras.layers.Dense(n_classes, activation="softmax"),
            ])
            lr = 3e-4
        else:
            # Dataset menor com mais amostras por classe: BiLSTM completo.
            model = tf.keras.Sequential([
                tf.keras.layers.Input(shape=(SEQUENCE_LENGTH, TOTAL_FEATURES)),

                tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(128, return_sequences=True)),
                tf.keras.layers.BatchNormalization(),
                tf.keras.layers.Dropout(0.30),

                tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(256, return_sequences=False)),
                tf.keras.layers.BatchNormalization(),
                tf.keras.layers.Dropout(0.35),

                tf.keras.layers.Dense(128, activation="relu"),
                tf.keras.layers.Dropout(0.25),
                tf.keras.layers.Dense(n_classes, activation="softmax"),
            ])
            lr = 1e-3

        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
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
        min_amostras_por_classe=2,
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

        Xv, yv, metav = self._validar_sequencias_dinamicas(X, y, meta, log=log)
        if len(Xv) == 0:
            return "❌ Nenhuma sequência dinâmica válida após validação."

        erro2 = self._validar_dataset(yv)
        if erro2:
            return erro2

        pesos, prioridades = self._calcular_pesos_amostras(yv, metav, rotulos_prioritarios, peso_local)

        min_n = max(2, int(min_amostras_por_classe))
        contagem_classes = Counter(yv)
        classes_validas = {classe for classe, qtd in contagem_classes.items() if qtd >= min_n}
        ignoradas = len(contagem_classes) - len(classes_validas)
        if ignoradas > 0 and log:
            log(f"⚠ Filtrando {ignoradas} classe(s) com menos de {min_n} amostras (total={sum(q for c,q in contagem_classes.items() if c not in classes_validas)} amostras removidas).")

        Xv_filtrado, yv_filtrado, metav_filtrado, pesos_filtrado = [], [], [], []

        for x_item, y_item, meta_item, peso_item in zip(Xv, yv, metav, pesos):
            if y_item in classes_validas:
                Xv_filtrado.append(x_item)
                yv_filtrado.append(y_item)
                metav_filtrado.append(meta_item)
                pesos_filtrado.append(peso_item)

        Xv = np.array(Xv_filtrado, dtype=np.float32)
        yv = np.array(yv_filtrado)
        metav = metav_filtrado
        pesos = np.array(pesos_filtrado, dtype=np.float32)

        if len(Xv) == 0:
            return "❌ Nenhuma sequência dinâmica válida após filtrar classes com poucas amostras."

        if len(set(yv)) < 2:
            return "❌ Após o filtro, restaram menos de 2 classes dinâmicas para treino."

        enc = LabelEncoder()
        enc.fit(yv)
        n_classes = len(enc.classes_)
        qtd_amostras = len(Xv)
        qtd_classes = n_classes

        amostras_por_classe = qtd_amostras / max(qtd_classes, 1)

        if log:
            log(f"📊 Classes dinâmicas: {qtd_classes} | Amostras: {qtd_amostras}")
            log(f"📊 Média amostras/classe: {amostras_por_classe:.1f}")

        # Estratégia por quantidade de dados
        if amostras_por_classe < self._MIN_AMOSTRAS_LSTM:
            # < 10 amostras/classe: usar DTW se disponível (melhor que KNN agregado)
            if DTW_DISPONIVEL:
                return self._treinar_dinamico_dtw(Xv, yv, metav, pesos, prioridades, enc, n_classes, log)
            else:
                return self._treinar_dinamico_rf(Xv, yv, metav, pesos, prioridades, enc, n_classes, log)
        elif amostras_por_classe < 20:
            # 10-20 amostras/classe: DTW é ótimo aqui (sequências completas, robusto)
            if DTW_DISPONIVEL:
                return self._treinar_dinamico_dtw(Xv, yv, metav, pesos, prioridades, enc, n_classes, log)
            else:
                return self._treinar_dinamico_rf(Xv, yv, metav, pesos, prioridades, enc, n_classes, log)

        # --- LSTM path (muitas amostras) ---
        y_enc = enc.transform(yv)

        test_size_abs = max(int(qtd_amostras * 0.2), qtd_classes)

        if test_size_abs >= qtd_amostras:
            test_size_abs = max(1, qtd_amostras - qtd_classes)

        if test_size_abs <= 0 or test_size_abs >= qtd_amostras:
            return (
                f"❌ Não há amostras suficientes para separar treino/teste.\n"
                f"Amostras: {qtd_amostras} | Classes: {qtd_classes}\n"
                f"Reduza a quantidade de classes ou colete mais amostras por classe."
            )

        if log:
            log(f"📊 Tamanho do teste ajustado: {test_size_abs}")

        Xtr, Xte, ytr_s, yte_s, wtr, _, _, _ = train_test_split(
            Xv, y_enc, pesos, metav,
            test_size=test_size_abs,
            random_state=42,
            stratify=y_enc
        )

        Xtr, Xte, media, std = self._normalizar_dinamico_train_test(Xtr, Xte)
        self.norm_media_din = media
        self.norm_std_din = std

        # Augmentation agressivo baseado nas amostras de treino
        fator_aug = 3 if (len(Xtr) / max(n_classes, 1)) < 20 else 1

        Xtr_aug, ytr_aug, wtr_aug = self._aumentar_dataset_dinamico(Xtr, ytr_s, wtr, fator=fator_aug)

        ytr = tf.keras.utils.to_categorical(ytr_aug, n_classes)
        yte = tf.keras.utils.to_categorical(yte_s, n_classes)

        # Batch size adaptativo
        batch_size = min(64, max(16, len(Xtr_aug) // 50))

        if log:
            log("🔄 Treinando modelo dinâmico...")
            log(f"📚 Dataset híbrido: {self._resumo_origens(metav)}")
            log(
                f"🎯 Sinais locais priorizados: "
                f"{', '.join(sorted(prioridades)) if prioridades else '(nenhum)'}"
                f" | peso extra: {peso_local:.2f}x"
            )
            log(f"🧪 Treino original: {len(Xtr)} | com augmentation (fator={fator_aug}): {len(Xtr_aug)}")
            log(f"📐 Shape treino: {Xtr_aug.shape} | validação: {Xte.shape}")
            log(f"⚙️  batch_size={batch_size} | amostras/classe≈{amostras_por_classe:.1f}")

        model = self._criar_modelo_dinamico(n_classes, n_amostras=len(Xtr_aug))
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
                filepath=str(chk_path), monitor="val_loss",
                save_best_only=True, save_weights_only=False, verbose=0,
            ),
            EpochProgressCallback(total_epochs=150, log_fn=log, progress_fn=progresso_epoca_cb),
        ]

        hist = model.fit(
            Xtr_aug, ytr,
            epochs=150,
            batch_size=batch_size,
            validation_data=(Xte, yte),
            callbacks=callbacks,
            sample_weight=wtr_aug,
            verbose=0,
        )

        if chk_path.exists():
            try:
                model = tf.keras.models.load_model(chk_path)
            except Exception:
                pass

        _, acc = model.evaluate(Xte, yte, verbose=0)
        pred = np.argmax(model.predict(Xte, verbose=0), axis=1)
        report = classification_report(yte_s, pred, labels=list(range(n_classes)), target_names=enc.classes_, zero_division=0)

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
            + f"Classes treinadas: {n_classes}\n"
            + f"Amostras usadas: {qtd_amostras}\n"
            + f"Prioridades locais: {', '.join(sorted(prioridades)) if prioridades else '(nenhuma)'}\n"
        )
        if grafico:
            msg += f"📉 Gráfico salvo em: {grafico}\n"
        else:
            msg += "📉 Gráfico não gerado (matplotlib indisponível).\n"
        msg += "─" * 50 + "\n" + report
        return msg


    def prever_dinamico(self, sequencia):
        # DTW tem prioridade (melhor que agregação para variação de velocidade)
        if self.X_train_dtw is not None:
            return self.prever_dinamico_dtw(sequencia)

        # Fallback: KNN agregado
        if self.modelo_dinamico_rf is not None:
            return self.prever_dinamico_rf(sequencia)

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
        # Carrega RF primeiro (não precisa de TF)
        self._carregar_dinamico_rf()

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

        # Segmentação automática (coleta dinâmica)
        # Estados: "aguardando_espaco" → [SPACE] → "aguardando_mao" → mão aparece
        #          → "gravando" → mão some N frames → salva → "aguardando_espaco"
        self.seg_estado = "aguardando_espaco"
        self.seg_frames_sem_mao = 0      # contador de frames sem mão após gravação
        self.SEG_FRAMES_PAUSA = 8        # frames sem mão para confirmar fim do sinal

        # Validação e diversidade
        self.buffer_ultimas_amostras = []  # últimas 5 amostras para verificar diversidade
        self.estatisticas_coleta = {      # tracker de qualidade durante coleta
            "total_validas": 0,
            "total_rejeitadas": 0,
            "qualidades": [],
            "diversidades": []
        }

        # Reconhecimento
        self.hold_pred = ""
        self.hold_start = 0.0
        self.seq_rec = []
        self.hand_was_visible = False  # controla disparo de predição dinâmica
        self.ultimo_pred = ""          # último sinal reconhecido (mantido na tela)
        self.ultima_conf = 0.0

        # Debug/diagnóstico
        self.last_log_rec = 0.0

        self._aplicar_estilo()
        self._ui()
        self._atualizar_status_tensorflow()
        self._iniciar_camera()
        self.bind("<space>", self._tecla_espaco)
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
        self._aba_transcricao()

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

        # Mão dominante — afeta coleta e reconhecimento
        dom_frame = ttk.LabelFrame(box, text="Mão dominante de quem está na câmera", padding=6)
        dom_frame.pack(fill=tk.X, pady=(0, 10))
        self.var_mao_dom = tk.StringVar(value="direita")
        ttk.Radiobutton(dom_frame, text="✋ Direita (destro)", variable=self.var_mao_dom, value="direita",
                        command=self._aplicar_mao_dominante).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(dom_frame, text="🤚 Esquerda (canhoto)", variable=self.var_mao_dom, value="esquerda",
                        command=self._aplicar_mao_dominante).pack(side=tk.LEFT, padx=10)
        ttk.Label(dom_frame, text="Mude antes de gravar ou reconhecer!", foreground=COR_YELLOW,
                  font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=8)

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
        min_amostras = int(self.var_min_amostras.get())
        return rotulos, peso_local, min_amostras

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

        ttk.Label(cfg, text="Mínimo de amostras por classe (filtra classes com poucos dados):").pack(anchor=tk.W, pady=(8, 0))
        self.var_min_amostras = tk.IntVar(value=2)
        fr_min = ttk.Frame(cfg)
        fr_min.pack(fill=tk.X, pady=(2, 0))
        for v in (2, 5, 10, 20):
            ttk.Radiobutton(fr_min, text=str(v), variable=self.var_min_amostras, value=v).pack(side=tk.LEFT, padx=5)

        self.var_debug = tk.BooleanVar(value=False)
        ttk.Checkbutton(cfg, text="Modo debug (logs detalhados)", variable=self.var_debug).pack(anchor=tk.W, pady=(8, 0))

        ttk.Label(
            cfg,
            text="Ex.: OLA,OBRIGADO. Coletas locais novas ficam em /local e importadas podem ficar em /public.",
            foreground=COR_YELLOW,
        ).pack(anchor=tk.W, pady=(8, 0))

        self.lbl_tf_status = ttk.Label(cfg, text="TensorFlow: verificando...", foreground=COR_YELLOW)
        self.lbl_tf_status.pack(anchor=tk.W, pady=(10, 2))

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
        self.var_conf = tk.DoubleVar(value=0.50)
        ttk.Scale(cfg, from_=0.3, to=0.99, variable=self.var_conf, orient="horizontal").pack(fill=tk.X)
        self.lbl_conf = ttk.Label(cfg, text="0.50", foreground=COR_PEACH)
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

    def _aba_transcricao(self):
        aba = ttk.Frame(self.nb, padding=15)
        self.nb.add(aba, text="✍️ Transcrição")

        # Modo de transcrição
        mode = ttk.LabelFrame(aba, text="Configuração", padding=10)
        mode.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(mode, text="Modo de tradução:").pack(anchor=tk.W)
        self.var_modo_trans = tk.StringVar(value="dinamico")
        ttk.Radiobutton(mode, text="👋 Dinâmico (gestos)", variable=self.var_modo_trans, value="dinamico").pack(anchor=tk.W)
        ttk.Radiobutton(mode, text="🖐 Estático (letras)", variable=self.var_modo_trans, value="estatico").pack(anchor=tk.W)
        ttk.Radiobutton(mode, text="🤟 Ambos", variable=self.var_modo_trans, value="ambos").pack(anchor=tk.W)

        # Controles
        btn_frame = ttk.Frame(aba)
        btn_frame.pack(fill=tk.X, pady=10)
        self.btn_trans_start = ttk.Button(btn_frame, text="🎥 Iniciar Transcrição", style="Accent.TButton", command=self._iniciar_transcricao)
        self.btn_trans_start.pack(side=tk.LEFT, padx=5)
        self.btn_trans_stop = ttk.Button(btn_frame, text="⏹ Parar", style="Danger.TButton", command=self._parar_transcricao, state=tk.DISABLED)
        self.btn_trans_stop.pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="💾 Salvar", command=self._salvar_transcricao).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🗑 Limpar", style="Danger.TButton", command=self._limpar_transcricao).pack(side=tk.LEFT, padx=5)

        # Texto traduzido
        txt_frame = ttk.LabelFrame(aba, text="Transcrição em Tempo Real", padding=10)
        txt_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.txt_trans = scrolledtext.ScrolledText(
            txt_frame,
            height=8,
            bg=COR_BG2,
            fg=COR_GREEN,
            font=("Consolas", 12),
            insertbackground=COR_FG,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.txt_trans.pack(fill=tk.BOTH, expand=True)

        # Histórico com timestamps
        hist_frame = ttk.LabelFrame(aba, text="Histórico (últimos 10 gestos)", padding=10)
        hist_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_historico = scrolledtext.ScrolledText(
            hist_frame,
            height=5,
            bg=COR_BG2,
            fg=COR_PEACH,
            font=("Consolas", 9),
            state=tk.DISABLED
        )
        self.txt_historico.pack(fill=tk.BOTH, expand=True)

        # Estado de transcrição
        self.transcrição_ativa = False
        self.transcrição_buffer = []
        self.transcrição_timestamps = []

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

    def _log_validacao(self, motivo, qualidade, diversidade, alerta_diversidade):
        """Log formatado de validação com estatísticas."""
        n = self.amostras_coletadas
        q_media = np.mean(self.estatisticas_coleta["qualidades"][-10:]) if self.estatisticas_coleta["qualidades"] else 0
        d_media = np.mean(self.estatisticas_coleta["diversidades"][-5:]) if self.estatisticas_coleta["diversidades"] else 0

        msg = f"#{n} {motivo} | qualidade={qualidade:.0%}"
        if q_media > 0:
            msg += f" (média={q_media:.0%})"
        msg += f" | diversidade={diversidade:.3f}"

        self._log(msg)

        if alerta_diversidade:
            self._log(alerta_diversidade)

    def _tecla_espaco(self, event=None):
        """Avança para o próximo sinal na coleta dinâmica com segmentação."""
        if self.coletando and self.tipo_coleta == "dinamico":
            if self.seg_estado == "aguardando_espaco":
                self.seg_estado = "aguardando_mao"
                self.seq_buffer = []
                self.seg_frames_sem_mao = 0

    def _aplicar_mao_dominante(self):
        """Atualiza o detector com a mão dominante selecionada."""
        if self.detector:
            self.detector.mao_dominante = self.var_mao_dom.get()
            self._log(f"✋ Mão dominante: {self.detector.mao_dominante}")

    def _apagar_ultimo(self):
        c = self.txt.get("1.0", tk.END).rstrip("\n")
        if c:
            self.txt.delete("1.0", tk.END)
            self.txt.insert("1.0", c[:-1])

    def _atualizar_status_tensorflow(self):
        ok, status = verificar_tensorflow()
        self.lbl_tf_status.configure(text=f"TensorFlow: {status}", foreground=COR_GREEN if ok else COR_RED)
        self.btn_treinar_din.configure(state=tk.NORMAL if ok else tk.DISABLED)

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

        # Reseta estado de segmentação automática
        self.seg_estado = "aguardando_espaco"
        self.seg_frames_sem_mao = 0

        # Reseta buffer e estatísticas
        self.buffer_ultimas_amostras = []
        self.estatisticas_coleta = {
            "total_validas": 0,
            "total_rejeitadas": 0,
            "qualidades": [],
            "diversidades": []
        }

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
            self.after(0, self._atualizar_classes)
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
        rotulos_prioritarios, peso_local, min_amostras = self._config_treino_hibrido()

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
                    min_amostras_por_classe=min_amostras,
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
        rotulos_prioritarios, peso_local, min_amostras = self._config_treino_hibrido()

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
                    min_amostras_por_classe=min_amostras,
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
        tem_modelo_din = (
            self.modelos.modelo_dinamico_rf is not None or
            self.modelos.modelo_dinamico is not None
        )
        if modo in ("dinamico", "ambos") and not tem_modelo_din:
            messagebox.showwarning("Aviso", "Treine o modelo dinâmico primeiro.")
            return

        self.reconhecendo = True
        self.hold_pred = ""
        self.hold_start = 0.0
        self.seq_rec = []
        self.hand_was_visible = False

        self.btn_start_rec.configure(state=tk.DISABLED)
        self.btn_stop_rec.configure(state=tk.NORMAL)
        self.lbl_info.configure(text="🔍 Reconhecimento ativo...", foreground=COR_GREEN)
        self._log(f"🔍 Reconhecimento iniciado | modo={modo} | limiar={self.var_conf.get():.2f}")

    def _parar_rec(self):
        self.reconhecendo = False
        self.ultimo_pred = ""
        self.ultima_conf = 0.0
        self.btn_start_rec.configure(state=tk.NORMAL)
        self.btn_stop_rec.configure(state=tk.DISABLED)
        self.lbl_info.configure(text="⏹ Reconhecimento parado.", foreground=COR_YELLOW)
        self.lbl_pred.configure(text="—")
        self._log("⏹ Reconhecimento pausado")

    def _iniciar_transcricao(self):
        """Inicia modo transcrição (reconhecimento + texto em tempo real)."""
        modo = self.var_modo_trans.get()
        if modo in ("dinamico", "ambos") and self.modelos.modelo_dinamico_rf is None and self.modelos.X_train_dtw is None:
            messagebox.showwarning("Aviso", "Treine o modelo dinâmico primeiro.")
            return
        if modo in ("estatico", "ambos") and self.modelos.modelo_estatico is None:
            messagebox.showwarning("Aviso", "Treine o modelo estático primeiro.")
            return

        self.transcrição_ativa = True
        self.transcrição_buffer = []
        self.transcrição_timestamps = []

        self.btn_trans_start.configure(state=tk.DISABLED)
        self.btn_trans_stop.configure(state=tk.NORMAL)
        self.txt_trans.configure(state=tk.NORMAL)
        self.txt_trans.delete("1.0", tk.END)
        self.txt_trans.configure(state=tk.DISABLED)

        self._iniciar_rec()
        self._log(f"✍️ Transcrição iniciada | modo={modo}")

    def _parar_transcricao(self):
        """Para transcrição e mostra resultado final."""
        self.transcrição_ativa = False
        self._parar_rec()

        self.btn_trans_start.configure(state=tk.NORMAL)
        self.btn_trans_stop.configure(state=tk.DISABLED)

        self._log(f"✍️ Transcrição parada | {len(self.transcrição_buffer)} gestos capturados")

    def _atualizar_transcricao(self, sinal, confianca):
        """Atualiza texto de transcrição quando um sinal é reconhecido."""
        if not self.transcrição_ativa:
            return

        self.transcrição_buffer.append(sinal)
        self.transcrição_timestamps.append(datetime.now())

        # Atualizar texto principal
        self.txt_trans.configure(state=tk.NORMAL)
        texto_atual = self.txt_trans.get("1.0", tk.END).strip()
        novo_texto = (texto_atual + " " + sinal).strip()
        self.txt_trans.delete("1.0", tk.END)
        self.txt_trans.insert("1.0", novo_texto)
        self.txt_trans.see(tk.END)
        self.txt_trans.configure(state=tk.DISABLED)

        # Atualizar histórico (últimos 10)
        histórico = self.transcrição_buffer[-10:]
        self.txt_historico.configure(state=tk.NORMAL)
        self.txt_historico.delete("1.0", tk.END)
        for i, (sig, ts) in enumerate(zip(histórico, self.transcrição_timestamps[-10:])):
            timestamp_str = ts.strftime("%H:%M:%S")
            self.txt_historico.insert(tk.END, f"{i+1}. [{timestamp_str}] {sig}\n")
        self.txt_historico.configure(state=tk.DISABLED)

    def _salvar_transcricao(self):
        """Salva transcrição como arquivo de texto."""
        if not self.transcrição_buffer:
            messagebox.showwarning("Aviso", "Nenhuma transcrição para salvar.")
            return

        conteudo = " ".join(self.transcrição_buffer)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        arquivo = f"transcricao_{timestamp}.txt"

        try:
            with open(arquivo, "w", encoding="utf-8") as f:
                f.write(f"Transcrição LIBRAS → Português\n")
                f.write(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Gestos reconhecidos: {len(self.transcrição_buffer)}\n")
                f.write("─" * 50 + "\n\n")
                f.write(conteudo + "\n\n")
                f.write("─" * 50 + "\n")
                f.write("Histórico detalhado:\n")
                for i, (sig, ts) in enumerate(zip(self.transcrição_buffer, self.transcrição_timestamps)):
                    f.write(f"{i+1}. [{ts.strftime('%H:%M:%S')}] {sig}\n")

            messagebox.showinfo("Sucesso", f"Transcrição salva em:\n{arquivo}")
            self._log(f"💾 Transcrição salva: {arquivo}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar: {e}")

    def _limpar_transcricao(self):
        """Limpa buffer de transcrição."""
        if messagebox.askyesno("Confirmar", "Limpar transcrição?"):
            self.transcrição_buffer = []
            self.transcrição_timestamps = []
            self.txt_trans.configure(state=tk.NORMAL)
            self.txt_trans.delete("1.0", tk.END)
            self.txt_trans.configure(state=tk.DISABLED)
            self.txt_historico.configure(state=tk.NORMAL)
            self.txt_historico.delete("1.0", tk.END)
            self.txt_historico.configure(state=tk.DISABLED)
            self._log("🗑 Transcrição limpa")

    def _confirmar_pred_direta(self, pred, conf):
        """Confirmação imediata para gestos dinâmicos (disparada ao fim do gesto)."""
        self.ultimo_pred = pred
        self.ultima_conf = conf
        self._set_pred_label(pred, conf)
        self.txt.insert(tk.END, pred + " ")
        self.txt.see(tk.END)

        # Atualizar transcrição se ativa
        if self.transcrição_ativa:
            self._atualizar_transcricao(pred, conf)

        self.lbl_info.configure(
            text=f"✅ Último gesto: {pred} ({conf:.0%})",
            foreground=COR_GREEN
        )
        self.hold_pred = ""
        self.hold_start = 0.0
        self._debug(f"Gesto dinâmico confirmado: {pred} ({conf:.2%})")

    def _confirmar_pred(self, pred, conf):
        self._set_pred_label(pred, conf)

        now = time.time()
        hold = float(self.var_hold.get())

        if pred == self.hold_pred:
            if now - self.hold_start >= hold:
                self.ultimo_pred = pred
                self.ultima_conf = conf
                self.txt.insert(tk.END, pred + " ")
                self.txt.see(tk.END)

                # Atualizar transcrição se ativa
                if self.transcrição_ativa:
                    self._atualizar_transcricao(pred, conf)

                self.hold_pred = ""
                self.hold_start = 0.0
                self.seq_rec.clear()
                self._debug(f"Predição confirmada: {pred} ({conf:.2%})")
        else:
            self.hold_pred = pred
            self.hold_start = now

    def _set_pred_label(self, pred, conf):
        if conf > 0:
            self.lbl_pred.configure(text=f"{pred} ({conf:.0%})", foreground=COR_GREEN if conf >= 0.8 else COR_YELLOW)
        else:
            self.lbl_pred.configure(text=pred, foreground=COR_FG)

    def _restaurar_ultimo_pred(self):
        """Mantém o último resultado visível quando não há gesto ativo."""
        if self.ultimo_pred:
            self._set_pred_label(self.ultimo_pred, self.ultima_conf)
        else:
            self.lbl_pred.configure(text="—", foreground=COR_FG)

    # ──────────────────────────────────────────────────────────────────────────
    # CÂMERA
    # ──────────────────────────────────────────────────────────────────────────
    def _inicializar_detector(self):
        try:
            self.lbl_cam.configure(text="🔎 Inicializando MediaPipe Holistic...", foreground=COR_YELLOW)
            self._log("🔎 Inicializando MediaPipe Holistic (mãos + pose + rosto)...")
            self.detector = DetectorHolistic(
                debug=self.var_debug.get(),
                log_fn=lambda s: self.after(0, self._log, s),
            )
            # Aplica mão dominante da UI (pode já ter sido selecionada antes do detector existir)
            if hasattr(self, "var_mao_dom"):
                self.detector.mao_dominante = self.var_mao_dom.get()
            self._log(f"✅ Holistic pronto — {TOTAL_FEATURES} features por frame "
                      f"(mãos={FEATURES_MAOS}, pose={FEATURES_POSE}) | "
                      f"mão dominante: {self.detector.mao_dominante}")
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

                tem_mao = self.detector.tem_mao(res)

                # COLETA
                if self.coletando:
                    if self.tipo_coleta == "estatico":
                        # Estático: captura frame a frame enquanto há mão
                        if tem_mao:
                            self.dados.salvar_estatico(self.rotulo_coleta, feats)
                            self.amostras_coletadas += 1
                            self.after(0, self._atualizar_progresso_overlay)
                            if self.amostras_coletadas >= self.amostras_alvo:
                                self.after(0, self._finalizar_coleta)
                    else:
                        # Dinâmico: segmentação automática com confirmação por ESPAÇO
                        if self.seg_estado == "aguardando_espaco":
                            pass  # aguarda tecla Espaço — tratado em _tecla_espaco

                        elif self.seg_estado == "aguardando_mao":
                            if tem_mao:
                                self.seg_estado = "gravando"
                                self.seq_buffer = []
                                self.seg_frames_sem_mao = 0

                        elif self.seg_estado == "gravando":
                            if tem_mao:
                                self.seg_frames_sem_mao = 0
                                self.seq_buffer.append(feats)
                            else:
                                self.seg_frames_sem_mao += 1
                                if self.seg_frames_sem_mao >= self.SEG_FRAMES_PAUSA:
                                    # Sinal terminou: VALIDA antes de salvar
                                    seq = np.array(self.seq_buffer, dtype=np.float32)

                                    # VALIDAÇÃO DE QUALIDADE
                                    valida, motivo, qualidade = self.modelos._validar_amostra_dinamica(seq)

                                    if valida:
                                        # CALCULA DIVERSIDADE
                                        self.buffer_ultimas_amostras.append(seq.copy())
                                        if len(self.buffer_ultimas_amostras) > 5:
                                            self.buffer_ultimas_amostras.pop(0)

                                        diversidade, alerta_div = self.modelos._calcular_diversidade(
                                            self.buffer_ultimas_amostras
                                        )

                                        # SALVA
                                        self.dados.salvar_dinamico(self.rotulo_coleta, seq)
                                        self.amostras_coletadas += 1

                                        # STATS
                                        self.estatisticas_coleta["total_validas"] += 1
                                        self.estatisticas_coleta["qualidades"].append(qualidade)
                                        self.estatisticas_coleta["diversidades"].append(diversidade)

                                        # FEEDBACK
                                        self.after(0, lambda m=motivo, q=qualidade, d=diversidade, a=alerta_div:
                                            self._log_validacao(m, q, d, a))
                                        self.after(0, self._atualizar_progresso_overlay)

                                        if self.amostras_coletadas >= self.amostras_alvo:
                                            self.after(0, self._finalizar_coleta)
                                    else:
                                        # REJEITADA
                                        self.estatisticas_coleta["total_rejeitadas"] += 1
                                        self.after(0, lambda m=motivo, q=qualidade:
                                            self._log(f"❌ Amostra rejeitada: {m} ({q:.0%})"))

                                    self.seq_buffer = []
                                    self.seg_estado = "aguardando_espaco"
                                    self.seg_frames_sem_mao = 0

                # RECONHECIMENTO
                if self.reconhecendo:
                    lim = float(self.var_conf.get())
                    modo = self.var_modo.get()

                    pred, conf = None, 0.0

                    if tem_mao:
                        # Mão apareceu agora: zera o buffer para começar gesto limpo
                        if not self.hand_was_visible:
                            self.seq_rec = []
                        self.hand_was_visible = True

                        if modo in ("estatico", "ambos"):
                            p, c = self.modelos.prever_estatico(feats)
                            if p and c >= lim:
                                pred, conf = p, c

                        if modo in ("dinamico", "ambos"):
                            self.seq_rec.append(feats)

                        if pred:
                            self.after(0, lambda p=pred, c=conf: self._confirmar_pred(p, c))
                        else:
                            self.after(0, self._restaurar_ultimo_pred)

                        if self.var_debug.get() and (time.time() - self.last_log_rec) > 2.0:
                            self.last_log_rec = time.time()
                            self.after(0, self._log, f"[DEBUG] Reconhecendo | modo={modo} | frames={len(self.seq_rec)}")

                    else:
                        # Mão saiu: se estava visível e temos frames suficientes → predizer agora
                        fez_predicao = False
                        if self.hand_was_visible and modo in ("dinamico", "ambos"):
                            if len(self.seq_rec) >= MIN_DYNAMIC_FRAMES:
                                seq = np.array(self.seq_rec[-SEQUENCE_LENGTH:], dtype=np.float32)
                                p, c = self.modelos.prever_dinamico(seq)
                                lim_din = max(0.15, lim * 0.4)
                                if p and c >= lim_din:
                                    self.after(0, lambda p=p, c=c: self._confirmar_pred_direta(p, c))
                                    fez_predicao = True
                                else:
                                    self.after(0, lambda p=p, c=c: self._set_pred_label(f"{p}?", c))
                                    fez_predicao = True
                                if self.var_debug.get():
                                    self.after(0, self._log, f"[DEBUG] Gesto: '{p}' ({c:.1%}) | {len(self.seq_rec)} frames")
                            self.seq_rec = []

                        self.hand_was_visible = False
                        if not fez_predicao:
                            self.after(0, self._restaurar_ultimo_pred)

                if self.coletando:
                    if self.tipo_coleta == "estatico":
                        cor = (0, 255, 0) if tem_mao else (0, 0, 255)
                        texto = f"ESTATICO | {self.rotulo_coleta} | {self.amostras_coletadas}/{self.amostras_alvo}"
                        cv2.putText(frame, texto, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75, cor, 2)
                    else:
                        # Dinâmico: overlay por estado
                        h, w = frame.shape[:2]
                        if self.seg_estado == "aguardando_espaco":
                            cv2.rectangle(frame, (0, 0), (w-1, h-1), (200, 200, 0), 4)
                            cv2.putText(frame, "Pressione ESPACO para gravar",
                                        (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 220, 220), 2)
                        elif self.seg_estado == "aguardando_mao":
                            cv2.rectangle(frame, (0, 0), (w-1, h-1), (0, 200, 0), 4)
                            cv2.putText(frame, "Mostre as maos e faca o sinal!",
                                        (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 220, 0), 2)
                        elif self.seg_estado == "gravando":
                            cv2.rectangle(frame, (0, 0), (w-1, h-1), (0, 0, 220), 6)
                            cv2.putText(frame, f"GRAVANDO  {len(self.seq_buffer)} frames",
                                        (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                        cv2.putText(frame,
                                    f"{self.rotulo_coleta}  {self.amostras_coletadas}/{self.amostras_alvo}",
                                    (10, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)

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
    print(f"Features: {TOTAL_FEATURES} (mãos={FEATURES_MAOS}, pose={FEATURES_POSE})")
    print("=" * 70)

    app = LibrasApp()
    app.mainloop()
