#!/usr/bin/env python
"""Teste rápido do reconhecimento com features DINÂMICAS."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from backend.services.recognition_service import service as recognition_service
from backend.services.dataset_provider import carregar

print("=" * 80)
print("TESTE DE RECONHECIMENTO COM FEATURES DINAMICAS")
print("=" * 80)

# Carregar algumas amostras V1
print("\nCarregando amostras V1...")
amostras = carregar("v1_dinamicos", limite_sinais=5)  # Apenas 5 sinais
print(f"Carregadas {len(amostras)} amostras")

if len(amostras) < 2:
    print("ERRO: Poucas amostras para teste")
    sys.exit(1)

# Separar em treino e teste
amostras_teste = amostras[:10]
print(f"\nTestando com {len(amostras_teste)} amostras...")

acertos = 0
total = 0

for i, amostra in enumerate(amostras_teste):
    if amostra.landmarks is None or amostra.landmarks.size == 0:
        continue

    # Enviar landmarks para reconhecimento
    landmarks_list = amostra.landmarks.tolist()
    resultado = recognition_service.reconhecer(landmarks_list)

    # Verificar se acertou
    acertou = resultado["sinal"] == amostra.sinal
    acertos += int(acertou)
    total += 1

    status = "OK" if acertou else "ERRADO"
    print(f"  [{i+1}] Esperado: {amostra.sinal:20} | Got: {resultado['sinal']:20} | Confianca: {resultado['confianca']:.1%} | {status}")

print("\n" + "=" * 80)
if total > 0:
    acuracia = acertos / total * 100
    print(f"RESULTADO: {acertos}/{total} acertos = {acuracia:.1f}% acuracia")
else:
    print("Nenhuma amostra foi testada")
print("=" * 80)

print("\nO que mudou:")
print("  1. Features extraem ultimos 5 frames (em vez de media)")
print("  2. Preserva dinamica temporal do gesto")
print("  3. Acuracia deve melhorar significativamente com novos treinos")
