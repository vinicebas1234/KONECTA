#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LSAE — Libras Semantic Augmentation Engine
Prova de conceito (demo) do motor de geração + validação biomecânica/estatística.

O que este script demonstra (escopo da demo, sem overclaim):
  1. Carrega execuções reais de UM sinal a partir do dataset já coletado no KONECTA
     (OCR/dados_libras/dinamicos/<SINAL>/local/*.npy).
  2. Gera variações sintéticas com o motor biomecânico (Pilar 2):
       - reescala por "osso" por mão (simula mão maior/menor)
       - rotação 3D em torno do pulso (simula ângulo de câmera diferente)
       - jitter controlado (simula pequena diferença de execução)
  3. Valida estatisticamente cada amostra sintética (Etapa 6 do LSAE) comparando,
     via DTW, a distância até a amostra real mais próxima contra a distribuição
     de distâncias reais-entre-si do próprio sinal. Descarta o que foge do padrão.
  4. Gera 2 figuras (scatter de landmarks real vs. sintético aceito vs. rejeitado,
     e histograma de distâncias) para ilustrar o artigo/post.

O QUE ESTE SCRIPT **NÃO** FAZ (propositalmente, para não inflar a tese):
  - Não mede acurácia cross-signer (isso depende da Fase 0 do plano: split de
    avaliação por sinalizante + retreino do modelo real). É a prova de conceito
    do motor de geração+validação, não o resultado final do TCC.
  - Não implementa a Etapa 5 (validação linguística por faixas de parâmetro por
    sinal) — fica citada no README como próximo passo, pois depende de um
    cadastro manual de faixas por sinal que ainda não existe no dataset atual.

Uso:
    python3 lsae_demo.py --sinal AMOR --n-sinteticos 60 \
        --dados-dir OCR/dados_libras/dinamicos --out-dir demo_out
"""

import argparse
import os
import sys
import zlib
from pathlib import Path

import numpy as np


def _hash_determ(texto: str) -> int:
    """Hash determinístico entre execuções (hash() embutido do Python é
    aleatorizado por processo — usar hash() aqui quebraria a reprodutibilidade
    do experimento de uma rodada para a outra)."""
    return zlib.crc32(texto.encode("utf-8"))

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:
    plt = None


# ──────────────────────────────────────────────────────────────────────────
# Layout de features (compatível com o dataset Holistic já coletado: 225 =
# 2 mãos * 21 pontos * 3 eixos (126) + pose (33 pontos * 3 eixos = 99))
# ──────────────────────────────────────────────────────────────────────────
PONTOS_POR_MAO = 21
EIXOS = 3
FEATURES_POR_MAO = PONTOS_POR_MAO * EIXOS  # 63
N_MAOS = 2
FEATURES_MAOS = FEATURES_POR_MAO * N_MAOS  # 126
IDX_PULSO = 0
IDX_REF_ESCALA = 9  # base do dedo médio, mesma referência usada no libras_recognizer.py


def carregar_execucoes_reais(sinal_dir: Path):
    """Carrega todas as sequências .npy de um sinal (pasta 'local' ou 'public')."""
    arquivos = sorted(sinal_dir.rglob("*.npy"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum .npy encontrado em {sinal_dir}")
    sequencias = [np.load(f).astype(np.float32) for f in arquivos]
    return sequencias, arquivos


def extrair_maos(seq):
    """Retorna só o bloco de mãos (primeiras 126 colunas) de uma sequência (T, 225)."""
    return seq[:, :FEATURES_MAOS].copy()


def _mao_pts(vetor_mao):
    """(63,) -> (21, 3)"""
    return vetor_mao.reshape(PONTOS_POR_MAO, EIXOS)


def _mao_flat(pts):
    """(21, 3) -> (63,)"""
    return pts.reshape(-1)


def _mao_ativa(vetor_frame_maos):
    """Retorna o bloco de 63 valores (uma mão) que está de fato preenchido nesse
    frame. O MediaPipe não garante que a mão detectada sempre caia no slot 0 —
    em boa parte do dataset real a mão ativa está no slot 1. Se as duas
    estiverem preenchidas, usa a de maior amplitude (mais provável de ser a
    mão dominante em movimento)."""
    h0 = vetor_frame_maos[:FEATURES_POR_MAO]
    h1 = vetor_frame_maos[FEATURES_POR_MAO:FEATURES_MAOS]
    z0, z1 = np.allclose(h0, 0), np.allclose(h1, 0)
    if not z0 and z1:
        return h0
    if z0 and not z1:
        return h1
    if z0 and z1:
        return h0
    return h0 if np.abs(h0).sum() >= np.abs(h1).sum() else h1


# ──────────────────────────────────────────────────────────────────────────
# PILAR 2 — Motor biomecânico
# ──────────────────────────────────────────────────────────────────────────

def reescalar_por_osso(seq_maos, fator_min=0.85, fator_max=1.15, rng=None):
    """Reescala cada mão em torno do próprio pulso, simulando mão maior/menor
    entre pessoas diferentes, preservando os ângulos entre as articulações
    (escala uniforme por mão em torno do pulso, não escala isotrópica global
    da sequência inteira)."""
    rng = rng or np.random.default_rng()
    out = seq_maos.copy()
    for mao_idx in range(N_MAOS):
        ini = mao_idx * FEATURES_POR_MAO
        fim = ini + FEATURES_POR_MAO
        fator = float(rng.uniform(fator_min, fator_max))
        for t in range(out.shape[0]):
            pts = _mao_pts(out[t, ini:fim])
            centro = pts[IDX_PULSO].copy()
            pts = (pts - centro) * fator + centro
            out[t, ini:fim] = _mao_flat(pts)
    return out


def rotacionar_3d(seq_maos, max_graus=15.0, rng=None):
    """Rotação 3D completa (x, y, z) em torno do pulso de cada mão — simula
    ângulo de câmera diferente. Vai além da rotação planar (só XY) que o
    augmentation atual do KONECTA já faz."""
    rng = rng or np.random.default_rng()
    out = seq_maos.copy()

    ang = np.deg2rad(rng.uniform(-max_graus, max_graus, size=3))
    rx, ry, rz = ang

    Rx = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
    Ry = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
    Rz = np.array([[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]])
    R = (Rz @ Ry @ Rx).astype(np.float32)

    for mao_idx in range(N_MAOS):
        ini = mao_idx * FEATURES_POR_MAO
        fim = ini + FEATURES_POR_MAO
        for t in range(out.shape[0]):
            pts = _mao_pts(out[t, ini:fim])
            centro = pts[IDX_PULSO].copy()
            pts = (pts - centro) @ R.T + centro
            out[t, ini:fim] = _mao_flat(pts)
    return out


def jitter_controlado(seq_maos, sigma=0.01, limite=0.03, rng=None):
    """Pequena perturbação por ponto, com clip — proxy simplificado de jitter em
    espaço articular (a versão completa por ângulo/cinemática direta fica como
    próximo passo; aqui o clip evita deslocamentos anatomicamente absurdos)."""
    rng = rng or np.random.default_rng()
    ruido = rng.normal(0.0, sigma, size=seq_maos.shape).astype(np.float32)
    ruido = np.clip(ruido, -limite, limite)
    return seq_maos + ruido


def gerar_variacao_sintetica(seq_real, rng=None):
    """Aplica a composição do motor biomecânico a UMA execução real. Faixas
    calibradas para cobrir a variação real de tamanho de mão/ângulo de câmera
    entre pessoas diferentes (não só ruído fino em cima da mesma pessoa)."""
    rng = rng or np.random.default_rng()
    seq = extrair_maos(seq_real)
    seq = reescalar_por_osso(seq, fator_min=0.7, fator_max=1.3, rng=rng)
    seq = rotacionar_3d(seq, max_graus=25.0, rng=rng)
    seq = jitter_controlado(seq, sigma=0.02, limite=0.05, rng=rng)
    return seq


def gerar_variacao_adversarial(seq_real, rng=None):
    """Variação deliberadamente exagerada — usada só para provar que o filtro
    estatístico (Etapa 6) de fato rejeita amostras fora do padrão do sinal.
    NÃO representa o comportamento normal do motor biomecânico."""
    rng = rng or np.random.default_rng()
    seq = extrair_maos(seq_real)
    seq = reescalar_por_osso(seq, fator_min=0.4, fator_max=2.2, rng=rng)
    seq = rotacionar_3d(seq, max_graus=90.0, rng=rng)
    seq = jitter_controlado(seq, sigma=0.15, limite=0.4, rng=rng)
    return seq


# ──────────────────────────────────────────────────────────────────────────
# ETAPA 6 — Validação estatística (DTW contra a distribuição real)
# ──────────────────────────────────────────────────────────────────────────

def dtw_distancia(a, b):
    """DTW simples (numpy puro) sobre sequências (T, F). Implementação O(n*m),
    suficiente para uma demo — em produção, trocar por dtaidistance/fastdtw."""
    n, m = a.shape[0], b.shape[0]
    custo = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=-1)  # (n, m)
    D = np.full((n + 1, m + 1), np.inf, dtype=np.float64)
    D[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = custo[i - 1, j - 1] + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    return float(D[n, m])


def validar_estatisticamente(sinteticas, reais, percentil=90):
    """Para cada amostra sintética, calcula a distância DTW até a real mais
    próxima. Define o limiar como o percentil P das distâncias reais-entre-si
    (quão distantes as execuções reais já são umas das outras) e rejeita
    sintéticos além disso."""
    # distâncias reais-entre-si (baseline de variação natural do sinal)
    dist_reais = []
    for i in range(len(reais)):
        for j in range(i + 1, len(reais)):
            dist_reais.append(dtw_distancia(reais[i], reais[j]))
    limiar = float(np.percentile(dist_reais, percentil)) if dist_reais else float("inf")

    resultados = []
    for seq_sint in sinteticas:
        d_min = min(dtw_distancia(seq_sint, seq_real) for seq_real in reais)
        aceito = d_min <= limiar
        resultados.append({"distancia_min": d_min, "aceito": aceito})

    return resultados, limiar, dist_reais


# ──────────────────────────────────────────────────────────────────────────
# VISUALIZAÇÃO
# ──────────────────────────────────────────────────────────────────────────

def plotar_landmarks(reais, sinteticas_info, out_path, frame_idx=0):
    if plt is None:
        print("[aviso] matplotlib indisponível — pulando figura de landmarks.")
        return

    fig, ax = plt.subplots(figsize=(6, 6))

    def desenhar_mao(vetor_mao, cor, label, alpha=1.0, marker="o", s=25, zorder=2):
        pts = _mao_pts(vetor_mao)
        if np.allclose(pts, 0):
            return
        ax.scatter(pts[:, 0], -pts[:, 1], c=cor, alpha=alpha, s=s, marker=marker,
                   label=label, zorder=zorder)

    # sintéticas rejeitadas / aceitas primeiro (fundo)
    label_ok, label_no = "sintético aceito", "sintético rejeitado"
    for seq, info in sinteticas_info:
        frame = min(frame_idx, seq.shape[0] - 1)
        vetor = _mao_ativa(seq[frame])
        if info["aceito"]:
            desenhar_mao(vetor, "tab:green", label_ok, alpha=0.5, marker="^", s=30, zorder=2)
            label_ok = None
        else:
            desenhar_mao(vetor, "tab:red", label_no, alpha=0.5, marker="x", s=30, zorder=2)
            label_no = None

    # amostras reais por cima, em destaque
    for i, seq in enumerate(reais):
        maos = extrair_maos(seq)
        frame = min(frame_idx, maos.shape[0] - 1)
        vetor = _mao_ativa(maos[frame])
        desenhar_mao(vetor, "black", "real" if i == 0 else None,
                     alpha=0.9, marker="*", s=90, zorder=3)

    ax.set_title("LSAE — landmarks reais vs. sintéticos (mão dominante, 1 frame)")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_xlabel("x (normalizado)")
    ax.set_ylabel("-y (normalizado)")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plotar_histograma(dist_reais, resultados, limiar, out_path, percentil=90.0):
    if plt is None:
        print("[aviso] matplotlib indisponível — pulando histograma.")
        return

    dist_sint_aceitas = [r["distancia_min"] for r in resultados if r["aceito"]]
    dist_sint_rejeitadas = [r["distancia_min"] for r in resultados if not r["aceito"]]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(dist_reais, bins=15, alpha=0.5, label="real ↔ real", color="black")
    if dist_sint_aceitas:
        ax.hist(dist_sint_aceitas, bins=15, alpha=0.6, label="sintético aceito", color="tab:green")
    if dist_sint_rejeitadas:
        ax.hist(dist_sint_rejeitadas, bins=15, alpha=0.6, label="sintético rejeitado", color="tab:red")
    ax.axvline(limiar, color="gray", linestyle="--", label=f"limiar (p{percentil:.0f}) = {limiar:.2f}")
    ax.set_title("Validação estatística (Etapa 6) — distância DTW")
    ax.set_xlabel("distância DTW até a execução real mais próxima")
    ax.set_ylabel("frequência")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# ──────────────────────────────────────────────────────────────────────────
# EXPERIMENTO "SEM LSAE" vs. "COM LSAE"
#
# Este experimento simula, de forma controlada e declarada, o que aconteceria
# com "outra pessoa" sinalizando: pega uma execução real de cada sinal, aplica
# uma transformação geométrica FIXA (mão menor + rotação), representando
# alguém com mão de tamanho diferente e outro ângulo de câmera, e usa isso
# como amostra de teste. NÃO é dado real de múltiplos sinalizantes — é uma
# simulação declarada, usada só para comparar dois cenários de treino:
#
#   "SEM LSAE" → treina 1-NN (DTW) só com as execuções reais restantes.
#   "COM LSAE" → treina 1-NN (DTW) com as execuções reais + sintéticas
#                 geradas e aprovadas pelo motor biomecânico/estatístico.
#
# A métrica é: o vizinho mais próximo (DTW) do "sinalizante simulado" cai na
# classe certa ou não? Repetido para vários sinais.
# ──────────────────────────────────────────────────────────────────────────

def _simular_execucao_de_outra_pessoa(seq_maos, rng=None):
    """Transformação de magnitude fixa e declarada (mão 28% menor + rotação de
    até 22°) para simular uma pessoa com mão de outro tamanho e câmera em
    outro ângulo. Usada só para montar o conjunto de teste do experimento
    sem/com LSAE — não é dado real de outro sinalizante."""
    seq = reescalar_por_osso(seq_maos, fator_min=0.72, fator_max=0.72, rng=rng)
    seq = rotacionar_3d(seq, max_graus=22.0, rng=rng)
    return seq


def _classificar_1nn_dtw(seq_teste, pool_rotulado):
    """1-NN por DTW: retorna o rótulo do vizinho mais próximo em pool_rotulado
    (lista de (rotulo, sequencia))."""
    melhor_rotulo, melhor_dist = None, float("inf")
    for rotulo, seq_treino in pool_rotulado:
        d = dtw_distancia(seq_teste, seq_treino)
        if d < melhor_dist:
            melhor_dist, melhor_rotulo = d, rotulo
    return melhor_rotulo, melhor_dist


def experimento_sem_com_lsae(sinais, dados_dir, n_sinteticos_por_sinal=8, percentil=75.0, seed=42):
    """Roda o experimento comparativo em uma lista de sinais e retorna um
    dicionário com os resultados (acerto sem/com LSAE por sinal + agregado)."""
    rng_base = np.random.default_rng(seed)

    dados_por_sinal = {}
    for sinal in sinais:
        pasta = Path(dados_dir) / sinal
        if not pasta.exists():
            print(f"[aviso] sinal '{sinal}' não encontrado em {dados_dir}, ignorando.")
            continue
        reais, _ = carregar_execucoes_reais(pasta)
        reais_maos = [extrair_maos(s) for s in reais]
        if len(reais_maos) < 3:
            print(f"[aviso] sinal '{sinal}' tem só {len(reais_maos)} amostras (mínimo 3), ignorando.")
            continue
        dados_por_sinal[sinal] = reais_maos

    if len(dados_por_sinal) < 2:
        raise ValueError("É preciso pelo menos 2 sinais válidos (>=3 amostras reais cada) para o experimento.")

    # monta teste (1 amostra "de outra pessoa" simulada por sinal) e treino base
    testes = {}       # sinal -> sequência de teste simulada
    treino_real = {}  # sinal -> lista de sequências reais restantes (treino)
    for sinal, amostras in dados_por_sinal.items():
        rng = np.random.default_rng(seed + _hash_determ(sinal) % 10_000)
        idx_teste = int(rng.integers(0, len(amostras)))
        base_teste = amostras[idx_teste]
        restantes = [a for i, a in enumerate(amostras) if i != idx_teste]
        testes[sinal] = _simular_execucao_de_outra_pessoa(base_teste, rng=rng)
        treino_real[sinal] = restantes

    # pool "SEM LSAE": só real
    pool_sem = [(sinal, seq) for sinal, seqs in treino_real.items() for seq in seqs]

    # pool "COM LSAE": real + sintéticas validadas (mesma lógica do resto do script)
    pool_com = list(pool_sem)
    resumo_geracao = {}
    for sinal, reais_treino in treino_real.items():
        rng = np.random.default_rng(seed + 1 + _hash_determ(sinal) % 10_000)
        sinteticas = [gerar_variacao_sintetica(s, rng=rng)
                      for s in (reais_treino[rng.integers(0, len(reais_treino))]
                                for _ in range(n_sinteticos_por_sinal))]
        resultados, _, _ = validar_estatisticamente(sinteticas, reais_treino, percentil=percentil)
        aprovadas = [seq for seq, r in zip(sinteticas, resultados) if r["aceito"]]
        resumo_geracao[sinal] = {"geradas": len(sinteticas), "aprovadas": len(aprovadas)}
        pool_com.extend((sinal, seq) for seq in aprovadas)

    # classificação
    linhas = []
    for sinal, seq_teste in testes.items():
        rot_sem, _ = _classificar_1nn_dtw(seq_teste, pool_sem)
        rot_com, _ = _classificar_1nn_dtw(seq_teste, pool_com)
        linhas.append({
            "sinal": sinal,
            "acertou_sem_lsae": rot_sem == sinal,
            "acertou_com_lsae": rot_com == sinal,
            "previsto_sem_lsae": rot_sem,
            "previsto_com_lsae": rot_com,
        })

    acc_sem = float(np.mean([l["acertou_sem_lsae"] for l in linhas]))
    acc_com = float(np.mean([l["acertou_com_lsae"] for l in linhas]))

    return {
        "linhas": linhas,
        "acc_sem_lsae": acc_sem,
        "acc_com_lsae": acc_com,
        "resumo_geracao": resumo_geracao,
        "n_sinais": len(dados_por_sinal),
    }


def experimento_sem_com_lsae_repetido(sinais, dados_dir, n_sinteticos_por_sinal=10,
                                       percentil=75.0, seeds=range(20)):
    """Repete o experimento sem/com LSAE variando a semente (o que muda tanto
    a amostra de cada sinal usada como 'teste simulado' quanto a geração
    sintética), e agrega média/desvio-padrão. Uma única repetição é ruidosa
    demais (poucos sinais, poucas amostras por classe) para servir de
    conclusão — a média sobre várias repetições é o número que deve ser
    reportado."""
    todas_sem, todas_com = [], []
    ultimo = None
    for seed in seeds:
        r = experimento_sem_com_lsae(sinais, dados_dir, n_sinteticos_por_sinal, percentil, seed=seed)
        todas_sem.append(r["acc_sem_lsae"])
        todas_com.append(r["acc_com_lsae"])
        ultimo = r

    return {
        "n_repeticoes": len(todas_sem),
        "n_sinais": ultimo["n_sinais"] if ultimo else 0,
        "acc_sem_lsae_media": float(np.mean(todas_sem)),
        "acc_sem_lsae_std": float(np.std(todas_sem)),
        "acc_com_lsae_media": float(np.mean(todas_com)),
        "acc_com_lsae_std": float(np.std(todas_com)),
        "todas_sem": todas_sem,
        "todas_com": todas_com,
    }


def plotar_comparacao_sem_com(resultado, out_path):
    if plt is None:
        print("[aviso] matplotlib indisponível — pulando gráfico de comparação.")
        return

    fig, ax = plt.subplots(figsize=(6.5, 5))
    valores = [resultado["acc_sem_lsae_media"] * 100, resultado["acc_com_lsae_media"] * 100]
    erros = [resultado["acc_sem_lsae_std"] * 100, resultado["acc_com_lsae_std"] * 100]
    cores = ["tab:red", "tab:green"]
    barras = ax.bar(["Sem LSAE\n(só dados reais)", "Com LSAE\n(real + sintético validado)"],
                     valores, yerr=erros, capsize=6, color=cores, alpha=0.85, width=0.55)
    for barra, v in zip(barras, valores):
        ax.text(barra.get_x() + barra.get_width() / 2, v + 3, f"{v:.1f}%",
                 ha="center", fontweight="bold")

    ax.set_ylim(0, max(valores) + max(erros) + 15)
    ax.set_ylabel("Acurácia média (1-NN / DTW)")
    ax.set_title(f"Sem LSAE vs. Com LSAE\n{resultado['n_sinais']} sinais · média de {resultado['n_repeticoes']} repetições\nteste = sinalizante simulado", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# ──────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Demo do motor LSAE (geração + validação)")
    parser.add_argument("--sinal", default="AMOR", help="Nome da pasta do sinal em dinamicos/")
    parser.add_argument("--dados-dir", default="OCR/dados_libras/dinamicos", help="Pasta raiz dos sinais dinâmicos")
    parser.add_argument("--n-sinteticos", type=int, default=60, help="Quantidade de variações sintéticas a gerar")
    parser.add_argument("--frac-adversarial", type=float, default=0.2,
                         help="Fração de amostras adversariais (exageradas) incluída só para provar que o filtro rejeita")
    parser.add_argument("--percentil", type=float, default=75.0, help="Percentil da distância real usado como limiar")
    parser.add_argument("--out-dir", default="demo_out", help="Pasta de saída para figuras")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--experimento-sem-com", action="store_true",
                         help="Roda também o experimento comparativo Sem LSAE vs. Com LSAE")
    parser.add_argument("--sinais-experimento", default="AMOR,Amarelo,Casa,Abraço,Abelha,Aborto",
                         help="Lista de sinais (separados por vírgula) usados no experimento sem/com LSAE")
    parser.add_argument("--repeticoes", type=int, default=20,
                         help="Repetições do experimento sem/com LSAE (a média entre elas é o número reportável)")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    sinal_dir = Path(args.dados_dir) / args.sinal
    if not sinal_dir.exists():
        print(f"[erro] Pasta não encontrada: {sinal_dir}")
        sys.exit(1)

    reais, arquivos = carregar_execucoes_reais(sinal_dir)
    reais_maos = [extrair_maos(s) for s in reais]
    print(f"Sinal '{args.sinal}': {len(reais)} execuções reais carregadas ({[a.name for a in arquivos][:5]}{'...' if len(arquivos) > 5 else ''})")

    # geração sintética: escolhe uma execução real base aleatoriamente por amostra
    n_adv = int(round(args.n_sinteticos * args.frac_adversarial))
    n_normais = args.n_sinteticos - n_adv

    sinteticas = []
    for _ in range(n_normais):
        base = reais[rng.integers(0, len(reais))]
        sinteticas.append(gerar_variacao_sintetica(base, rng=rng))
    for _ in range(n_adv):
        base = reais[rng.integers(0, len(reais))]
        sinteticas.append(gerar_variacao_adversarial(base, rng=rng))
    print(f"  → {n_normais} variações biomecânicas normais + {n_adv} adversariais (stress-test do filtro)")

    resultados, limiar, dist_reais = validar_estatisticamente(sinteticas, reais_maos, percentil=args.percentil)
    n_aceitas = sum(r["aceito"] for r in resultados)

    print(f"Amostras sintéticas geradas: {len(sinteticas)}")
    print(f"Limiar estatístico (p{args.percentil:.0f} da distância real↔real): {limiar:.3f}")
    print(f"Aceitas após validação estatística: {n_aceitas} ({n_aceitas/len(sinteticas):.0%})")
    print(f"Rejeitadas: {len(sinteticas) - n_aceitas} ({1 - n_aceitas/len(sinteticas):.0%})")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sinteticas_info = list(zip(sinteticas, resultados))
    plotar_landmarks(reais, sinteticas_info, out_dir / f"lsae_landmarks_{args.sinal}.png")
    plotar_histograma(dist_reais, resultados, limiar, out_dir / f"lsae_histograma_{args.sinal}.png", percentil=args.percentil)

    print(f"\nFiguras salvas em: {out_dir.resolve()}")

    if args.experimento_sem_com:
        sinais = [s.strip() for s in args.sinais_experimento.split(",") if s.strip()]
        print(f"\n{'='*60}\nExperimento SEM LSAE vs. COM LSAE — sinais: {sinais}\n{'='*60}")
        print(f"Rodando {args.repeticoes} repetições (troca a amostra de teste e a geração sintética a cada rodada)...")

        resultado = experimento_sem_com_lsae_repetido(
            sinais, args.dados_dir,
            n_sinteticos_por_sinal=10,
            percentil=args.percentil,
            seeds=range(args.repeticoes),
        )

        print(f"\nAcurácia média SEM LSAE: {resultado['acc_sem_lsae_media']:.1%} (± {resultado['acc_sem_lsae_std']:.1%})")
        print(f"Acurácia média COM LSAE: {resultado['acc_com_lsae_media']:.1%} (± {resultado['acc_com_lsae_std']:.1%})")
        print("(sinalizante de teste é simulado por transformação geométrica declarada — ver docstring do experimento;"
              " uma única repetição é ruidosa demais para concluir algo — por isso a média de várias.)")

        plotar_comparacao_sem_com(resultado, out_dir / "lsae_sem_vs_com.png")
        print(f"Gráfico salvo em: {(out_dir / 'lsae_sem_vs_com.png').resolve()}")


if __name__ == "__main__":
    main()
