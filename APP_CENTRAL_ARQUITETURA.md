# 🎯 Aplicativo Central Multi-IA - KONECTA Intelligence Hub

**Objetivo:** Sistema distribuído de reconhecimento de Libras com **máxima acurácia** + **mínima latência**

**IAs Disponíveis:** Claude, Gemini, Codex, Grok, OpenCode, Cursor

---

## 🏗️ Arquitetura

```
┌──────────────────────────────────────────────────────────┐
│         KONECTA INTELLIGENCE HUB                         │
│    (Janela Flutuante - Multiplataforma)                 │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  UI: Captura vídeo + mostra resultado em tempo  │   │
│  │  real + histórico de sinais                     │   │
│  └──────────────────────────────────────────────────┘   │
│                       │                                  │
│  ┌────────────────────▼─────────────────────────────┐   │
│  │    PIPELINE DE RECONHECIMENTO (Paralelo)        │   │
│  │                                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐            │   │
│  │  │ KONECTA V3   │  │ GEMINI VISION│ (paralelo) │   │
│  │  │ (Rápido)     │  │ (Acurado)    │            │   │
│  │  │ 250ms        │  │ 300ms        │            │   │
│  │  └──────────────┘  └──────────────┘            │   │
│  │         │                  │                   │   │
│  │         └──────────┬───────┘                   │   │
│  │                    ▼                           │   │
│  │         ┌─────────────────────┐                │   │
│  │         │ Validação Cruzada   │                │   │
│  │         │ (Resultado imediato)│                │   │
│  │         └──────────┬──────────┘                │   │
│  │                    │                           │   │
│  │    ┌───────────────┴──────────────┐            │   │
│  │    ▼                              ▼            │   │
│  │ Confiança > 0.85             Confiança         │   │
│  │ Resultado → Cache             0.7-0.85        │   │
│  │            → N8N              ↓                │   │
│  │            (async)        CLAUDE LOGIC        │   │
│  │                           Valida contexto     │   │
│  │                           ↓                   │   │
│  │                           Cache → N8N        │   │
│  │                                               │   │
│  │    ┌──────────────────────────────────┐       │   │
│  │    │ Confiança < 0.7                  │       │   │
│  │    │ ↓                                │       │   │
│  │    │ GROK CONTEXT (histórico)         │       │   │
│  │    │ RETRY com modelo ensemble        │       │   │
│  │    │ → Resultado refinado → Cache     │       │   │
│  │    └──────────────────────────────────┘       │   │
│  └──────────────────────────────────────────────┘   │
│                       │                              │
│  ┌────────────────────▼──────────────────────────┐  │
│  │    CACHE LOCAL (Zero Latência)                │  │
│  │    • Sinais mais recentes                     │  │
│  │    • Histórico de usuário                     │  │
│  │    • Embeddings pré-computados                │  │
│  └────────────────────┬──────────────────────────┘  │
│                       │                              │
│  ┌────────────────────▼──────────────────────────┐  │
│  │    N8N (Assincronamente)                      │  │
│  │    • Não bloqueia UI                          │  │
│  │    • Enriquece contexto                       │  │
│  │    • Integra com outras plataformas           │  │
│  └─────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

---

## 📊 Distribuição de Responsabilidades

| IA | Função | Latência | Quando Usar |
|-------|--------|----------|------------|
| **KONECTA V3** | Classificação rápida (RF/MLP) | 100-150ms | Sempre (primária) |
| **Gemini Vision** | Validação de landmarks | 200-300ms | Paralelo a V3 |
| **Claude** | Lógica contextual + fallback | 200-500ms | Quando confiança 0.7-0.85 |
| **Grok** | Contexto histórico + dados | 300-1000ms | Quando confiança < 0.7 |
| **Codex/OpenCode** | Otimizações dinâmicas | N/A | Background (melhoria contínua) |

---

## 💻 Estrutura de Arquivos

```
KONECTA_V3/
├── app_central/
│   ├── __init__.py
│   ├── main.py                      # Aplicativo principal (PyQt5)
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── floating_window.py        # Janela flutuante
│   │   ├── dashboard.py              # Dashboard em tempo real
│   │   └── styles.css
│   │
│   ├── motors/
│   │   ├── __init__.py
│   │   ├── motor_base.py             # Classe base
│   │   ├── motor_konecta_v3.py       # V3 reconhecimento
│   │   ├── motor_gemini_vision.py    # Gemini vision
│   │   ├── motor_claude_logic.py     # Claude lógica
│   │   ├── motor_grok_context.py     # Grok contexto
│   │   └── motor_codex_optimize.py   # Codex otimização
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── recognizer_pipeline.py    # Orquestração
│   │   ├── cache_manager.py          # Cache local
│   │   ├── confidence_validator.py   # Validação cruzada
│   │   └── performance_monitor.py    # Métricas
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── config.yaml               # Configuração central
│   │   ├── api_keys.yaml             # Chaves IAs (gitignored)
│   │   └── models.yaml               # Modelos carregados
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── video_capture.py          # Captura de vídeo
│   │   ├── audio_capture.py          # Captura de áudio
│   │   ├── logger.py                 # Logging
│   │   └── metrics.py                # Métricas
│   │
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── n8n_client.py             # Cliente N8N
│   │   ├── konecta_v3_client.py      # Cliente KONECTA V3
│   │   └── webhook_listener.py       # Listener de webhooks
│   │
│   └── requirements.txt
│
├── models/
│   └── v1/
│       ├── classifier.joblib
│       └── metadata.json
│
├── start_app_central.bat            # Script inicialização (Windows)
├── start_app_central.sh             # Script inicialização (Linux/Mac)
└── README.md
```

---

## 🔧 Scripts para Cada Motor IA

### **1. Motor KONECTA V3** (`motor_konecta_v3.py`)

**Responsabilidade:** Reconhecimento rápido (primário)

```python
import joblib
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Tuple
import time

class MotorKonectaV3:
    """Motor de reconhecimento rápido usando modelos treinados."""
    
    def __init__(self, model_path: str = "models/v1"):
        self.model_path = Path(model_path)
        self.classifier = joblib.load(self.model_path / "classifier.joblib")
        self.sequence_model = None  # BiLSTM se disponível
        self.metadata = joblib.load(self.model_path / "metadata.json")
        self.cache = {}
        
    async def process(self, frame: np.ndarray) -> Dict:
        """Processa frame em < 150ms."""
        start = time.time()
        
        try:
            # Extrai landmarks (MediaPipe)
            landmarks = self._extract_landmarks(frame)
            
            # Classifica
            prediction = self.classifier.predict(landmarks)
            confidence = self.classifier.predict_proba(landmarks).max()
            
            # Calcula latência
            latency = (time.time() - start) * 1000
            
            return {
                "model": "konecta_v3",
                "signal": self.metadata["labels"][prediction[0]],
                "confidence": float(confidence),
                "latency_ms": latency,
                "landmarks": landmarks.tolist(),
                "status": "success"
            }
        except Exception as e:
            return {
                "model": "konecta_v3",
                "status": "error",
                "error": str(e)
            }
    
    def _extract_landmarks(self, frame):
        """Extrai landmarks com MediaPipe."""
        # Implementação com MediaPipe HandLandmarker
        pass
```

---

### **2. Motor Gemini Vision** (`motor_gemini_vision.py`)

**Responsabilidade:** Validação de landmarks (acurácia)

```python
import anthropic
import base64
import json
from typing import Dict
import time

class MotorGeminiVision:
    """Validação de qualidade de vídeo e landmarks."""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20241022"  # Com visão
        
    async def validate(self, frame_base64: str, landmarks: list) -> Dict:
        """Valida qualidade do frame e landmarks em < 300ms."""
        start = time.time()
        
        try:
            # Análise de visão
            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": frame_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": """
                                Analise este frame de vídeo de Libras:
                                1. Qualidade da imagem (0-100)
                                2. Posição das mãos (centralizada? visível?)
                                3. Iluminação adequada?
                                4. Landmarks detectáveis?
                                
                                Responda em JSON:
                                {"quality": X, "hands_visible": bool, "lighting_ok": bool, "valid": bool}
                                """
                            }
                        ]
                    }
                ]
            )
            
            # Parse resposta
            content = response.content[0].text
            validation = json.loads(content)
            
            latency = (time.time() - start) * 1000
            
            return {
                "model": "gemini_vision",
                "valid": validation["valid"],
                "quality_score": validation["quality"],
                "hands_visible": validation["hands_visible"],
                "lighting_ok": validation["lighting_ok"],
                "latency_ms": latency,
                "status": "success"
            }
        except Exception as e:
            return {
                "model": "gemini_vision",
                "status": "error",
                "error": str(e),
                "valid": False
            }
```

---

### **3. Motor Claude Logic** (`motor_claude_logic.py`)

**Responsabilidade:** Lógica contextual e fallback

```python
import anthropic
from typing import Dict
import json
import time

class MotorClaudeLogic:
    """Orquestrador de lógica e decisões."""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20241022"
        
    async def validate_with_context(self, 
                                   signal: str,
                                   confidence: float,
                                   user_history: list,
                                   landmarks_quality: Dict) -> Dict:
        """
        Valida resultado com contexto.
        Usado quando: 0.7 <= confidence <= 0.85
        """
        start = time.time()
        
        try:
            prompt = f"""
            Você é um validador de sinais em Libras.
            
            RESULTADO DO MODELO:
            - Sinal identificado: {signal}
            - Confiança: {confidence}
            - Qualidade dos landmarks: {landmarks_quality['quality_score']}/100
            - Mãos visíveis: {landmarks_quality['hands_visible']}
            
            CONTEXTO DO USUÁRIO:
            - Sinais recentes: {user_history[-5:]}
            - Padrão: {self._analyze_pattern(user_history)}
            
            TAREFA:
            1. O resultado faz sentido contextualmente?
            2. É provável que o usuário tenha feito este sinal?
            3. Qual é sua confiança? (0-100%)
            
            Responda em JSON:
            {{
                "is_valid": bool,
                "confidence_adjusted": float,
                "reasoning": "str",
                "recommendation": "accept|retry|request_clarification"
            }}
            """
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.content[0].text
            result = json.loads(content)
            
            latency = (time.time() - start) * 1000
            
            return {
                "model": "claude_logic",
                "validated": result["is_valid"],
                "confidence_adjusted": result["confidence_adjusted"],
                "reasoning": result["reasoning"],
                "recommendation": result["recommendation"],
                "latency_ms": latency,
                "status": "success"
            }
        except Exception as e:
            return {
                "model": "claude_logic",
                "status": "error",
                "error": str(e)
            }
    
    def _analyze_pattern(self, history):
        """Analisa padrão de sinais."""
        if not history:
            return "sem histórico"
        return f"últimos sinais: {history[-5:]}"
```

---

### **4. Motor Grok Context** (`motor_grok_context.py`)

**Responsabilidade:** Contexto histórico (quando confiança < 0.7)

```python
import json
from typing import Dict, List
from datetime import datetime
import time

class MotorGrokContext:
    """Análise de contexto e histórico."""
    
    def __init__(self, db_path: str = "cache/signals.db"):
        self.db_path = db_path
        self.history = self._load_history()
        
    async def enrich_with_context(self,
                                  low_confidence_signal: str,
                                  confidence: float,
                                  user_id: str) -> Dict:
        """
        Enriquece predição com contexto.
        Usado quando: confidence < 0.7
        """
        start = time.time()
        
        try:
            # Busca contexto
            user_history = self._get_user_history(user_id)
            similar_signals = self._find_similar(low_confidence_signal)
            time_context = self._get_time_context()
            
            # Análise
            enriched = {
                "original_signal": low_confidence_signal,
                "original_confidence": confidence,
                "user_history": user_history[-10:],
                "similar_signals_in_history": similar_signals,
                "time_of_day": time_context,
                "most_likely_signal": self._vote_signals(
                    low_confidence_signal, 
                    similar_signals
                ),
                "latency_ms": (time.time() - start) * 1000,
                "status": "success"
            }
            
            return enriched
        except Exception as e:
            return {
                "model": "grok_context",
                "status": "error",
                "error": str(e)
            }
    
    def _load_history(self):
        """Carrega histórico de cache."""
        try:
            with open(self.db_path, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _get_user_history(self, user_id: str) -> List[str]:
        """Retorna histórico do usuário."""
        return self.history.get(user_id, {}).get("signals", [])
    
    def _find_similar(self, signal: str) -> List[str]:
        """Encontra sinais similares no histórico."""
        # Implementação com similarity search
        pass
    
    def _get_time_context(self) -> str:
        """Retorna contexto temporal."""
        hour = datetime.now().hour
        if 6 <= hour < 12:
            return "manhã"
        elif 12 <= hour < 18:
            return "tarde"
        else:
            return "noite"
    
    def _vote_signals(self, primary: str, similar: List[str]) -> str:
        """Vota entre sinais com base no histórico."""
        # Implementação com votação ponderada
        pass
```

---

### **5. Motor Codex Optimize** (`motor_codex_optimize.py`)

**Responsabilidade:** Otimizações dinâmicas (background)

```python
import anthropic
import json
from typing import Dict
import time

class MotorCodexOptimize:
    """Otimizações contínuas de performance."""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20241022"
        
    async def suggest_optimizations(self, metrics: Dict) -> Dict:
        """
        Sugere otimizações baseado em métricas.
        Roda em background (não bloqueia).
        """
        start = time.time()
        
        try:
            prompt = f"""
            Você é especialista em otimização de IA e latência.
            
            MÉTRICAS ATUAIS:
            {json.dumps(metrics, indent=2)}
            
            CONTEXTO:
            - Sistema de reconhecimento de Libras
            - Usuários esperam latência < 1s
            - Rodando em múltiplas máquinas
            
            TAREFA:
            1. Identifique gargalos de performance
            2. Sugira otimizações específicas de código
            3. Classifique por impacto (alto/médio/baixo)
            4. Estime ganho de latência
            
            Responda em JSON:
            {{
                "gargalos": [
                    {{"area": "str", "impacto": "ms"}}
                ],
                "otimizacoes": [
                    {{
                        "descricao": "str",
                        "impacto_esperado_ms": float,
                        "complexidade": "low|medium|high",
                        "codigo_snippet": "str"
                    }}
                ],
                "prioridade": ["otimizacao1", "otimizacao2"]
            }}
            """
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.content[0].text
            suggestions = json.loads(content)
            
            return {
                "model": "codex_optimize",
                "suggestions": suggestions,
                "generated_at": time.time(),
                "latency_ms": (time.time() - start) * 1000,
                "status": "success"
            }
        except Exception as e:
            return {
                "model": "codex_optimize",
                "status": "error",
                "error": str(e)
            }
```

---

## 🚀 Pipeline Orquestrador (`recognizer_pipeline.py`)

```python
import asyncio
from typing import Dict
import time

class RecognizerPipeline:
    """Orquestra todos os motores em paralelo."""
    
    def __init__(self, config: Dict):
        self.konecta = MotorKonectaV3()
        self.gemini = MotorGeminiVision(config["gemini_api_key"])
        self.claude = MotorClaudeLogic(config["claude_api_key"])
        self.grok = MotorGrokContext()
        self.cache = CacheManager()
        
    async def process_frame(self, frame, user_id: str) -> Dict:
        """
        Pipeline principal:
        1. KONECTA V3 + Gemini Vision em paralelo
        2. Validação cruzada
        3. Claude Logic se necessário
        4. Grok Context se necessário
        5. Cache + N8N assincronamente
        """
        start = time.time()
        
        # Fase 1: Reconhecimento paralelo
        konecta_result, gemini_result = await asyncio.gather(
            self.konecta.process(frame),
            self.gemini.validate(self._frame_to_base64(frame), None)
        )
        
        # Fase 2: Validação Cruzada
        confidence = konecta_result["confidence"]
        
        if confidence > 0.85 and gemini_result["valid"]:
            # ✅ Resultado pronto
            final_result = konecta_result
            final_result["validated_by"] = "ensemble"
            
        elif 0.7 <= confidence <= 0.85:
            # ⚠️ Precisa Claude Logic
            claude_result = await self.claude.validate_with_context(
                konecta_result["signal"],
                confidence,
                self.cache.get_user_history(user_id),
                gemini_result
            )
            final_result = {**konecta_result, **claude_result}
            
        else:  # confidence < 0.7
            # 🔍 Precisa Grok Context
            grok_result = await self.grok.enrich_with_context(
                konecta_result["signal"],
                confidence,
                user_id
            )
            final_result = {**konecta_result, **grok_result}
        
        # Fase 3: Cache + N8N (não bloqueia)
        await asyncio.gather(
            self.cache.update(user_id, final_result),
            self._notify_n8n_async(final_result, user_id)
        )
        
        total_latency = (time.time() - start) * 1000
        final_result["total_latency_ms"] = total_latency
        
        return final_result
    
    async def _notify_n8n_async(self, result: Dict, user_id: str):
        """Notifica N8N sem bloquear."""
        try:
            # WebSocket ou HTTP async
            await self.n8n_client.send_result(result, user_id)
        except:
            pass  # Falha silenciosa, não afeta UI
```

---

## 🖥️ Interface (PyQt5)

```python
import sys
from PyQt5.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
import cv2

class FloatingRecognitionWindow(QMainWindow):
    """Janela flutuante de reconhecimento."""
    
    result_signal = pyqtSignal(dict)
    
    def __init__(self, pipeline: RecognizerPipeline):
        super().__init__()
        self.pipeline = pipeline
        self.setup_ui()
        self.start_capture()
        
    def setup_ui(self):
        """Setup interface minimalista."""
        self.setWindowTitle("KONECTA Intelligence Hub")
        self.setGeometry(10, 10, 400, 300)
        
        # Estilo flutuante (sempre no topo)
        self.setWindowFlags(
            self.windowFlags() | 
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint
        )
        
        # Labels
        self.signal_label = QLabel("Aguardando...")
        self.confidence_label = QLabel("Confiança: -")
        self.latency_label = QLabel("Latência: -")
        self.history_label = QLabel("Histórico:\n-")
        
        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.signal_label)
        layout.addWidget(self.confidence_label)
        layout.addWidget(self.latency_label)
        layout.addWidget(self.history_label)
        
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
    
    def start_capture(self):
        """Inicia captura de vídeo."""
        self.worker = CaptureWorker(self.pipeline)
        self.worker.result_signal.connect(self.update_ui)
        self.worker.start()
    
    def update_ui(self, result: dict):
        """Atualiza interface com resultado."""
        signal = result.get("signal", "?")
        confidence = result.get("confidence", 0)
        latency = result.get("total_latency_ms", 0)
        
        self.signal_label.setText(f"🤟 {signal}")
        self.confidence_label.setText(f"Confiança: {confidence:.1%}")
        self.latency_label.setText(f"Latência: {latency:.0f}ms")
```

---

## ⚙️ Configuração Central (`config.yaml`)

```yaml
# KONECTA Intelligence Hub Config

app:
  name: "KONECTA Intelligence Hub"
  version: "1.0.0"
  window:
    floating: true
    always_on_top: true
    width: 400
    height: 300

motors:
  konecta_v3:
    enabled: true
    model_path: "models/v1"
    timeout_ms: 150
    priority: "primary"
    
  gemini_vision:
    enabled: true
    api_key: "${GEMINI_API_KEY}"
    timeout_ms: 300
    priority: "parallel"
    model: "claude-3-5-sonnet-20241022"
    
  claude_logic:
    enabled: true
    api_key: "${CLAUDE_API_KEY}"
    timeout_ms: 500
    priority: "fallback"
    trigger_confidence_range: [0.7, 0.85]
    
  grok_context:
    enabled: true
    timeout_ms: 1000
    priority: "fallback"
    trigger_confidence: 0.7
    
  codex_optimize:
    enabled: true
    api_key: "${CLAUDE_API_KEY}"
    timeout_ms: null  # Background, sem timeout
    priority: "background"

pipeline:
  parallel_processing: true
  cache_enabled: true
  cache_ttl_seconds: 3600
  confidence_threshold: 0.7

n8n:
  enabled: true
  webhook_url: "http://localhost:5678/webhook/signal-recognized"
  timeout_ms: 100  # Não bloqueia
  async_only: true

logging:
  level: "INFO"
  file: "logs/app_central.log"

performance:
  target_latency_ms: 1000
  alert_latency_ms: 1500
  collect_metrics: true
```

---

## 🚀 Inicialização

### Windows
```batch
@echo off
cd /d "%~dp0"
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
python app_central/main.py
```

### Linux/Mac
```bash
#!/bin/bash
cd "$(dirname "$0")"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app_central/main.py
```

---

## 📊 Métricas e Monitoramento

```python
class PerformanceMonitor:
    """Monitora latência e acurácia."""
    
    metrics = {
        "konecta_v3_avg_ms": 0,
        "gemini_avg_ms": 0,
        "claude_avg_ms": 0,
        "grok_avg_ms": 0,
        "total_latency_avg_ms": 0,
        "cache_hit_rate": 0.0,
        "error_rate": 0.0,
        "signals_processed": 0,
        "confidence_distribution": {}
    }
    
    def log_result(self, result: Dict):
        """Registra resultado para análise."""
        # Atualiza métricas
        # Envia para dashboard
        # Alerta se latência > target
        pass
```

---

## ✅ Checklist de Implementação

- [ ] Estrutura de pastas criada
- [ ] Motor KONECTA V3 integrado
- [ ] Motor Gemini Vision conectado
- [ ] Motor Claude Logic funcional
- [ ] Motor Grok Context configurado
- [ ] Pipeline orquestrador pronto
- [ ] Interface PyQt5 funcionando
- [ ] Cache local implementado
- [ ] N8N webhook integrado
- [ ] Métricas coletando dados
- [ ] Testes de latência passando
- [ ] Documentação completa
- [ ] Deploy em Windows/Linux/Mac

**Status:** Pronto para desenvolvimento 🚀
