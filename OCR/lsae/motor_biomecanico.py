#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pilar 2 do LSAE — Conhecimento Biomecânico (motor de augmentation).

Gera variações sintéticas de uma pose/sequência de mão que preservam a
plausibilidade anatômica POR CONSTRUÇÃO: em vez de somar ruído xyz direto nos
21 landmarks (o que pode fazer um dedo "atravessar" a mão ou um pulso girar
de um jeito impossível), tudo aqui opera no espaço de OSSOS (vetor
pai->filho da árvore cinemática da mão do MediaPipe):

  - reescalar um dedo = mudar o COMPRIMENTO do osso, mantendo a direção
    (ângulo da articulação) exatamente igual — não é escala isotrópica.
  - jitter cinemático = girar levemente a DIREÇÃO do osso (ângulo pequeno),
    mantendo o comprimento — simula variação natural de execução sem
    permitir rotações grandes/impossíveis.
  - rotação 3D / escala global = transformação rígida da nuvem de pontos
    inteira (equivalente a inclinar o braço ou mudar distância da câmera),
    não muda proporção interna nenhuma.

Isso é o "não permite dedos atravessando a mão, rotações impossíveis, ...
Só gera poses biologicamente plausíveis" do documento LSAE — implementado
como restrição estrutural (o pipeline não consegue gerar certas classes de
pose impossível), não como um classificador que julga poses depois de
geradas. `validar_biomecanica` é uma rede de segurança adicional, não o
mecanismo principal.

Funções puras (só numpy), sem Tkinter/MediaPipe/TensorFlow — testável
isoladamente. Opera sobre o MESMO espaço normalizado que
DetectorMaos._normalizar_mao já produz (mão centralizada no pulso, escalada
pela distância pulso→base-do-dedo-médio, landmark 0 ≈ origem).
"""

import numpy as np

FEATURES_PER_HAND = 21 * 3
MP_MAX_HANDS = 2
TOTAL_FEATURES = FEATURES_PER_HAND * MP_MAX_HANDS
N_LANDMARKS = 21

# Árvore cinemática da mão (MediaPipe Hands, 21 pontos): landmark -> pai.
# Pulso (0) é a raiz. Cada dedo é uma cadeia: raiz da palma -> 3 falanges.
HAND_PARENT = {
    0: None,
    1: 0, 2: 1, 3: 2, 4: 3,       # polegar
    5: 0, 6: 5, 7: 6, 8: 7,       # indicador
    9: 0, 10: 9, 11: 10, 12: 11,  # médio
    13: 0, 14: 13, 15: 14, 16: 15,  # anelar
    17: 0, 18: 17, 19: 18, 20: 19,  # mínimo
}

DEDOS = {
    "polegar": (1, 2, 3, 4),
    "indicador": (5, 6, 7, 8),
    "medio": (9, 10, 11, 12),
    "anelar": (13, 14, 15, 16),
    "minimo": (17, 18, 19, 20),
}

def _profundidade_landmark(idx, cache={}):
    if idx not in cache:
        pai = HAND_PARENT[idx]
        cache[idx] = 0 if pai is None else 1 + _profundidade_landmark(pai, cache)
    return cache[idx]


ORDEM_TOPOLOGICA = sorted(HAND_PARENT.keys(), key=_profundidade_landmark)


# ══════════════════════════════════════════════════════════════════════════
# CINEMÁTICA: landmarks <-> ossos (vetor pai->filho)
# ══════════════════════════════════════════════════════════════════════════

def landmarks_para_ossos(hand_xyz):
    """hand_xyz: (21, 3). Retorna dict landmark_idx -> vetor_osso (filho-pai),
    para todo landmark que não seja a raiz (pulso)."""
    ossos = {}
    for idx in range(1, N_LANDMARKS):
        pai = HAND_PARENT[idx]
        ossos[idx] = hand_xyz[idx] - hand_xyz[pai]
    return ossos


def ossos_para_landmarks(pulso_xyz, ossos):
    """Reconstrói os 21 landmarks a partir do pulso + vetores de osso,
    processando em ordem topológica (pai sempre calculado antes do filho)."""
    out = np.zeros((N_LANDMARKS, 3), dtype=np.float32)
    out[0] = pulso_xyz
    for idx in ORDEM_TOPOLOGICA:
        if idx == 0:
            continue
        pai = HAND_PARENT[idx]
        out[idx] = out[pai] + ossos[idx]
    return out


def _mao_e_valida(hand_xyz, eps=1e-6):
    """Uma mão 'zero' (sem detecção naquele frame) não tem estrutura óssea —
    não faz sentido aplicar cinemática nela."""
    return bool(np.any(np.abs(hand_xyz) > eps))


# ══════════════════════════════════════════════════════════════════════════
# AUGMENTATION ANATÔMICA: reescala por segmento (preserva ângulos)
# ══════════════════════════════════════════════════════════════════════════

def reescalar_dedos(hand_xyz, fatores_por_dedo=None, fator_largura_palma=1.0, rng=None):
    """Muda o comprimento dos ossos de cada dedo (e opcionalmente o
    'espalhamento' da palma, via o osso raiz pulso->base do dedo), mantendo a
    DIREÇÃO de cada osso idêntica — ou seja, o ângulo de toda articulação
    fica exatamente igual ao original. Isso é reescala por segmento, não
    escala isotrópica: simula mãos com dedos mais longos/curtos sem
    distorcer a pose em si.

    fatores_por_dedo: dict opcional {"polegar": 1.05, "indicador": 0.97, ...}.
    Se None, sorteia um fator por dedo em torno de 1.0 usando rng."""
    if not _mao_e_valida(hand_xyz):
        return hand_xyz.copy()

    rng = rng or np.random.default_rng()
    if fatores_por_dedo is None:
        fatores_por_dedo = {dedo: float(rng.uniform(0.88, 1.12)) for dedo in DEDOS}

    ossos = landmarks_para_ossos(hand_xyz)

    for dedo, indices in DEDOS.items():
        fator_dedo = fatores_por_dedo.get(dedo, 1.0)
        raiz = indices[0]
        # osso raiz (pulso -> base do dedo): controla o "espalhamento" da palma
        ossos[raiz] = ossos[raiz] * fator_largura_palma
        # ossos das falanges: controla o comprimento do dedo
        for idx in indices[1:]:
            ossos[idx] = ossos[idx] * fator_dedo

    return ossos_para_landmarks(hand_xyz[0], ossos)


# ══════════════════════════════════════════════════════════════════════════
# AUGMENTATION CINEMÁTICA: jitter em espaço articular
# ══════════════════════════════════════════════════════════════════════════

def _matriz_rotacao_eixo_angulo(eixo, angulo_rad):
    """Rotação de Rodrigues em torno de um eixo unitário arbitrário."""
    eixo = eixo / (np.linalg.norm(eixo) + 1e-9)
    x, y, z = eixo
    c, s = np.cos(angulo_rad), np.sin(angulo_rad)
    C = 1 - c
    return np.array([
        [x * x * C + c,     x * y * C - z * s, x * z * C + y * s],
        [y * x * C + z * s, y * y * C + c,     y * z * C - x * s],
        [z * x * C - y * s, z * y * C + x * s, z * z * C + c],
    ], dtype=np.float64)


def jitter_articular(hand_xyz, sigma_graus=3.0, max_graus=10.0, rng=None):
    """Perturba a DIREÇÃO de cada osso com uma rotação pequena e aleatória em
    torno de um eixo aleatório, mantendo o comprimento do osso. O ângulo é
    sorteado de uma normal truncada em max_graus — bounded por construção,
    então não existe rotação "grande demais" que produza uma pose absurda.
    Simula a variação natural de execução entre repetições do mesmo sinal."""
    if not _mao_e_valida(hand_xyz):
        return hand_xyz.copy()

    rng = rng or np.random.default_rng()
    ossos = landmarks_para_ossos(hand_xyz)

    for idx, vetor in ossos.items():
        comprimento = np.linalg.norm(vetor)
        if comprimento < 1e-9:
            continue

        angulo_graus = float(np.clip(rng.normal(0.0, sigma_graus), -max_graus, max_graus))
        eixo = rng.normal(size=3)
        R = _matriz_rotacao_eixo_angulo(eixo, np.deg2rad(angulo_graus))
        ossos[idx] = (R @ vetor).astype(np.float32)

    return ossos_para_landmarks(hand_xyz[0], ossos)


# ══════════════════════════════════════════════════════════════════════════
# AUGMENTATION GEOMÉTRICA: rotação 3D e escala (transformação rígida global)
# ══════════════════════════════════════════════════════════════════════════

def rotacionar_3d(hand_xyz, angulos_graus, centro=None):
    """Rotaciona a nuvem de pontos inteira em torno de X, Y e Z (nessa
    ordem), em torno de `centro` (default: o próprio pulso). Transformação
    rígida — não muda nenhuma proporção interna, só a orientação (ex.:
    simula inclinação do braço/pulso ou ângulo de câmera)."""
    if not _mao_e_valida(hand_xyz):
        return hand_xyz.copy()

    centro = hand_xyz[0] if centro is None else centro
    rx, ry, rz = (np.deg2rad(a) for a in angulos_graus)

    Rx = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
    Ry = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
    Rz = np.array([[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]])
    R = Rz @ Ry @ Rx

    pontos = (hand_xyz - centro) @ R.T
    return (pontos + centro).astype(np.float32)


def escalar_isotropico(hand_xyz, fator, centro=None):
    """Escala uniforme da mão inteira (simula distância da câmera / zoom).
    Ao contrário de reescalar_dedos, aqui a proporção interna não muda —
    só o tamanho aparente."""
    if not _mao_e_valida(hand_xyz):
        return hand_xyz.copy()
    centro = hand_xyz[0] if centro is None else centro
    return ((hand_xyz - centro) * fator + centro).astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════
# VALIDAÇÃO BIOMECÂNICA (rede de segurança)
# ══════════════════════════════════════════════════════════════════════════

def validar_biomecanica(hand_xyz, hand_xyz_original, tol_comprimento=0.35, limite_coord=3.5):
    """Checagem determinística, não um julgamento semântico: os ossos não
    podem ter mudado de comprimento além de `tol_comprimento` (fração) em
    relação à amostra original, e nenhuma coordenada pode explodir para fora
    da faixa observada nos dados normalizados (DetectorMaos já clipa em
    [-3, 3]). Retorna (valido: bool, motivo: str)."""
    if not _mao_e_valida(hand_xyz):
        return True, "mao_vazia"

    if not np.all(np.isfinite(hand_xyz)):
        return False, "coordenadas_nao_finitas"

    if np.max(np.abs(hand_xyz)) > limite_coord:
        return False, f"coordenada_fora_da_faixa (max={np.max(np.abs(hand_xyz)):.2f})"

    ossos_novo = landmarks_para_ossos(hand_xyz)
    ossos_orig = landmarks_para_ossos(hand_xyz_original)

    for idx in ossos_novo:
        len_orig = np.linalg.norm(ossos_orig[idx])
        len_novo = np.linalg.norm(ossos_novo[idx])
        if len_orig < 1e-9:
            continue
        variacao = abs(len_novo - len_orig) / len_orig
        if variacao > tol_comprimento:
            return False, f"osso_{idx}_variou_{variacao:.0%}"

    return True, "ok"


# ══════════════════════════════════════════════════════════════════════════
# ORQUESTRAÇÃO: aplica o motor a um frame (126,) ou sequência (T, 126)
# ══════════════════════════════════════════════════════════════════════════

def _dividir_maos(vetor_126):
    return [vetor_126[i * FEATURES_PER_HAND:(i + 1) * FEATURES_PER_HAND].reshape(N_LANDMARKS, 3)
            for i in range(MP_MAX_HANDS)]


def _juntar_maos(maos):
    return np.concatenate([m.reshape(-1) for m in maos]).astype(np.float32)


def augmentar_pose(vetor_126, rng=None, fatores_por_dedo=None, fator_largura_palma=1.0,
                    sigma_jitter_graus=2.0, angulos_rotacao_graus=(0.0, 0.0, 0.0), fator_escala=1.0,
                    validar=True):
    """Aplica reescala anatômica -> jitter articular -> rotação/escala rígida
    a uma pose de até 2 mãos (vetor de 126 = TOTAL_FEATURES). Retorna o novo
    vetor e, se validar=True, também a lista de (mao_idx, valido, motivo)."""
    rng = rng or np.random.default_rng()
    original = vetor_126
    maos_orig = _dividir_maos(original)

    maos_novas = []
    validacoes = []
    for i, mao in enumerate(maos_orig):
        nova = reescalar_dedos(mao, fatores_por_dedo, fator_largura_palma, rng=rng)
        nova = jitter_articular(nova, sigma_graus=sigma_jitter_graus, rng=rng)
        nova = rotacionar_3d(nova, angulos_rotacao_graus)
        nova = escalar_isotropico(nova, fator_escala)

        if validar:
            ok, motivo = validar_biomecanica(nova, mao)
            validacoes.append((i, ok, motivo))
            if not ok:
                nova = mao  # descarta a variação inválida, mantém a pose original

        maos_novas.append(nova)

    saida = _juntar_maos(maos_novas)
    return (saida, validacoes) if validar else saida


def augmentar_sequencia(seq_T_126, rng=None, sigma_jitter_graus=2.0, validar=True):
    """Gera UMA variação sintética de uma sequência dinâmica inteira.

    Os parâmetros "lentos" (reescala de dedo, rotação, escala) são sorteados
    UMA VEZ e aplicados em TODOS os frames — porque mão-maior-que-a-outra-
    pessoa ou câmera-um-pouco-rotacionada são constantes ao longo do vídeo,
    não mudam frame a frame. Só o jitter articular é resorteado a cada
    frame, simulando a micro-variação natural de execução."""
    rng = rng or np.random.default_rng()
    seq = np.asarray(seq_T_126, dtype=np.float32)
    T = seq.shape[0]

    fatores_por_dedo = {dedo: float(rng.uniform(0.9, 1.1)) for dedo in DEDOS}
    fator_largura_palma = float(rng.uniform(0.93, 1.07))
    angulos_rotacao = tuple(float(rng.uniform(-8.0, 8.0)) for _ in range(3))
    fator_escala = float(rng.uniform(0.9, 1.1))

    saida = np.empty_like(seq)
    descartes = 0
    for t in range(T):
        nova, validacoes = augmentar_pose(
            seq[t], rng=rng,
            fatores_por_dedo=fatores_por_dedo,
            fator_largura_palma=fator_largura_palma,
            sigma_jitter_graus=sigma_jitter_graus,
            angulos_rotacao_graus=angulos_rotacao,
            fator_escala=fator_escala,
            validar=validar,
        )
        saida[t] = nova
        if validar:
            descartes += sum(1 for _, ok, _ in validacoes if not ok)

    return (saida, descartes) if validar else saida
