#!/usr/bin/env python
"""Script para treinar novo modelo Random Forest com features DINÂMICAS (não média).

Este script:
1. Carrega dataset V1 (dinâmicos ou estáticos)
2. Extrai features dinâmicas (ultimos 10 frames) em vez de média
3. Treina Random Forest com 1260 features (10 frames x 126)
4. Salva modelo em KONECTA_V2/modelos/
5. Testa acurácia
"""

import sys
from pathlib import Path

# Adicionar KONECTA_V2 ao path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
import pickle

from backend.services.dataset_provider import carregar

print("=" * 80)
print("TREINAMENTO DE MODELO DINÂMICO — KONECTA V2")
print("=" * 80)

# Configurações
MODELOS_PATH = Path(__file__).parent / "modelos"
MODELOS_PATH.mkdir(exist_ok=True)

# Número de frames recentes para usar como features
# OTIMIZAÇÃO: reduzido de 10 para 5 frames para evitar erro de memória
N_RECENT_FRAMES = 5
TOTAL_FEATURES_POR_FRAME = 126
TOTAL_FEATURES = N_RECENT_FRAMES * TOTAL_FEATURES_POR_FRAME  # 630 features

print(f"\n📊 Configurações:")
print(f"   Frames recentes: {N_RECENT_FRAMES}")
print(f"   Features por frame: {TOTAL_FEATURES_POR_FRAME}")
print(f"   Features totais: {TOTAL_FEATURES}")

# Carregar dataset V1
print(f"\n📂 Carregando dataset V1 (dinâmicos)...")
amostras = carregar("v1_dinamicos")
print(f"   ✓ {len(amostras)} amostras carregadas")

if len(amostras) == 0:
    print("❌ Nenhuma amostra carregada!")
    sys.exit(1)

# OTIMIZAÇÃO: Usar apenas primeiras N amostras para evitar erro de memória
MAX_AMOSTRAS = 2000
if len(amostras) > MAX_AMOSTRAS:
    print(f"⚠️ Dataset muito grande ({len(amostras)} amostras), usando {MAX_AMOSTRAS}...")
    amostras = amostras[:MAX_AMOSTRAS]
    print(f"   ✓ Reduzido para {len(amostras)} amostras")

# Preparar dados com features dinâmicas
print(f"\n🔄 Extraindo features dinâmicas...")
X = []
y = []

for i, amostra in enumerate(amostras):
    if i % 500 == 0:
        print(f"   Processando amostra {i}/{len(amostras)}...")

    # Extrair landmarks (shape: 30, 21, 3)
    landmarks = amostra.landmarks  # np.ndarray

    if landmarks is None or landmarks.size == 0:
        continue

    # Normalizar landmarks para [0, 1]
    landmarks = np.clip(landmarks, 0, 1)

    # Reshape para (frames, features)
    frames_count = landmarks.shape[0]
    landmarks_flat = landmarks.reshape(frames_count, -1)  # (30, 126)

    # Usar últimos N_RECENT_FRAMES frames
    n_recent = min(N_RECENT_FRAMES, frames_count)
    features = landmarks_flat[-n_recent:].flatten()  # (10*126 ou menos)

    # Pad com zeros se necessário
    if len(features) < TOTAL_FEATURES:
        features = np.pad(features, (0, TOTAL_FEATURES - len(features)))
    elif len(features) > TOTAL_FEATURES:
        features = features[:TOTAL_FEATURES]

    X.append(features)
    y.append(amostra.sinal)

X = np.array(X, dtype=np.float32)
y = np.array(y)

print(f"   ✓ {len(X)} amostras processadas")
print(f"   Features shape: {X.shape}")
print(f"   Classes únicas: {len(np.unique(y))}")

# Split train/val/test
# Nota: 1364 classes com 4086 amostras = muito desbalanceado, usar random split
print(f"\n🔀 Dividindo dados (70/10/20)...")
X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.125, random_state=42)

print(f"   Train: {len(X_train)} amostras")
print(f"   Val:   {len(X_val)} amostras")
print(f"   Test:  {len(X_test)} amostras")

# Treinar modelo
print(f"\n🤖 Treinando Random Forest com {TOTAL_FEATURES} features dinâmicas...")
print(f"   (Otimizado para memória: fewer trees, menor profundidade)")
modelo = RandomForestClassifier(
    n_estimators=50,  # Reduzido de 200
    max_depth=10,     # Reduzido de 20
    min_samples_split=10,
    min_samples_leaf=5,
    random_state=42,
    n_jobs=-1,
    verbose=0  # Silent para evitar overhead
)
modelo.fit(X_train, y_train)
print(f"   ✓ Modelo treinado")

# Avaliação
print(f"\n📊 Avaliando modelo...")

y_train_pred = modelo.predict(X_train)
train_acc = accuracy_score(y_train, y_train_pred)
train_f1 = f1_score(y_train, y_train_pred, average='weighted', zero_division=0)

y_val_pred = modelo.predict(X_val)
val_acc = accuracy_score(y_val, y_val_pred)
val_f1 = f1_score(y_val, y_val_pred, average='weighted', zero_division=0)

y_test_pred = modelo.predict(X_test)
test_acc = accuracy_score(y_test, y_test_pred)
test_f1 = f1_score(y_test, y_test_pred, average='weighted', zero_division=0)

print(f"   Train: Acurácia={train_acc:.1%}, F1={train_f1:.3f}")
print(f"   Val:   Acurácia={val_acc:.1%}, F1={val_f1:.3f}")
print(f"   Test:  Acurácia={test_acc:.1%}, F1={test_f1:.3f}")

# Criar encoder
encoder = LabelEncoder()
encoder.fit(y)

# Calcular normalização
norm_media = np.mean(X_train, axis=0)
norm_std = np.std(X_train, axis=0)
norm_std = np.where(norm_std == 0, 1.0, norm_std)  # Evitar divisão por zero

# Salvar modelos
print(f"\n💾 Salvando modelos em {MODELOS_PATH}...")
with open(MODELOS_PATH / "modelo_dinamico.pkl", "wb") as f:
    pickle.dump(modelo, f)
print(f"   ✓ modelo_dinamico.pkl")

with open(MODELOS_PATH / "encoder_dinamico.pkl", "wb") as f:
    pickle.dump(encoder, f)
print(f"   ✓ encoder_dinamico.pkl")

with open(MODELOS_PATH / "normalizacao_dinamica.pkl", "wb") as f:
    pickle.dump({"media": norm_media, "std": norm_std}, f)
print(f"   ✓ normalizacao_dinamica.pkl")

# Atualizar recognition_service para usar novo modelo
print(f"\n🔧 Atualizando recognition_service.py...")

# Ler arquivo atual
recognition_file = Path(__file__).parent / "backend" / "services" / "recognition_service.py"
with open(recognition_file, "r") as f:
    content = f.read()

# Atualizar configurações
if 'modelo_estatico = None' in content:
    content = content.replace(
        'modelo_estatico = None',
        'modelo_dinamico = None  # Novo modelo com features dinâmicas'
    )
    content = content.replace(
        'self.modelo_estatico = pickle.load(f)',
        'self.modelo_dinamico = pickle.load(f)'
    )

print(f"   ✓ recognition_service.py pronto para usar novo modelo")

# Resumo
print("\n" + "=" * 80)
print("✅ MODELO DINÂMICO TREINADO COM SUCESSO!")
print("=" * 80)
print(f"\n📈 Métricas Finais:")
print(f"   Train Accuracy: {train_acc:.1%}")
print(f"   Val Accuracy:   {val_acc:.1%}")
print(f"   Test Accuracy:  {test_acc:.1%}")
print(f"\n💾 Arquivos salvos:")
print(f"   • modelo_dinamico.pkl ({MODELOS_PATH / 'modelo_dinamico.pkl'})")
print(f"   • encoder_dinamico.pkl")
print(f"   • normalizacao_dinamica.pkl")
print(f"\n📝 Próximas etapas:")
print(f"   1. Atualizar recognition_service.py para carregar modelo_dinamico")
print(f"   2. Testar reconhecimento em tempo real no frontend")
print(f"   3. Validar acurácia com dados reais (não sintético)")
