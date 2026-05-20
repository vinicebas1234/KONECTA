#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" 
╔══════════════════════════════════════════════════════════════════════╗
║         SISTEMA DE RECONHECIMENTO DE LIBRAS — TCC                  ║
║  Visão Computacional + Machine Learning + Interface (Tkinter)       ║
╚══════════════════════════════════════════════════════════════════════╝

✅ Atualização (solicitada):
- Campo de texto para definir o NOME do sinal/ letra/ número (rótulo)
- Ao iniciar a coleta, o sistema PERGUNTA se o sinal é ESTÁTICO ou DINÂMICO
- Cria automaticamente a pasta da classe no local correto
- Base do projeto fixa em: C:\\KONECTA\\OCR\\

Instalação:
    pip install opencv-python mediapipe numpy scikit-learn pillow tensorflow

Execução:
    python libras_recognizer.py

Obs.: TensorFlow é opcional. Sem ele, o modo dinâmico fica desativado.
"""

# ═══════════════════════════════════════════════════════════════════════
#  IMPORTAÇÕES
# ═══════════════════════════════════════════════════════════════════════
import cv2
import mediapipe as mp
import numpy as np
import os
import pickle
import threading
import time
from collections import deque
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from PIL import Image, ImageTk

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder

from mediapipe.tasks import python
from mediapipe.tasks.python import vision


try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.utils import to_categorical
    from tensorflow.keras.callbacks import EarlyStopping
    TF_DISPONIVEL = True
except Exception:
    TF_DISPONIVEL = False

# ═══════════════════════════════════════════════════════════════════════
#  CONFIGURAÇÕES (PASTA BASE DO PROJETO)
# ═══════════════════════════════════════════════════════════════════════

# ✅ Caminho base pedido pelo usuário
BASE_DIR = r"C:\KONECTA\OCR"

# Estrutura interna
DIR_DADOS     = os.path.join(BASE_DIR, "dados_libras")
DIR_ESTATICOS = os.path.join(DIR_DADOS, "estaticos")
DIR_DINAMICOS = os.path.join(DIR_DADOS, "dinamicos")
DIR_MODELOS   = os.path.join(BASE_DIR, "modelos")

# MediaPipe
MP_MAX_HANDS      = 2
MP_DET_CONF       = 0.7
MP_TRK_CONF       = 0.5

# Sequências (dinâmico)
SEQUENCE_LENGTH   = 30

# Câmera
CAM_INDEX         = 0
CAM_WIDTH         = 640
CAM_HEIGHT        = 480

# Features
FEATURES_PER_HAND = 21 * 3  # 63
TOTAL_FEATURES    = FEATURES_PER_HAND * MP_MAX_HANDS  # 126

# Tema (Catppuccin Mocha)
COR_BG       = "#1e1e2e"
COR_BG2      = "#313244"
COR_BG3      = "#45475a"
COR_FG       = "#cdd6f4"
COR_ACCENT   = "#89b4fa"
COR_GREEN    = "#a6e3a1"
COR_RED      = "#f38ba8"
COR_YELLOW   = "#f9e2af"
COR_LAVENDER = "#b4befe"
COR_PEACH    = "#fab387"


# ═══════════════════════════════════════════════════════════════════════
#  DETECTOR DE MÃOS (MediaPipe)
# ═══════════════════════════════════════════════════════════════════════


class DetectorMaos:
    """Detector de mãos e extrator de features (landmarks normalizados) usando MediaPipe Tasks (HandLandmarker)."""

    def __init__(self):
        # ✅ Modelo .task (precisa existir neste caminho)
        # Ex.: C:\KONECTA\OCR\modelos\hand_landmarker.task
        self.model_path = os.path.join(DIR_MODELOS, "hand_landmarker.task")

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Modelo não encontrado: {self.model_path}\n"
                f"Baixe o 'hand_landmarker.task' e coloque em {DIR_MODELOS}."
            )

        # ✅ Cria o HandLandmarker (Tasks API)
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=MP_MAX_HANDS
            # Você pode acrescentar thresholds aqui se quiser:
            # min_hand_detection_confidence=MP_DET_CONF,
            # min_tracking_confidence=MP_TRK_CONF,
        )
        self.detector = vision.HandLandmarker.create_from_options(options)  # create_from_options é o padrão oficial [3](blob:https://m365.cloud.microsoft/73dd7e17-92e9-462b-a271-7e3b816376f9)

        # ✅ Utilitários de desenho do Tasks (seguindo o exemplo oficial)
        self.mp_hands = mp.tasks.vision.HandLandmarksConnections
        self.mp_draw = mp.tasks.vision.drawing_utils
        self.mp_style = mp.tasks.vision.drawing_styles  # drawing_styles aparece nos exemplos oficiais [4](https://pypi.org/project/mediapipe/)[5](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/python/solutions/hands.py)

    def processar(self, frame_bgr):
        # BGR -> RGB
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # ✅ Converte para mp.Image e detecta com HandLandmarker
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        result = self.detector.detect(mp_image)  # detect() é o fluxo padrão do Tasks API [2](https://blog.csdn.net/ObsidianRaven13/article/details/156684217)[5](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/python/solutions/hands.py)
        return result

    def desenhar(self, frame_bgr, result):
        # desenhar em RGB e voltar para BGR
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

    def extrair_features(self, result):
        """Retorna vetor 126 (2 mãos). Se não houver mão: zeros."""
        feats = np.zeros(TOTAL_FEATURES, dtype=np.float32)

        if not result.hand_landmarks:
            return feats

        # result.hand_landmarks: lista de mãos; cada mão tem 21 landmarks (x,y,z) [2](https://blog.csdn.net/ObsidianRaven13/article/details/156684217)[3](blob:https://m365.cloud.microsoft/73dd7e17-92e9-462b-a271-7e3b816376f9)
        for idx, hand in enumerate(result.hand_landmarks):
            if idx >= MP_MAX_HANDS:
                break

            pts = np.array([[lm.x, lm.y, lm.z] for lm in hand], dtype=np.float32)

            # Normalização: centralizar no pulso (0) e escalar
            center = pts[0].copy()
            pts = pts - center
            m = np.max(np.abs(pts))
            if m > 0:
                pts = pts / m

            start = idx * FEATURES_PER_HAND
            end = start + FEATURES_PER_HAND
            feats[start:end] = pts.flatten()

        return feats

    def liberar(self):
        # ✅ Tasks usa close()
        try:
            self.detector.close()
        except Exception:
            pass



# ═══════════════════════════════════════════════════════════════════════
#  GERENCIADOR DE DADOS
# ═══════════════════════════════════════════════════════════════════════

class GerenciadorDados:
    """Cria pastas e salva/ carrega amostras estáticas e dinâmicas."""

    def __init__(self):
        for d in [BASE_DIR, DIR_DADOS, DIR_ESTATICOS, DIR_DINAMICOS, DIR_MODELOS]:
            os.makedirs(d, exist_ok=True)

    def _pasta_classe(self, tipo, rotulo):
        if tipo == "estatico":
            return os.path.join(DIR_ESTATICOS, rotulo)
        return os.path.join(DIR_DINAMICOS, rotulo)

    def garantir_classe(self, tipo, rotulo):
        """Cria a pasta da classe imediatamente."""
        pasta = self._pasta_classe(tipo, rotulo)
        os.makedirs(pasta, exist_ok=True)
        return pasta

    # ─── Salvar ───────────────────────────────────────────────────────
    def salvar_estatico(self, rotulo, features):
        pasta = self.garantir_classe("estatico", rotulo)
        idx = len([f for f in os.listdir(pasta) if f.endswith('.npy')])
        np.save(os.path.join(pasta, f"{idx:04d}.npy"), features)

    def salvar_dinamico(self, rotulo, sequencia):
        pasta = self.garantir_classe("dinamico", rotulo)
        idx = len([f for f in os.listdir(pasta) if f.endswith('.npy')])
        np.save(os.path.join(pasta, f"{idx:04d}.npy"), np.array(sequencia, dtype=np.float32))

    # ─── Carregar ─────────────────────────────────────────────────────
    def carregar_estaticos(self):
        X, y = [], []
        if not os.path.exists(DIR_ESTATICOS):
            return np.array(X), np.array(y)

        for rotulo in sorted(os.listdir(DIR_ESTATICOS)):
            pasta = os.path.join(DIR_ESTATICOS, rotulo)
            if not os.path.isdir(pasta):
                continue
            for arq in os.listdir(pasta):
                if arq.endswith('.npy'):
                    X.append(np.load(os.path.join(pasta, arq)))
                    y.append(rotulo)
        return np.array(X), np.array(y)

    def carregar_dinamicos(self):
        X, y = [], []
        if not os.path.exists(DIR_DINAMICOS):
            return np.array(X), np.array(y)

        for rotulo in sorted(os.listdir(DIR_DINAMICOS)):
            pasta = os.path.join(DIR_DINAMICOS, rotulo)
            if not os.path.isdir(pasta):
                continue
            for arq in os.listdir(pasta):
                if arq.endswith('.npy'):
                    X.append(np.load(os.path.join(pasta, arq)))
                    y.append(rotulo)
        return (np.array(X) if X else np.array(X)), np.array(y)

    # ─── Listagem/Exclusão ─────────────────────────────────────────────
    def listar_classes(self):
        out = {"estatico": {}, "dinamico": {}}
        if os.path.exists(DIR_ESTATICOS):
            for rotulo in sorted(os.listdir(DIR_ESTATICOS)):
                pasta = os.path.join(DIR_ESTATICOS, rotulo)
                if os.path.isdir(pasta):
                    out["estatico"][rotulo] = len([f for f in os.listdir(pasta) if f.endswith('.npy')])
        if os.path.exists(DIR_DINAMICOS):
            for rotulo in sorted(os.listdir(DIR_DINAMICOS)):
                pasta = os.path.join(DIR_DINAMICOS, rotulo)
                if os.path.isdir(pasta):
                    out["dinamico"][rotulo] = len([f for f in os.listdir(pasta) if f.endswith('.npy')])
        return out

    def deletar_classe(self, tipo, rotulo):
        import shutil
        pasta = self._pasta_classe(tipo, rotulo)
        if os.path.exists(pasta):
            shutil.rmtree(pasta)


# ═══════════════════════════════════════════════════════════════════════
#  GERENCIADOR DE MODELOS
# ═══════════════════════════════════════════════════════════════════════

class GerenciadorModelos:
    """Treino, inferência e persistência dos modelos estático/dinâmico."""

    def __init__(self):
        self.modelo_estatico = None
        self.encoder_estatico = None
        self.modelo_dinamico = None
        self.encoder_dinamico = None
        self._carregar_estatico()
        self._carregar_dinamico()

    # ─── Estático (RandomForest) ───────────────────────────────────────
    def treinar_estatico(self, X, y, log=None):
        if len(X) == 0:
            return "❌ Nenhuma amostra estática encontrada." 

        enc = LabelEncoder()
        y_enc = enc.fit_transform(y)

        Xtr, Xte, ytr, yte = train_test_split(X, y_enc, test_size=0.2, random_state=42, stratify=y_enc)

        if log:
            log("🔄 Treinando RandomForest (estático)...")

        mdl = RandomForestClassifier(n_estimators=250, max_depth=25, random_state=42, n_jobs=-1)
        mdl.fit(Xtr, ytr)

        pred = mdl.predict(Xte)
        acc = accuracy_score(yte, pred)
        report = classification_report(yte, pred, target_names=enc.classes_, zero_division=0)

        self.modelo_estatico = mdl
        self.encoder_estatico = enc

        with open(os.path.join(DIR_MODELOS, "modelo_estatico.pkl"), "wb") as f:
            pickle.dump(mdl, f)
        with open(os.path.join(DIR_MODELOS, "encoder_estatico.pkl"), "wb") as f:
            pickle.dump(enc, f)

        return (
            "✅ MODELO ESTÁTICO TREINADO\n" +
            f"Acurácia: {acc:.2%}\n" +
            "─"*50 + "\n" +
            report
        )

    def prever_estatico(self, features):
        if self.modelo_estatico is None or self.encoder_estatico is None:
            return None, 0.0
        proba = self.modelo_estatico.predict_proba(features.reshape(1, -1))[0]
        i = int(np.argmax(proba))
        return self.encoder_estatico.classes_[i], float(proba[i])

    def _carregar_estatico(self):
        m = os.path.join(DIR_MODELOS, "modelo_estatico.pkl")
        e = os.path.join(DIR_MODELOS, "encoder_estatico.pkl")
        if os.path.exists(m) and os.path.exists(e):
            with open(m, "rb") as f:
                self.modelo_estatico = pickle.load(f)
            with open(e, "rb") as f:
                self.encoder_estatico = pickle.load(f)

    # ─── Dinâmico (LSTM) ───────────────────────────────────────────────
    def treinar_dinamico(self, X, y, log=None):
        if not TF_DISPONIVEL:
            return "❌ TensorFlow não instalado. Instale com: pip install tensorflow"
        if len(X) == 0:
            return "❌ Nenhuma amostra dinâmica encontrada." 

        enc = LabelEncoder()
        y_enc = enc.fit_transform(y)
        n_classes = len(enc.classes_)
        y_cat = to_categorical(y_enc, n_classes)

        Xtr, Xte, ytr, yte, ytr_s, yte_s = train_test_split(
            X, y_cat, y_enc, test_size=0.2, random_state=42, stratify=y_enc
        )

        if log:
            log("🔄 Treinando LSTM (dinâmico)...")

        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=(SEQUENCE_LENGTH, TOTAL_FEATURES)),
            Dropout(0.25),
            LSTM(128),
            Dropout(0.25),
            Dense(64, activation="relu"),
            Dropout(0.25),
            Dense(n_classes, activation="softmax"),
        ])
        model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])

        es = EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True)
        hist = model.fit(Xtr, ytr, epochs=80, batch_size=32, validation_data=(Xte, yte), callbacks=[es], verbose=0)

        loss, acc = model.evaluate(Xte, yte, verbose=0)
        pred = np.argmax(model.predict(Xte, verbose=0), axis=1)
        report = classification_report(yte_s, pred, target_names=enc.classes_, zero_division=0)

        self.modelo_dinamico = model
        self.encoder_dinamico = enc

        model.save(os.path.join(DIR_MODELOS, "modelo_dinamico.keras"))
        with open(os.path.join(DIR_MODELOS, "encoder_dinamico.pkl"), "wb") as f:
            pickle.dump(enc, f)

        return (
            "✅ MODELO DINÂMICO TREINADO\n" +
            f"Acurácia: {acc:.2%} | Épocas: {len(hist.history['loss'])}\n" +
            "─"*50 + "\n" +
            report
        )

    def prever_dinamico(self, sequencia):
        if self.modelo_dinamico is None or self.encoder_dinamico is None:
            return None, 0.0
        x = np.array(sequencia, dtype=np.float32).reshape(1, SEQUENCE_LENGTH, TOTAL_FEATURES)
        proba = self.modelo_dinamico.predict(x, verbose=0)[0]
        i = int(np.argmax(proba))
        return self.encoder_dinamico.classes_[i], float(proba[i])

    def _carregar_dinamico(self):
        if not TF_DISPONIVEL:
            return
        m = os.path.join(DIR_MODELOS, "modelo_dinamico.keras")
        e = os.path.join(DIR_MODELOS, "encoder_dinamico.pkl")
        if os.path.exists(m) and os.path.exists(e):
            self.modelo_dinamico = load_model(m)
            with open(e, "rb") as f:
                self.encoder_dinamico = pickle.load(f)


# ═══════════════════════════════════════════════════════════════════════
#  APP (Tkinter)
# ═══════════════════════════════════════════════════════════════════════

class LibrasApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("🤟 Libras OCR — TCC")
        self.geometry("1280x800")
        self.minsize(1100, 700)
        self.configure(bg=COR_BG)

        self.detector = DetectorMaos()
        self.dados = GerenciadorDados()
        self.modelos = GerenciadorModelos()

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

        self._aplicar_estilo()
        self._ui()
        self._iniciar_camera()
        self.protocol("WM_DELETE_WINDOW", self._fechar)

    # ─────────────────────────── UI / TEMA ─────────────────────────────
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

        self.txt = scrolledtext.ScrolledText(bottom, height=3, bg=COR_BG2, fg=COR_FG, font=("Consolas", 14), insertbackground=COR_FG, wrap=tk.WORD)
        self.txt.pack(fill=tk.X, side=tk.LEFT, expand=True)

        btns = ttk.Frame(bottom)
        btns.pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(btns, text="🗑 Limpar", style="Danger.TButton", command=lambda: self.txt.delete("1.0", tk.END)).pack(pady=2)
        ttk.Button(btns, text="⬅ Apagar", command=self._apagar_ultimo).pack(pady=2)
        ttk.Button(btns, text="␣ Espaço", command=lambda: self.txt.insert(tk.END, " ")).pack(pady=2)

    # ─────────────────────────── ABAS ──────────────────────────────────
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

    def _aba_treino(self):
        aba = ttk.Frame(self.nb, padding=15)
        self.nb.add(aba, text="🧠 Treino")

        bar = ttk.Frame(aba)
        bar.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(bar, text="🏋 Treinar Estático", style="Accent.TButton", command=self._treinar_estatico).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text="🏋 Treinar Dinâmico", style="Green.TButton", command=self._treinar_dinamico).pack(side=tk.LEFT, padx=5)

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

    # ─────────────────────────── UTIL ──────────────────────────────────
    def _log(self, s):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, s + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _apagar_ultimo(self):
        c = self.txt.get("1.0", tk.END).rstrip("\n")
        if c:
            self.txt.delete("1.0", tk.END)
            self.txt.insert("1.0", c[:-1])

    # ─────────────────────────── POPUP TIPO ────────────────────────────
    def _perguntar_tipo(self):
        """Pergunta se o sinal é estático ou dinâmico (modal simples)."""
        win = tk.Toplevel(self)
        win.title("Tipo do sinal")
        win.configure(bg=COR_BG)
        win.resizable(False, False)
        win.grab_set()  # modal

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

    # ─────────────────────────── COLETA ────────────────────────────────
    def _iniciar_coleta(self):
        rotulo = self.entry_rotulo.get().strip().upper()
        if not rotulo:
            messagebox.showwarning("Aviso", "Digite o nome do sinal (rótulo).")
            return

        tipo = self._perguntar_tipo()
        if tipo is None:
            return

        if tipo == "dinamico" and not TF_DISPONIVEL:
            messagebox.showwarning("Aviso", "TensorFlow não instalado. Coleta dinâmica até pode salvar, mas treino dinâmico ficará desativado.")

        # ✅ cria a pasta automaticamente no lugar correto
        pasta = self.dados.garantir_classe(tipo, rotulo)

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

    def _parar_coleta(self):
        self.coletando = False
        self.btn_start_collect.configure(state=tk.NORMAL)
        self.btn_stop_collect.configure(state=tk.DISABLED)
        self.lbl_prog.configure(text=f"⏹ Coleta parada — {self.amostras_coletadas} amostras")
        self._atualizar_classes()

    def _finalizar_coleta(self):
        self.coletando = False
        self.btn_start_collect.configure(state=tk.NORMAL)
        self.btn_stop_collect.configure(state=tk.DISABLED)
        self.lbl_prog.configure(text=f"✅ Coleta concluída: {self.rotulo_coleta} ({self.tipo_coleta}) — {self.amostras_coletadas} amostras")
        self._atualizar_classes()
        messagebox.showinfo("Concluído", f"✅ {self.amostras_coletadas} amostras salvas para '{self.rotulo_coleta}' ({self.tipo_coleta}).")

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

    # ─────────────────────────── TREINO ────────────────────────────────
    def _treinar_estatico(self):
        def job():
            X, y = self.dados.carregar_estaticos()
            self.after(0, self._log, f"📊 Estáticos: {len(X)} amostras")
            r = self.modelos.treinar_estatico(X, y, log=lambda s: self.after(0, self._log, s))
            self.after(0, self._log, r)
        self._log("\n" + "═"*60)
        self._log("🏋 Treinamento ESTÁTICO")
        self._log("═"*60)
        threading.Thread(target=job, daemon=True).start()

    def _treinar_dinamico(self):
        def job():
            X, y = self.dados.carregar_dinamicos()
            self.after(0, self._log, f"📊 Dinâmicos: {len(X)} amostras")
            r = self.modelos.treinar_dinamico(X, y, log=lambda s: self.after(0, self._log, s))
            self.after(0, self._log, r)
        self._log("\n" + "═"*60)
        self._log("🏋 Treinamento DINÂMICO")
        self._log("═"*60)
        threading.Thread(target=job, daemon=True).start()

    # ─────────────────────────── RECONHECIMENTO ─────────────────────────
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

    def _parar_rec(self):
        self.reconhecendo = False
        self.btn_start_rec.configure(state=tk.NORMAL)
        self.btn_stop_rec.configure(state=tk.DISABLED)
        self.lbl_info.configure(text="⏹ Reconhecimento parado.", foreground=COR_YELLOW)
        self.lbl_pred.configure(text="—")

    def _confirmar_pred(self, pred, conf):
        """Confirma por tempo: se manter a mesma classe por X segundos, adiciona ao texto."""
        self._set_pred_label(pred, conf)

        now = time.time()
        hold = float(self.var_hold.get())

        if pred == self.hold_pred:
            if now - self.hold_start >= hold:
                self.txt.insert(tk.END, pred)
                self.txt.see(tk.END)
                self.hold_pred = ""
                self.hold_start = 0.0
        else:
            self.hold_pred = pred
            self.hold_start = now

    def _set_pred_label(self, pred, conf):
        if conf > 0:
            self.lbl_pred.configure(text=f"{pred} ({conf:.0%})", foreground=COR_GREEN if conf >= 0.8 else COR_YELLOW)
        else:
            self.lbl_pred.configure(text=pred, foreground=COR_FG)

    # ─────────────────────────── CÂMERA ────────────────────────────────
    def _iniciar_camera(self):
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
        """Loop: captura -> MediaPipe -> (coleta / reconhecimento) -> exibição."""
        while self.camera_rodando:
            ok, frame = self.camera.read()
            if not ok:
                continue

            frame = cv2.flip(frame, 1)
            res = self.detector.processar(frame)
            feats = self.detector.extrair_features(res)
            frame = self.detector.desenhar(frame, res)

            tem_mao = bool(res.hand_landmarks)

            # ───────────── COLETA (ENSINO) ─────────────
            if self.coletando and tem_mao:
                if self.tipo_coleta == "estatico":
                    self.dados.salvar_estatico(self.rotulo_coleta, feats)
                    self.amostras_coletadas += 1
                else:
                    self.seq_buffer.append(feats)
                    if len(self.seq_buffer) == SEQUENCE_LENGTH:
                        self.dados.salvar_dinamico(self.rotulo_coleta, self.seq_buffer)
                        self.seq_buffer = []
                        self.amostras_coletadas += 1

                self.after(0, lambda: self._atualizar_progresso_overlay(frame))

                if self.amostras_coletadas >= self.amostras_alvo:
                    self.after(0, self._finalizar_coleta)

            # ───────────── RECONHECIMENTO (TRADUÇÃO) ─────────────
            if self.reconhecendo:
                lim = float(self.var_conf.get())
                modo = self.var_modo.get()

                pred, conf = None, 0.0

                if tem_mao:
                    # Estático
                    if modo in ("estatico", "ambos"):
                        p, c = self.modelos.prever_estatico(feats)
                        if p and c >= lim:
                            pred, conf = p, c

                    # Dinâmico
                    if modo in ("dinamico", "ambos"):
                        self.seq_rec.append(feats)
                        if len(self.seq_rec) >= SEQUENCE_LENGTH:
                            seq = self.seq_rec[-SEQUENCE_LENGTH:]
                            p, c = self.modelos.prever_dinamico(seq)
                            if p and c >= lim and c > conf:
                                pred, conf = p, c

                    if pred:
                        self.after(0, lambda p=pred, c=conf: self._confirmar_pred(p, c))
                    else:
                        self.after(0, lambda: self._set_pred_label("...", 0.0))
                else:
                    self.seq_rec = []
                    self.after(0, lambda: self._set_pred_label("—", 0.0))

            # Overlay de info da coleta
            if self.coletando:
                color = (0, 255, 0) if tem_mao else (0, 0, 255)
                cv2.putText(frame,
                            f"Coleta: {self.rotulo_coleta} ({self.tipo_coleta}) {self.amostras_coletadas}/{self.amostras_alvo}",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)

            # Exibir no Tk
            self.after(0, lambda fr=frame: self._exibir(fr))
            time.sleep(0.025)

    def _atualizar_progresso_overlay(self, _frame):
        self.prog["maximum"] = self.amostras_alvo
        self.prog["value"] = self.amostras_coletadas
        self.lbl_prog.configure(text=f"📦 Coletando '{self.rotulo_coleta}' ({self.tipo_coleta}) — {self.amostras_coletadas}/{self.amostras_alvo}")

    def _exibir(self, frame):
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            imgtk = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)
            self.canvas._imgtk = imgtk
        except Exception:
            pass

    # ─────────────────────────── FECHAR ────────────────────────────────
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
            self.detector.liberar()
        except Exception:
            pass

        self.destroy()


if __name__ == "__main__":
    print("="*70)
    print("🤟 Libras OCR — TCC")
    print("Base do projeto:", BASE_DIR)
    print("TensorFlow:", "OK" if TF_DISPONIVEL else "NÃO INSTALADO")
    print("Dados:", DIR_DADOS)
    print("Modelos:", DIR_MODELOS)
    print("="*70)

    app = LibrasApp()
    app.mainloop()
