"""
Teste automatizado do fluxo completo
Simula: Captura → Processa → Treina → Reconhece
"""

import cv2
import numpy as np
import requests
import base64
import time

BASE_URL = "http://localhost:9000/api"

print("=" * 50)
print("TESTE COMPLETO DO SISTEMA KONECTA V2")
print("=" * 50)

# 1. Testar backend
print("\n✓ Teste 1: Conexão com Backend")
try:
    r = requests.get(f"{BASE_URL}/health", timeout=3)
    print(f"  Status: {r.status_code}")
    print(f"  Resposta: {r.json()}")
except Exception as e:
    print(f"  ❌ Erro: {e}")
    exit(1)

# 2. Capturar frames
print("\n✓ Teste 2: Captura de Frames")
cap = cv2.VideoCapture(1)
if not cap.isOpened():
    cap = cv2.VideoCapture(0)

frames = []
print("  Capturando 20 frames...")
for i in range(20):
    ret, frame = cap.read()
    if ret:
        frames.append(frame)
    time.sleep(0.05)
cap.release()
print(f"  Capturados: {len(frames)} frames ✓")

# 3. Processar frames
print("\n✓ Teste 3: Processamento de Frames (Backend)")
frames_b64 = []
for frame in frames:
    _, buf = cv2.imencode('.jpg', frame)
    frames_b64.append(base64.b64encode(buf).decode())

payload = {"sinal": "A", "frames": frames_b64}
try:
    r = requests.post(f"{BASE_URL}/processar-frames", json=payload, timeout=30)
    print(f"  Status: {r.status_code}")
    data = r.json()

    if r.status_code == 200:
        landmarks = data.get('landmarks', [])
        print(f"  Landmarks extraídos: {len(landmarks)} ✓")

        if len(landmarks) > 0:
            print(f"  Pontos por frame: {len(landmarks[0])} ✓")
    else:
        print(f"  ❌ Erro: {data}")
        exit(1)
except Exception as e:
    print(f"  ❌ Erro: {e}")
    exit(1)

# 4. Treinar modelo
print("\n✓ Teste 4: Treino de Modelo")
try:
    dados = {"A": landmarks}
    r = requests.post(f"{BASE_URL}/treinar", json=dados, timeout=30)
    print(f"  Status: {r.status_code}")

    if r.status_code == 200:
        resultado = r.json()
        if resultado.get('sucesso'):
            print(f"  ✓ Modelo treinado!")
            print(f"  Mensagem: {resultado.get('mensagem', '')}")
        else:
            print(f"  ❌ Erro: {resultado.get('erro', '')}")
    else:
        print(f"  ❌ Status: {r.status_code}")
except Exception as e:
    print(f"  ❌ Erro: {e}")
    exit(1)

# 5. Reconhecer
print("\n✓ Teste 5: Reconhecimento")
if landmarks and len(landmarks) > 0:
    # Flatten landmarks
    lms_flat = []
    for frame_lm in landmarks[:10]:  # Usar apenas 10 frames
        for point in frame_lm:
            lms_flat.extend(point)

    try:
        r = requests.post(f"{BASE_URL}/reconhecer", json=lms_flat, timeout=10)
        print(f"  Status: {r.status_code}")

        if r.status_code == 200:
            resultado = r.json()
            sinal = resultado.get('sinal', '?')
            conf = resultado.get('confianca', 0) * 100
            print(f"  Sinal reconhecido: {sinal}")
            print(f"  Confiança: {conf:.1f}% ✓")
        else:
            print(f"  ❌ Status: {r.status_code}")
    except Exception as e:
        print(f"  ❌ Erro: {e}")
else:
    print("  ⚠ Sem landmarks para testar reconhecimento")

print("\n" + "=" * 50)
print("✅ TODOS OS TESTES COMPLETOS!")
print("=" * 50)
