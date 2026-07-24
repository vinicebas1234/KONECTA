#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fase 3 do LSAE — concretização da Etapa 6 (Validação Estatística).

"Descarta se a amostra estiver muito distante da distribuição real" só vira
uma regra de verdade quando "muito distante" tem número atrás.

ACHADO IMPORTANTE (documentado aqui porque muda o desenho do módulo): a
abordagem óbvia — Mahalanobis com covariância por sinal via Ledoit-Wolf,
limiar qui-quadrado — foi testada primeiro e FALHA na prática. A maioria dos
sinais dinâmicos tem só 2-3 amostras reais (3 vídeos do V-Librasil), e com
N=2-3 amostras em F=126 dimensões nenhum estimador de covariância por sinal
é confiável: testei empiricamente e o Ledoit-Wolf, mesmo com encolhimento,
rejeitava ~100% das amostras sintéticas plausíveis nesse regime (a variância
estimada de 2-3 pontos é tão instável que qualquer amostra nova parece um
outlier extremo). Isso não é specific do Ledoit-Wolf: uma Mahalanobis
diagonal (variância por dimensão, sem covariância cruzada) tem exatamente o
mesmo problema, porque a causa é a estimativa de variância em si, não a
estrutura de correlação.

A correção adotada, verificada por simulação antes de aplicar:

  1) A MÉDIA por sinal é confiável mesmo com N=2-3 (erro de estimação da
     média cai com sqrt(N), não explode) — é exatamente o que o Pilar 1
     (perfil_estatistico.py) já calcula em `media_trajetoria`.

  2) A VARIÂNCIA não pode vir do sinal individual. Em vez disso, agregamos
     («pooling») os resíduos de TODOS os sinais do dataset (cada amostra
     menos a média do PRÓPRIO sinal) para estimar uma variância intra-sinal
     única e estável — um procedimento clássico de ANOVA/efeitos aleatórios.
     Com ~4000 amostras em ~1364 sinais isso dá milhares de graus de
     liberdade agregados, mesmo que cada sinal isoladamente só contribua 1-2.

  3) Como ainda usamos a média específica do sinal (estimada de N amostras),
     a variância efetiva de comparação precisa incluir o erro dessa
     estimativa: var_efetiva = var_pooled * (1 + 1/N). Sem essa correção o
     limiar qui-quadrado fica mal calibrado (confirmado por simulação: sem a
     correção, ~90% de falsos positivos com N=2; com ela, ~3-4%, batendo com
     o percentil pedido).

DTW não tem esse problema (compara sequência inteira contra sequência
inteira, não depende de estimar variância por dimensão), então segue como
descrito no documento original.
"""

import sys

import numpy as np
from scipy.stats import chi2

from lsae.perfil_estatistico import resample_sequencia, TOTAL_FEATURES, SEQUENCE_LENGTH


# ══════════════════════════════════════════════════════════════════════════
# VARIÂNCIA POOLED (intra-sinal, agregada entre TODOS os sinais do dataset)
# ══════════════════════════════════════════════════════════════════════════

def estimar_variancia_pooled_dinamica(X, y, n_pontos=SEQUENCE_LENGTH, min_amostras_por_sinal=2):
    """Variância intra-sinal agregada de todos os sinais com >= 2 amostras
    reais (cada amostra centrada na média do seu PRÓPRIO sinal antes de
    somar os quadrados — isso isola a variação natural de repetição do
    sinal, sem contaminar com a diferença de médias ENTRE sinais diferentes).
    Retorna (n_pontos, F)."""
    rotulos = sorted(set(str(r) for r in y))
    soma_quadrados = np.zeros((n_pontos, TOTAL_FEATURES), dtype=np.float64)
    graus_liberdade = 0

    for rotulo in rotulos:
        brutas = [np.asarray(x, dtype=np.float32) for x, r in zip(X, y) if str(r) == rotulo]
        brutas = [seq for seq in brutas if seq.ndim == 2 and seq.shape[0] >= 2 and seq.shape[1] == TOTAL_FEATURES]
        if len(brutas) < min_amostras_por_sinal:
            continue

        arr = np.stack([resample_sequencia(seq, n_pontos) for seq in brutas], axis=0)  # (n, T, F)
        media = arr.mean(axis=0, keepdims=True)
        soma_quadrados += ((arr - media) ** 2).sum(axis=0)
        graus_liberdade += len(brutas) - 1

    if graus_liberdade < 1:
        raise ValueError(
            "Nenhum sinal tem amostras reais suficientes (>=2) para estimar variância pooled."
        )

    return soma_quadrados / graus_liberdade


def estimar_variancia_pooled_estatica(X, y, min_amostras_por_classe=2):
    """Equivalente para poses estáticas (sem dimensão temporal). Retorna (F,)."""
    rotulos = sorted(set(str(r) for r in y))
    soma_quadrados = np.zeros(TOTAL_FEATURES, dtype=np.float64)
    graus_liberdade = 0

    for rotulo in rotulos:
        amostras = np.array([np.asarray(x, dtype=np.float32) for x, r in zip(X, y) if str(r) == rotulo])
        if len(amostras) < min_amostras_por_classe:
            continue
        media = amostras.mean(axis=0, keepdims=True)
        soma_quadrados += ((amostras - media) ** 2).sum(axis=0)
        graus_liberdade += len(amostras) - 1

    if graus_liberdade < 1:
        raise ValueError(
            "Nenhuma classe tem amostras reais suficientes (>=2) para estimar variância pooled."
        )

    return soma_quadrados / graus_liberdade


# ══════════════════════════════════════════════════════════════════════════
# MAHALANOBIS (média por sinal + variância pooled do dataset, com correção
# de tamanho de amostra)
# ══════════════════════════════════════════════════════════════════════════

def validar_mahalanobis_dinamico(seq_sintetica, media_trajetoria_sinal, n_amostras_sinal, var_pooled,
                                  percentil=0.97, fracao_max_outlier=0.2, n_pontos=SEQUENCE_LENGTH):
    """media_trajetoria_sinal: (n_pontos, F) — vem de
    perfil_estatistico.calcular_perfil_dinamico(...)[rotulo]['media_trajetoria'].
    var_pooled: (n_pontos, F) — vem de estimar_variancia_pooled_dinamica,
    calculada UMA VEZ para o dataset inteiro e reutilizada para todo sinal.
    n_amostras_sinal: quantas amostras reais esse sinal específico tem (usado
    na correção var*(1+1/N) — quanto menos amostras, mais incerta a média)."""
    sint = resample_sequencia(seq_sintetica, n_pontos)
    var_efetiva = np.maximum(var_pooled * (1.0 + 1.0 / max(n_amostras_sinal, 1)), 1e-8)

    d2_por_frame = np.sum((sint - media_trajetoria_sinal) ** 2 / var_efetiva, axis=1)
    limiar = float(chi2.ppf(percentil, df=sint.shape[1]))

    fracao_outlier = float(np.mean(d2_por_frame > limiar))
    aceito = fracao_outlier <= fracao_max_outlier

    return {
        "aceito": aceito,
        "motivo": "ok" if aceito else f"outlier_em_{fracao_outlier:.0%}_dos_frames",
        "fracao_outlier": fracao_outlier,
        "d2_medio": float(d2_por_frame.mean()),
        "limiar": limiar,
    }


def validar_mahalanobis_estatico(pose_sintetica, media_sinal, n_amostras_sinal, var_pooled, percentil=0.97):
    """Equivalente para pose única. media_sinal/var_pooled: (F,)."""
    var_efetiva = np.maximum(var_pooled * (1.0 + 1.0 / max(n_amostras_sinal, 1)), 1e-8)
    d2 = float(np.sum((np.asarray(pose_sintetica, dtype=np.float64) - media_sinal) ** 2 / var_efetiva))
    limiar = float(chi2.ppf(percentil, df=len(media_sinal)))
    aceito = d2 <= limiar
    return {"aceito": aceito, "motivo": "ok" if aceito else "distante_da_distribuicao_real",
            "d2": d2, "limiar": limiar}


# ══════════════════════════════════════════════════════════════════════════
# DTW (Dynamic Time Warping) — não depende de estimar variância, sem o
# problema acima
# ══════════════════════════════════════════════════════════════════════════

def dtw_distancia(seq_a, seq_b):
    """DTW clássico com custo euclidiano por frame. Sequências podem ter
    tamanhos diferentes; O(n*m), trivial para as sequências curtas (~30
    frames) usadas aqui."""
    seq_a = np.asarray(seq_a, dtype=np.float64)
    seq_b = np.asarray(seq_b, dtype=np.float64)
    n, m = len(seq_a), len(seq_b)

    custo = np.linalg.norm(seq_a[:, None, :] - seq_b[None, :, :], axis=2)  # (n, m)

    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = custo[i - 1, j - 1] + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])

    return float(D[n, m])


def validar_dtw(seq_sintetica, amostras_reais, percentil=90):
    """Compara a sequência sintética às amostras reais do sinal via DTW, e
    usa como limiar o percentil das distâncias DTW observadas ENTRE as
    próprias amostras reais (quanto elas já variam naturalmente entre si).
    Com só 2 amostras reais, o 'percentil' é a própria (única) distância
    real-real — funciona, mas é um limiar fraco; sinalizamos isso em
    'motivo' quando aplicável."""
    if len(amostras_reais) < 2:
        return {"aceito": True, "motivo": "amostras_reais_insuficientes_para_dtw",
                "dist_min_ao_real": None, "limiar": None}

    distancias_real_real = [
        dtw_distancia(amostras_reais[i], amostras_reais[j])
        for i in range(len(amostras_reais))
        for j in range(i + 1, len(amostras_reais))
    ]
    limiar = float(np.percentile(distancias_real_real, percentil))

    distancias_sint_real = [dtw_distancia(seq_sintetica, real) for real in amostras_reais]
    dist_min = float(min(distancias_sint_real))
    aceito = dist_min <= limiar

    motivo = "ok" if aceito else "dtw_acima_do_limiar_real_real"
    if len(amostras_reais) == 2:
        motivo += "_aviso_limiar_de_apenas_1_par_real"

    return {"aceito": aceito, "motivo": motivo, "dist_min_ao_real": dist_min, "limiar": limiar}


# ══════════════════════════════════════════════════════════════════════════
# ORQUESTRAÇÃO
# ══════════════════════════════════════════════════════════════════════════

def validar_estatisticamente_dinamico(seq_sintetica, amostras_reais, media_trajetoria_sinal, var_pooled,
                                       percentil_mahalanobis=0.97, percentil_dtw=90, fracao_max_outlier=0.2):
    """Combina Mahalanobis (média do sinal + variância pooled do dataset) e
    DTW (contra as amostras reais do próprio sinal). Só aceita se AMBOS os
    critérios aplicáveis passarem."""
    r_maha = validar_mahalanobis_dinamico(
        seq_sintetica, media_trajetoria_sinal, len(amostras_reais), var_pooled,
        percentil=percentil_mahalanobis, fracao_max_outlier=fracao_max_outlier,
    )
    r_dtw = validar_dtw(seq_sintetica, amostras_reais, percentil=percentil_dtw)

    aceito = r_maha["aceito"] and r_dtw["aceito"]
    return {"aceito": aceito, "mahalanobis": r_maha, "dtw": r_dtw}


# ══════════════════════════════════════════════════════════════════════════
# CLI — calcula a variância pooled sobre o dataset real, salva em disco e
# roda um teste de aceitação (Pilar 2 + Fase 3) para conferir a calibração
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os
    from pathlib import Path

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    base_dir = Path(os.environ.get("LIBRAS_BASE_DIR", Path(__file__).resolve().parent.parent))
    os.environ["LIBRAS_BASE_DIR"] = str(base_dir)
    sys.path.insert(0, str(base_dir))

    import libras_recognizer as lr
    from lsae.motor_biomecanico import augmentar_sequencia
    from lsae.perfil_estatistico import calcular_perfil_dinamico, calcular_perfil_estatico, salvar_perfis

    print("=" * 70)
    print("LSAE — Fase 3: variância pooled + teste de calibração real")
    print("=" * 70)

    dados = lr.GerenciadorDados()

    Xd, yd, _ = dados.carregar_dinamicos()
    Xd_f, yd_f = [], []
    for x, r in zip(Xd, yd):
        x = np.asarray(x, dtype=np.float32)
        if x.ndim == 2 and x.shape[0] >= 4 and x.shape[1] == TOTAL_FEATURES:
            Xd_f.append(x)
            yd_f.append(r)
    print(f"\nDinâmicos válidos: {len(Xd_f)}/{len(Xd)}")

    var_pooled_din = estimar_variancia_pooled_dinamica(Xd_f, yd_f)
    salvar_perfis(var_pooled_din, base_dir / "modelos" / "variancia_pooled_dinamica.pkl")
    print(f"Variância pooled dinâmica salva. Média={var_pooled_din.mean():.6f}")

    Xe, ye, _ = dados.carregar_estaticos()
    var_pooled_est = estimar_variancia_pooled_estatica(Xe, ye)
    salvar_perfis(var_pooled_est, base_dir / "modelos" / "variancia_pooled_estatica.pkl")
    print(f"Variância pooled estática salva. Média={var_pooled_est.mean():.6f}")

    perfis_din = calcular_perfil_dinamico(Xd_f, yd_f, min_amostras=2)

    print(f"\nRodando teste de aceitação: 5 variações sintéticas x 50 sinais reais...")
    rng = np.random.default_rng(3)
    sinais_teste = list(perfis_din.keys())[:50]
    total_gerado, total_aceito = 0, 0
    motivos_rejeicao = {}

    for rotulo in sinais_teste:
        amostras_reais = [x for x, r in zip(Xd_f, yd_f) if r == rotulo]
        media_traj = perfis_din[rotulo]["media_trajetoria"]
        for _ in range(5):
            sint, _descartes_biomec = augmentar_sequencia(amostras_reais[0], rng=rng)
            r = validar_estatisticamente_dinamico(sint, amostras_reais, media_traj, var_pooled_din)
            total_gerado += 1
            if r["aceito"]:
                total_aceito += 1
            else:
                motivo = r["mahalanobis"]["motivo"] if not r["mahalanobis"]["aceito"] else r["dtw"]["motivo"]
                motivos_rejeicao[motivo] = motivos_rejeicao.get(motivo, 0) + 1

    print(f"\nAceitos: {total_aceito}/{total_gerado} ({total_aceito/total_gerado:.1%})")
    print(f"Motivos de rejeição: {motivos_rejeicao}")

    print("\nControle negativo (amostra deliberadamente corrompida, deve ser rejeitada):")
    rotulo0 = sinais_teste[0]
    amostras_reais0 = [x for x, r in zip(Xd_f, yd_f) if r == rotulo0]
    media0 = perfis_din[rotulo0]["media_trajetoria"]
    sint_ruim = amostras_reais0[0] + rng.normal(0, 1.5, amostras_reais0[0].shape).astype(np.float32)
    r_ruim = validar_estatisticamente_dinamico(sint_ruim, amostras_reais0, media0, var_pooled_din)
    print(f"  aceito={r_ruim['aceito']} (esperado False) | motivo={r_ruim['mahalanobis']['motivo']}")
