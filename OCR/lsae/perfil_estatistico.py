#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pilar 1 do LSAE — Conhecimento Estatístico.

Para cada sinal já coletado (estático ou dinâmico), calcula como ele varia
naturalmente entre as amostras reais: posição média, desvio padrão, amplitude,
trajetória, velocidade, aceleração e duração. Isso é o "modelo semântico
básico por sinal" (Etapas 2-3 do documento LSAE) — não um julgamento
linguístico, apenas a distribuição estatística observada nos dados reais.

Funções puras: recebem os mesmos (X, y, meta) que já saem de
GerenciadorDados.carregar_estaticos()/carregar_dinamicos() em
libras_recognizer.py, e não dependem de Tkinter, MediaPipe, TensorFlow ou
OpenCV — só numpy. Isso permite testar e depurar o motor isoladamente,
antes de expor qualquer coisa como MCP (ver "Recomendação de escopo" no
PLANO_GENERALIZACAO.md).

IMPORTANTE: os valores abaixo espelham as constantes de libras_recognizer.py
(FEATURES_PER_HAND, MP_MAX_HANDS, TOTAL_FEATURES, SEQUENCE_LENGTH). Se aquele
arquivo mudar a geometria dos landmarks, atualize aqui também.
"""

import pickle
from pathlib import Path

import numpy as np

FEATURES_PER_HAND = 21 * 3  # 63 (21 landmarks x xyz)
MP_MAX_HANDS = 2
TOTAL_FEATURES = FEATURES_PER_HAND * MP_MAX_HANDS  # 126
SEQUENCE_LENGTH = 30


# ══════════════════════════════════════════════════════════════════════════
# RESAMPLING (só para agregação estatística — não é o pad/crop de treino)
# ══════════════════════════════════════════════════════════════════════════

def resample_sequencia(seq, n_pontos=SEQUENCE_LENGTH):
    """Reamostra uma sequência (n_frames, F) para (n_pontos, F) por
    interpolação linear no tempo, preservando a forma do movimento
    independente de quantos frames o vídeo original tinha."""
    seq = np.asarray(seq, dtype=np.float64)
    if seq.ndim != 2:
        raise ValueError(f"Sequência deve ser 2D (n_frames, F); recebido shape {seq.shape}")
    if seq.shape[0] == 0:
        raise ValueError("Sequência vazia (0 frames) não pode ser reamostrada.")

    n_frames, n_feat = seq.shape
    if n_frames == n_pontos:
        return seq.astype(np.float32)
    if n_frames < 2:
        return np.repeat(seq, n_pontos, axis=0).astype(np.float32)

    t_old = np.linspace(0.0, 1.0, n_frames)
    t_new = np.linspace(0.0, 1.0, n_pontos)

    out = np.empty((n_pontos, n_feat), dtype=np.float64)
    for i in range(n_feat):
        out[:, i] = np.interp(t_new, t_old, seq[:, i])
    return out.astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════
# PERFIL ESTÁTICO (pose única — letras/números)
# ══════════════════════════════════════════════════════════════════════════

def calcular_perfil_estatico(X, y, min_amostras=1):
    """Retorna {rotulo: perfil} onde perfil descreve a pose típica do sinal
    através das amostras reais: média, desvio, mínimo, máximo e amplitude
    (max-min) por dimensão de landmark."""
    perfis = {}
    rotulos = sorted(set(str(r) for r in y))

    for rotulo in rotulos:
        amostras = np.array([np.asarray(x, dtype=np.float32) for x, r in zip(X, y) if str(r) == rotulo])
        if len(amostras) < min_amostras:
            continue

        perfis[rotulo] = {
            "n_amostras": int(len(amostras)),
            "media": amostras.mean(axis=0),
            "std": amostras.std(axis=0),
            "minimo": amostras.min(axis=0),
            "maximo": amostras.max(axis=0),
            "amplitude": amostras.max(axis=0) - amostras.min(axis=0),
        }

    return perfis


# ══════════════════════════════════════════════════════════════════════════
# PERFIL DINÂMICO (sequência — palavras/sinais com movimento)
# ══════════════════════════════════════════════════════════════════════════

def calcular_perfil_dinamico(X, y, n_pontos=SEQUENCE_LENGTH, min_amostras=1, min_frames=4):
    """Retorna {rotulo: perfil} com estatísticas de trajetória, velocidade,
    aceleração, amplitude e duração calculadas sobre as amostras reais do
    sinal (todas reamostradas para n_pontos antes de agregar, para poder
    comparar amostras com número de frames originais diferentes)."""
    perfis = {}
    rotulos = sorted(set(str(r) for r in y))

    for rotulo in rotulos:
        brutas = [np.asarray(x, dtype=np.float32) for x, r in zip(X, y) if str(r) == rotulo]
        brutas = [seq for seq in brutas if seq.ndim == 2 and seq.shape[0] >= min_frames and seq.shape[1] == TOTAL_FEATURES]

        if len(brutas) < min_amostras:
            continue

        duracoes = np.array([seq.shape[0] for seq in brutas], dtype=np.float32)
        reamostradas = np.stack([resample_sequencia(seq, n_pontos) for seq in brutas], axis=0)  # (N, T, F)

        velocidades = np.diff(reamostradas, axis=1)          # (N, T-1, F)
        aceleracoes = np.diff(velocidades, axis=1)            # (N, T-2, F)
        amplitude_por_amostra = brutas_amplitude(brutas)      # (N, F) — no espaço original, sem reamostragem

        perfis[rotulo] = {
            "n_amostras": int(len(brutas)),
            "duracao_media_frames": float(duracoes.mean()),
            "duracao_std_frames": float(duracoes.std()),
            "duracao_min_frames": float(duracoes.min()),
            "duracao_max_frames": float(duracoes.max()),
            "media_trajetoria": reamostradas.mean(axis=0),        # (T, F)
            "std_trajetoria": reamostradas.std(axis=0),            # (T, F)
            "velocidade_media": velocidades.mean(axis=0),          # (T-1, F)
            "velocidade_std": velocidades.std(axis=0),              # (T-1, F)
            "aceleracao_media": aceleracoes.mean(axis=0),          # (T-2, F)
            "aceleracao_std": aceleracoes.std(axis=0),              # (T-2, F)
            "amplitude_media": amplitude_por_amostra.mean(axis=0),  # (F,)
            "amplitude_std": amplitude_por_amostra.std(axis=0),     # (F,)
        }

    return perfis


def brutas_amplitude(sequencias):
    """Amplitude (max-min) por dimensão, calculada dentro de cada amostra
    bruta (sem reamostrar) e empilhada -> (N, F)."""
    return np.stack([seq.max(axis=0) - seq.min(axis=0) for seq in sequencias], axis=0)


# ══════════════════════════════════════════════════════════════════════════
# RESUMOS ESCALARES (para relatórios / diagnóstico humano)
# ══════════════════════════════════════════════════════════════════════════

def velocidade_escalar_media(perfil_sinal):
    """Colapsa velocidade_media (T-1, F) numa única velocidade média escalar,
    calculando a norma L2 por landmark (x,y,z) e tirando a média entre
    landmarks e frames. Serve só para comparar sinais 'rápidos' x 'parados'."""
    vel = perfil_sinal["velocidade_media"]
    n_frames_menos_1, n_feat = vel.shape
    n_landmarks_total = n_feat // 3
    vel_landmarks = vel.reshape(n_frames_menos_1, n_landmarks_total, 3)
    normas = np.linalg.norm(vel_landmarks, axis=2)  # (T-1, n_landmarks_total)
    return float(normas.mean())


def amplitude_escalar_media(perfil_sinal):
    return float(np.mean(perfil_sinal["amplitude_media"]))


def resumo_dinamico(perfis_dinamicos, top_n=10):
    """Retorna um relatório textual: sinais mais rápidos/mais amplos/mais
    curtos, e estatísticas gerais — só para inspeção humana rápida."""
    linhas = []
    linhas.append(f"Sinais dinâmicos com perfil calculado: {len(perfis_dinamicos)}")

    if not perfis_dinamicos:
        return "\n".join(linhas)

    velocidades = {r: velocidade_escalar_media(p) for r, p in perfis_dinamicos.items()}
    amplitudes = {r: amplitude_escalar_media(p) for r, p in perfis_dinamicos.items()}
    duracoes = {r: p["duracao_media_frames"] for r, p in perfis_dinamicos.items()}

    def _topo(d, reverse=True):
        return sorted(d.items(), key=lambda kv: kv[1], reverse=reverse)[:top_n]

    linhas.append(f"\nDuração média geral: {np.mean(list(duracoes.values())):.1f} frames")
    linhas.append(f"Velocidade média geral: {np.mean(list(velocidades.values())):.4f}")
    linhas.append(f"Amplitude média geral: {np.mean(list(amplitudes.values())):.4f}")

    linhas.append(f"\nTop {top_n} sinais mais RÁPIDOS:")
    for r, v in _topo(velocidades):
        linhas.append(f"  {r:30s} vel={v:.4f}")

    linhas.append(f"\nTop {top_n} sinais mais LENTOS:")
    for r, v in _topo(velocidades, reverse=False):
        linhas.append(f"  {r:30s} vel={v:.4f}")

    linhas.append(f"\nTop {top_n} sinais com MAIOR amplitude de movimento:")
    for r, v in _topo(amplitudes):
        linhas.append(f"  {r:30s} amp={v:.4f}")

    return "\n".join(linhas)


# ══════════════════════════════════════════════════════════════════════════
# PERSISTÊNCIA
# ══════════════════════════════════════════════════════════════════════════

def salvar_perfis(perfis, caminho):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "wb") as f:
        pickle.dump(perfis, f)


def carregar_perfis(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        return {}
    with open(caminho, "rb") as f:
        return pickle.load(f)


# ══════════════════════════════════════════════════════════════════════════
# CLI — roda sobre o dataset real e salva os perfis em OCR/modelos/
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    base_dir = Path(os.environ.get("LIBRAS_BASE_DIR", Path(__file__).resolve().parent.parent))
    os.environ["LIBRAS_BASE_DIR"] = str(base_dir)
    sys.path.insert(0, str(base_dir))

    import libras_recognizer as lr

    dados = lr.GerenciadorDados()

    print("=" * 70)
    print("LSAE — Pilar 1: perfil estatístico por sinal")
    print("=" * 70)

    Xe, ye, _ = dados.carregar_estaticos()
    print(f"\nEstáticos carregados: {len(Xe)} amostras")
    perfil_est = calcular_perfil_estatico(Xe, ye, min_amostras=2)
    salvar_perfis(perfil_est, base_dir / "modelos" / "perfil_estatico_sinais.pkl")
    print(f"Perfis estáticos calculados: {len(perfil_est)} sinais")
    for rotulo, p in sorted(perfil_est.items()):
        print(f"  {rotulo:6s} n={p['n_amostras']:3d}  amplitude_media={float(p['amplitude'].mean()):.4f}")

    Xd, yd, _ = dados.carregar_dinamicos()
    print(f"\nDinâmicos carregados: {len(Xd)} amostras")
    perfil_din = calcular_perfil_dinamico(Xd, yd, min_amostras=2)
    salvar_perfis(perfil_din, base_dir / "modelos" / "perfil_dinamico_sinais.pkl")
    print(f"Perfis dinâmicos calculados: {len(perfil_din)} sinais")
    print()
    print(resumo_dinamico(perfil_din, top_n=10))
