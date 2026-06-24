#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher para Libras OCR
- Funciona em QUALQUER PC (Windows, Mac, Linux)
- Detecta automaticamente caminhos
- Seta variáveis de ambiente corretamente
- Instala dependências se faltarem
"""

import os
import sys
from pathlib import Path

# Detecta caminho base (funciona em qualquer lugar)
if getattr(sys, 'frozen', False):
    # Executando como EXE
    BASE_DIR = Path(sys.executable).parent.parent
else:
    # Executando como script Python
    BASE_DIR = Path(__file__).resolve().parent

# Seta variáveis de ambiente para libras_recognizer.py
os.environ['LIBRAS_BASE_DIR'] = str(BASE_DIR)
os.environ['PYTHONPATH'] = str(BASE_DIR)

# Add current directory to path
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

print("=" * 70)
print("  LIBRAS OCR - Sistema de Reconhecimento de LIBRAS")
print("=" * 70)
print()
print(f"📍 Pasta base: {BASE_DIR}")
print()

# Verifica módulos essenciais
REQUIRED_MODULES = {
    'cv2': 'opencv-python',
    'mediapipe': 'mediapipe',
    'numpy': 'numpy',
    'PIL': 'pillow',
    'sklearn': 'scikit-learn',
    'tkinter': None,  # built-in
}

print("Verificando dependências...")
missing_modules = []
for module_name, package_name in REQUIRED_MODULES.items():
    try:
        __import__(module_name)
        print(f"  ✓ {module_name}")
    except ImportError:
        if package_name:
            print(f"  ✗ {module_name} (faltando)")
            missing_modules.append(package_name)
        else:
            print(f"  ✗ {module_name} (built-in não disponível)")

# TensorFlow é opcional (tenta importar)
try:
    __import__('tensorflow')
    print(f"  ✓ tensorflow")
except ImportError:
    print(f"  ⚠ tensorflow (opcional)")

if missing_modules:
    print()
    print("⚠️  Instalando dependências faltantes...")
    import subprocess
    for package in missing_modules:
        try:
            print(f"  → {package}...", end=" ", flush=True)
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', '-q', package],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("✓")
        except Exception as e:
            print(f"✗ ({e})")

print()
print("=" * 70)
print("  Iniciando aplicação...")
print("=" * 70)
print()

# Executa libras_recognizer.py diretamente (no final dele tem if __name__ == "__main__")
try:
    # Torna current_dir = BASE_DIR para que imports funcionem
    os.chdir(BASE_DIR)

    # Executa como módulo
    import runpy
    runpy.run_path(str(BASE_DIR / 'libras_recognizer.py'), run_name='__main__')

except FileNotFoundError:
    print(f"❌ ERRO: libras_recognizer.py não encontrado em {BASE_DIR}")
    print()
    input("Pressione ENTER para sair...")
    sys.exit(1)
except Exception as e:
    print(f"❌ ERRO ao executar: {e}")
    print()
    import traceback
    traceback.print_exc()
    print()
    input("Pressione ENTER para sair...")
    sys.exit(1)
