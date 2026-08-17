#!/usr/bin/env python
"""Quick test of capture and recognition"""

from vision_lab.training import BaselineTrainer
from vision_lab.realtime import RealtimeRecognizer
from vision_lab.landmarks import LandmarkExtractor
from vision_lab.processing import LandmarkNormalizer
import numpy as np
import cv2

print("=" * 80)
print("KONECTA V3 - TESTE RAPIDO DE CAPTURA E RECONHECIMENTO")
print("=" * 80)

# ============================================
# STEP 1: Treinar modelo
# ============================================

print("\n[PASSO 1] Treinando modelo...")

X_train = np.random.randn(100, 228).astype(np.float32)
y_train = np.array(["CASA"] * 50 + ["CARRO"] * 50 + ["LIVRO"] * 50)[:100]

trainer = BaselineTrainer(n_estimators=50)
metrics = trainer.train(X_train, y_train)

print(f"[OK] Modelo treinado!")
print(f"     Accuracy: {metrics['accuracy']:.2%}")
print(f"     F1: {metrics['f1']:.4f}")

# ============================================
# STEP 2: Testar com frames simulados
# ============================================

print("\n[PASSO 2] Testando com frames simulados...")

extractor = LandmarkExtractor()
recognizer = RealtimeRecognizer(model=trainer)

# Simular 10 frames da webcam
for frame_id in range(10):
    # Frame dummy (você pode substituir por cap.read() de verdade)
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Processar
    prediction, confidence, latency = recognizer.process_frame(frame)

    print(f"Frame {frame_id:02d}: {prediction if prediction else 'None':10s} | Conf: {confidence:.2%} | Latency: {latency:.1f}ms")

avg_latency = recognizer.get_average_latency()
avg_fps = recognizer.get_average_fps()

print(f"\n[OK] Teste completado!")
print(f"     Avg Latency: {avg_latency:.1f}ms")
print(f"     Avg FPS: {avg_fps:.1f}")

# ============================================
# STEP 3: Opção de usar webcam de verdade
# ============================================

print("\n" + "=" * 80)
print("PROXIMA ETAPA: Usar webcam de verdade")
print("=" * 80)
print("\nPara usar SUA WEBCAM de verdade, execute:")
print("  python run_realtime_webcam.py")
print("\nIsso vai:")
print("  1. Abrir sua webcam")
print("  2. Detectar seu corpo em tempo real")
print("  3. Reconhecer qual sinal voce esta fazendo")
print("  4. Mostrar confianca, FPS e latencia")
print("\nTecle ESC para sair")
print("\n" + "=" * 80)
