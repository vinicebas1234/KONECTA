# 🔗 Arquitetura de Integração - KONECTA V3 + N8N

**Status:** Planejamento Técnico  
**Data:** 2026-08-11  
**Equipe:** Vinicius (Reconhecimento), Colega-X (Audio-Texto), Colega-Y (Texto-Libras)

---

## 📋 Índice
1. [Visão Geral](#visão-geral)
2. [Componentes da Arquitetura](#componentes)
3. [Fluxos de Comunicação](#fluxos)
4. [APIs de Cada Motor](#apis)
5. [Integração com N8N](#n8n)
6. [Exemplos Práticos](#exemplos)
7. [Sequência Temporal](#sequência)
8. [Performance e Latência](#performance)

---

## 🎯 Visão Geral

Sistema de comunicação **bidirecional** entre deficientes auditivos e pessoas sem deficiência usando reconhecimento de Libras, conversão de áudio-texto e texto-Libras.

```
┌─────────────────────────────────────────────────────────────────┐
│                     APLICAÇÃO FRONTEND                          │
│              (Multiplataformas via N8N)                         │
│  • Captura vídeo (câmera)                                       │
│  • Captura áudio (microfone)                                    │
│  • Exibe sinais animados (resultado)                            │
└─────────────┬──────────────────────────────┬────────────────────┘
              │                              │
              ▼                              ▼
      ┌──────────────────┐          ┌──────────────────┐
      │  KONECTA V3      │          │   N8N Workflow   │
      │  (Reconhecimento)│          │  (Orquestração)  │
      │                  │          │                  │
      │ • Motor reconh.  │◄────────►│ • Lógica fluxo   │
      │ • Modelos (.jl)  │          │ • Conecta APIs   │
      │ • MediaPipe      │          │ • Multi-plataforma
      │ • API HTTP/WS    │          │                  │
      └──────────────────┘          └──────────────────┘
              ▲                              ▲
              │                              │
      ┌───────┴──────────┬──────────────────┴───────────┐
      ▼                  ▼                               ▼
┌──────────────┐  ┌──────────────┐           ┌──────────────┐
│ Speech-Text  │  │ Text-to-Sign │           │  Banco de    │
│ (Colega-X)   │  │ (Colega-Y)   │           │   Dados      │
│              │  │              │           │              │
│ • Transcreve │  │ • Gera sinal │           │ • Histórico  │
│ • Audio→Txt  │  │ • Txt→Sinal  │           │ • Usuários   │
│ • API REST   │  │ • Animação   │           │ • Sinais     │
└──────────────┘  └──────────────┘           └──────────────┘
```

---

## 💻 Componentes da Arquitetura

### 1️⃣ **KONECTA V3** (Motor de Reconhecimento)
**Responsável:** Vinicius  
**Entrada:** Vídeo de sinal em Libras  
**Saída:** Texto identificado do sinal + confiança  

**Arquivos esperados:**
```
KONECTA_V3/
├── app/
│   ├── backend/
│   │   ├── main.py                 # FastAPI
│   │   ├── routes/
│   │   │   └── recognize.py        # POST /api/recognize
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── recognition.py      # Classe RecognitionEngine
│   │   └── database.py
│   └── frontend/
│       └── index.html              # (Optional: debug UI)
├── models/
│   ├── v1/
│   │   ├── classifier.joblib       # RF/MLP treinado
│   │   ├── sequence_model.keras    # BiLSTM/LSTM
│   │   └── metadata.json           # {labels, features}
│   └── v2/
│       └── ...
├── requirements.txt
└── start.bat
```

---

### 2️⃣ **N8N** (Orquestrador Central)
**Responsável:** N/A (ferramenta)  
**Função:** Conectar e orquestrar todos os motores  
**Porta:** 5678 (padrão N8N)

**Workflows principais:**
- ✅ Fluxo 1: Deficiente Auditivo faz sinal
  - Vídeo → KONECTA V3 → Reconhece sinal → Texto → Speech-to-Text reverso ou saída para interface
  
- ✅ Fluxo 2: Ouvinte fala
  - Audio → Speech-to-Text → Texto → Text-to-Sign → Animação de sinal

- ✅ Fluxo 3: Histórico e análise
  - Armazena interações no banco de dados

---

### 3️⃣ **Speech-to-Text** (Motor de Audio)
**Responsável:** Colega-X  
**Entrada:** Arquivo de áudio (.wav, .mp3) ou stream  
**Saída:** Texto transcrito  

**API esperada:**
```
POST http://colega-x:5000/api/transcribe
{
  "audio": <base64 ou arquivo>,
  "language": "pt-BR",
  "format": "wav"
}

Response:
{
  "text": "Olá, como você está?",
  "confidence": 0.98,
  "duration": 2.5
}
```

---

### 4️⃣ **Text-to-Sign** (Motor de Libras)
**Responsável:** Colega-Y  
**Entrada:** Texto em português  
**Saída:** Animação de sinal (vídeo, coordenadas, SVG)  

**API esperada:**
```
POST http://colega-y:6000/api/generate-sign
{
  "text": "Olá",
  "animation_format": "mp4",  # ou "coordinates", "svg"
  "speed": 1.0
}

Response:
{
  "animation_url": "http://colega-y:6000/results/abc123.mp4",
  "duration": 1.5,
  "width": 800,
  "height": 600
}
```

---

### 5️⃣ **Banco de Dados**
**Responsável:** Vinicius (ou compartilhado)  
**Dados armazenados:**
- Histórico de sinais reconhecidos
- Usuários e sessões
- Modelos de texto-to-sign (cache)
- Logs de requisições

**Tecnologia:** SQLite ou PostgreSQL

---

## 🔄 Fluxos de Comunicação

### **Fluxo 1: Deficiente Auditivo faz Sinal** 🤟

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Câmera do Deficiente Auditivo)                   │
│  1. Captura vídeo contínuo (30 fps)                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼ (HTTP POST ou WebSocket)
            ┌─────────────────────────┐
            │    KONECTA V3 API       │
            │ POST /api/recognize     │
            │ Body: {video: bytes}    │
            └────────────┬────────────┘
                         │
                         ▼
            ┌─────────────────────────┐
            │ Processamento:          │
            │ 1. MediaPipe landmarks  │
            │ 2. Extrai features      │
            │ 3. Carrega modelo v1    │
            │ 4. Prediz sinal         │
            └────────────┬────────────┘
                         │
                         ▼
            ┌─────────────────────────┐
            │  Response:              │
            │  {                      │
            │    "signal": "OLHO",    │
            │    "confidence": 0.98,  │
            │    "model": "v1"        │
            │  }                      │
            └────────────┬────────────┘
                         │
                         ▼
        ┌─────────────────────────────────────┐
        │     N8N Workflow                    │
        │  1. Recebe sinal "OLHO"             │
        │  2. Consulta banco (histórico)      │
        │  3. Transforma em mensagem texto    │
        │  4. Envia para Speech-to-Text       │
        │     reverso (se necessário)         │
        │  5. Ou armazena no histórico        │
        └────────────┬────────────────────────┘
                     │
                     ▼
        ┌─────────────────────────────────────┐
        │  Frontend (do Ouvinte)              │
        │  Exibe:                             │
        │  "Usuário fez o sinal: OLHO"        │
        │  ou áudio falado                    │
        └─────────────────────────────────────┘
```

---

### **Fluxo 2: Ouvinte fala** 🎤

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Microfone do Ouvinte)                            │
│  1. Captura áudio contínuo                                  │
│  2. Envia para Speech-to-Text                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼ (HTTP POST)
            ┌──────────────────────────────┐
            │  Speech-to-Text API          │
            │  POST /api/transcribe        │
            │  Body: {audio: bytes}        │
            └───────────┬──────────────────┘
                        │
                        ▼
            ┌──────────────────────────────┐
            │  Response:                   │
            │  {                           │
            │    "text": "Olá, tudo bem?", │
            │    "confidence": 0.95        │
            │  }                           │
            └───────────┬──────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
  (1) N8N Workflow          (2) Frontend (Cliente)
      1. Recebe texto            Exibe texto
      2. Chama Text-to-Sign      captado
      3. Gera animação
        │
        ▼
  ┌──────────────────────────────────┐
  │  Text-to-Sign API                │
  │  POST /api/generate-sign         │
  │  Body: {text: "Olá, tudo bem?"} │
  └────────┬─────────────────────────┘
           │
           ▼
  ┌──────────────────────────────────┐
  │  Response:                       │
  │  {                               │
  │    "animation_url": "..mp4",     │
  │    "duration": 3.2               │
  │  }                               │
  └────────┬─────────────────────────┘
           │
           ▼
  ┌──────────────────────────────────┐
  │  Frontend (Deficiente Auditivo)  │
  │  Exibe animação de sinal         │
  │  "Olá, tudo bem?" em Libras      │
  └──────────────────────────────────┘
```

---

## 🔌 APIs de Cada Motor

### **KONECTA V3 - Motor de Reconhecimento**

#### Endpoint 1: Reconhecer Sinal
```http
POST /api/recognize HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "video": "base64_encoded_video_bytes",
  "model_version": "v1",
  "confidence_threshold": 0.7
}
```

**Response (200 OK):**
```json
{
  "signal": "OLHO",
  "confidence": 0.98,
  "model_version": "v1",
  "processing_time_ms": 234,
  "landmarks": [
    {"x": 0.5, "y": 0.3, "z": 0.0, "visibility": 0.98},
    ...
  ]
}
```

---

#### Endpoint 2: Listar Sinais Disponíveis
```http
GET /api/signals HTTP/1.1
Host: localhost:8000
```

**Response (200 OK):**
```json
{
  "total": 57,
  "signals": [
    {"id": 1, "name": "OLHO", "model_version": "v1"},
    {"id": 2, "name": "BOCA", "model_version": "v1"},
    ...
  ],
  "model_version": "v1"
}
```

---

#### Endpoint 3: Health Check
```http
GET /api/health HTTP/1.1
Host: localhost:8000
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "model_loaded": true,
  "model_version": "v1",
  "timestamp": "2026-08-11T15:30:00Z"
}
```

---

### **Speech-to-Text API (Colega-X)**

```http
POST /api/transcribe HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "audio": "base64_encoded_audio",
  "language": "pt-BR",
  "format": "wav"
}
```

**Response (200 OK):**
```json
{
  "text": "Olá, como você está?",
  "confidence": 0.95,
  "language": "pt-BR",
  "duration_seconds": 2.5,
  "words": [
    {"word": "Olá", "confidence": 0.97, "start_time": 0.0, "end_time": 0.5}
  ]
}
```

---

### **Text-to-Sign API (Colega-Y)**

```http
POST /api/generate-sign HTTP/1.1
Host: localhost:6000
Content-Type: application/json

{
  "text": "Olá",
  "animation_format": "mp4",  # ou "coordinates", "gif"
  "speed": 1.0,
  "width": 800,
  "height": 600
}
```

**Response (200 OK):**
```json
{
  "animation_url": "http://localhost:6000/results/abc123.mp4",
  "duration_seconds": 1.2,
  "width": 800,
  "height": 600,
  "format": "mp4",
  "size_bytes": 245000,
  "timestamp": "2026-08-11T15:30:45Z"
}
```

---

## 🔗 Integração com N8N

### **Instalação e Setup**

```bash
# 1. Baixar Docker (ou instalar N8N localmente)
docker run -d -p 5678:5678 --name n8n n8nio/n8n

# 2. Acessar http://localhost:5678
# 3. Configurar os 3 webhooks (KONECTA V3, Speech-to-Text, Text-to-Sign)
```

---

### **Fluxo 1: Reconhecimento de Sinal (N8N Workflow)**

**Trigger:** Webhook POST `/webhook/recognize-signal`

```json
{
  "steps": [
    {
      "name": "Receber Video",
      "type": "webhook",
      "endpoint": "/webhook/recognize-signal",
      "method": "POST"
    },
    {
      "name": "Chamar KONECTA V3",
      "type": "http",
      "method": "POST",
      "url": "http://localhost:8000/api/recognize",
      "headers": {"Content-Type": "application/json"},
      "body": "{{ $json.payload }}"
    },
    {
      "name": "Validar Confiança",
      "type": "if",
      "condition": "confidence > 0.7"
    },
    {
      "name": "Armazenar no BD",
      "type": "postgres", 
      "query": "INSERT INTO signals (user_id, signal, confidence, timestamp) VALUES (?, ?, ?, NOW())"
    },
    {
      "name": "Retornar Resultado",
      "type": "http_response",
      "status": 200,
      "body": "{{ steps['Chamar KONECTA V3'].data }}"
    }
  ]
}
```

---

### **Fluxo 2: Áudio para Libras (N8N Workflow)**

**Trigger:** Webhook POST `/webhook/audio-to-sign`

```json
{
  "steps": [
    {
      "name": "Receber Áudio",
      "type": "webhook",
      "endpoint": "/webhook/audio-to-sign"
    },
    {
      "name": "Transcrever (Speech-to-Text)",
      "type": "http",
      "method": "POST",
      "url": "http://localhost:5000/api/transcribe",
      "body": "{{ $json.audio }}"
    },
    {
      "name": "Gerar Sinal (Text-to-Sign)",
      "type": "http",
      "method": "POST",
      "url": "http://localhost:6000/api/generate-sign",
      "body": "{ \"text\": \"{{ steps['Transcrever'].data.text }}\" }"
    },
    {
      "name": "Armazenar Histórico",
      "type": "postgres",
      "query": "INSERT INTO conversations (user_id, audio_text, animation_url) VALUES (?, ?, ?)"
    },
    {
      "name": "Retornar Animação",
      "type": "http_response",
      "body": "{{ steps['Gerar Sinal'].data }}"
    }
  ]
}
```

---

### **Fluxo 3: Sinal para Áudio (Bidirecional)**

**Trigger:** Webhook POST `/webhook/sign-to-audio`

```json
{
  "steps": [
    {
      "name": "Receber Vídeo",
      "type": "webhook",
      "endpoint": "/webhook/sign-to-audio"
    },
    {
      "name": "Reconhecer Sinal",
      "type": "http",
      "method": "POST",
      "url": "http://localhost:8000/api/recognize",
      "body": "{{ $json.video }}"
    },
    {
      "name": "Validar Resultado",
      "type": "if",
      "condition": "confidence > 0.8"
    },
    {
      "name": "Armazenar Sinal",
      "type": "postgres",
      "query": "INSERT INTO signals ..."
    },
    {
      "name": "Retornar Sinal Reconhecido",
      "type": "http_response",
      "body": "{{ steps['Reconhecer Sinal'].data }}"
    }
  ]
}
```

---

## 📝 Exemplos Práticos

### **Exemplo 1: Usuário Deficiente Auditivo Faz Sinal**

**Requisição do Frontend:**
```bash
curl -X POST http://localhost:5678/webhook/recognize-signal \
  -H "Content-Type: application/json" \
  -d '{
    "video": "base64_encoded_video_bytes...",
    "user_id": "user_123"
  }'
```

**Processamento N8N:**
1. Recebe vídeo
2. Envia para `KONECTA V3:8000/api/recognize`
3. Recebe: `{signal: "OLHO", confidence: 0.98}`
4. Armazena no BD: `signals.user_id=123, signal=OLHO, confidence=0.98`
5. Retorna ao frontend com timestamp

**Resposta para outro usuário (ouvinte):**
```json
{
  "event": "signal_recognized",
  "user": "Deficiente Auditivo",
  "signal": "OLHO",
  "confidence": 0.98,
  "timestamp": "2026-08-11T15:30:45Z",
  "message": "Usuário fez o sinal: OLHO"
}
```

---

### **Exemplo 2: Ouvinte fala "Olá, tudo bem?"**

**Requisição do Frontend:**
```bash
curl -X POST http://localhost:5678/webhook/audio-to-sign \
  -H "Content-Type: application/json" \
  -d '{
    "audio": "base64_encoded_audio...",
    "user_id": "user_456",
    "language": "pt-BR"
  }'
```

**Processamento N8N:**
1. Recebe áudio
2. Envia para `Speech-to-Text:5000/api/transcribe`
3. Recebe: `{text: "Olá, tudo bem?", confidence: 0.95}`
4. Envia para `Text-to-Sign:6000/api/generate-sign`
5. Recebe: `{animation_url: "http://localhost:6000/results/abc123.mp4", duration: 3.2}`
6. Armazena: `conversations.user_id=456, text="Olá, tudo bem?", animation_url=abc123.mp4`
7. Retorna animação

**Resposta para usuário deficiente auditivo:**
```json
{
  "event": "animation_generated",
  "user": "Ouvinte",
  "text": "Olá, tudo bem?",
  "animation_url": "http://localhost:6000/results/abc123.mp4",
  "duration": 3.2,
  "message": "Ouvinte disse em Libras: 'Olá, tudo bem?'"
}
```

---

## ⏱️ Sequência Temporal (Conversação Completa)

```
Tempo  │ Deficiente Auditivo         │ N8N                    │ Ouvinte
───────┼─────────────────────────────┼────────────────────────┼─────────────────
  0ms  │ Faz sinal "OLHO"            │                        │ Aguardando...
       │ Captura vídeo               │                        │
       ▼                             │                        │
       
100ms  │ Envia vídeo para N8N        │                        │
       │ (HTTP POST)                 │                        │
       │                             ▼                        │
       │                     Recebe vídeo                     │
       │                     Chama KONECTA V3                 │
       ▼                             │                        │
       
300ms  │ Aguarda resultado           │ Aguarda processamento  │
       │                             │ MediaPipe              │
       │                             │ Classificação RF/MLP   │
       │                             ▼                        │
       │                     Recebe: OLHO (0.98)              │
       │                     Armazena no BD                   │
       ▼                             │                        │
       
400ms  │ Recebe confirmação          │ Envia para cliente     │
       │ "OLHO reconhecido"          │                        │
       │                             │                        ▼
       │                             │                 Vê mensagem:
       │                             │                 "Deficiente fez: OLHO"
       │                             │                 
       │ Fala algo...                │                        
       │                             │                        │ Fala: "Que bacana!"
       │                             │                        ▼
       
500ms  │                             │                 Envia áudio para N8N
       │                             │                        │
       │                             ▼ Recebe áudio           │
       │                     Chama Speech-to-Text             │
       ▼                             │                        │
       
700ms  │ Aguarda...                  │ Recebe: "Que bacana!"  │
       │                             │ Chama Text-to-Sign     │
       ▼                             │                        │
       
900ms  │                             │ Recebe animação MP4    │
       │                             │ Armazena no BD         │
       ▼                             │                        │
       
1000ms │ Recebe animação             │ Envia para cliente     │
       │ Vê sinal em Libras:         │                        │ Aguardando...
       │ "Que bacana!"               ▼                        │
       │                     Tudo registrado                  │
       │                     no histórico                     │
```

**Latência Total: ~1 segundo** (aceitável para comunicação em tempo real)

---

## ⚡ Performance e Latência

### **Breakdown de Latência**

| Etapa | Min | Típico | Max | Otimização |
|-------|-----|--------|-----|------------|
| Captura vídeo/áudio | 16ms | 33ms | 100ms | Aumentar FPS |
| Envio HTTP | 10ms | 50ms | 200ms | WebSocket, compressão |
| KONECTA V3 processamento | 100ms | 250ms | 500ms | Cache, GPU |
| Speech-to-Text | 200ms | 1000ms | 3000ms | Modelo mais leve |
| Text-to-Sign render | 100ms | 500ms | 2000ms | Cache de animações |
| N8N overhead | 50ms | 150ms | 300ms | WebSockets diretos |
| **TOTAL** | **476ms** | **1983ms** | **6100ms** | |

---

### **Otimizações Recomendadas**

#### **Curto Prazo (Dia 1)**
- ✅ WebSocket para vídeo/áudio (reduz HTTP overhead)
- ✅ Cache de sinais frequentes em KONECTA V3
- ✅ Compressão de vídeo antes de envio (H.264)

#### **Médio Prazo (Semana 1-2)**
- ⏳ GPU para KONECTA V3 (TensorFlow/CUDA)
- ⏳ Modelo quantizado para Speech-to-Text
- ⏳ Pré-render de animações comuns em Text-to-Sign

#### **Longo Prazo (Mês 1-2)**
- 🔮 Modelo de ML próprio (menor latência)
- 🔮 Edge processing (frontend em WebAssembly)
- 🔮 CDN para animações

---

### **Monitoramento**

```json
{
  "metrics_endpoint": "/api/metrics",
  "tracks": [
    {
      "name": "konecta_recognition_time",
      "type": "histogram",
      "unit": "milliseconds",
      "buckets": [50, 100, 250, 500, 1000]
    },
    {
      "name": "n8n_workflow_duration",
      "type": "histogram",
      "unit": "milliseconds"
    },
    {
      "name": "api_error_rate",
      "type": "counter",
      "threshold_alert": 0.05
    },
    {
      "name": "model_confidence_distribution",
      "type": "histogram",
      "buckets": [0.0, 0.5, 0.7, 0.9, 1.0]
    }
  ]
}
```

---

## 🛠️ Checklist de Implementação

### **KONECTA V3 (Vinicius)**
- [ ] Estrutura FastAPI criada
- [ ] Endpoint `/api/recognize` implementado
- [ ] Carregamento de modelos (.joblib)
- [ ] Processamento MediaPipe
- [ ] Resposta JSON estruturada
- [ ] Health check implementado
- [ ] Documentação Swagger
- [ ] Testes unitários
- [ ] Deploy (localhost:8000)

### **N8N (Setup)**
- [ ] Docker/N8N instalado
- [ ] 3 Webhooks configurados
- [ ] 3 Workflows criados
- [ ] Testes end-to-end
- [ ] Documentação de fluxos

### **Colega-X (Speech-to-Text)**
- [ ] API REST pronta
- [ ] Endpoint `/api/transcribe` implementado
- [ ] Resposta JSON estruturada
- [ ] Deploy (localhost:5000)

### **Colega-Y (Text-to-Sign)**
- [ ] API REST pronta
- [ ] Endpoint `/api/generate-sign` implementado
- [ ] Resposta JSON estruturada
- [ ] Deploy (localhost:6000)

### **Banco de Dados**
- [ ] Schema criado
- [ ] Tabela `signals`
- [ ] Tabela `conversations`
- [ ] Índices para performance

---

## 📌 Próximos Passos

1. **Esta semana:**
   - Criar estrutura básica do KONECTA V3
   - Preparar endpoints API
   - Testes com dados reais do SIGNLAB

2. **Próxima semana:**
   - Integração com N8N
   - Testes end-to-end com colegas
   - Otimização de latência

3. **Após testes:**
   - Multiplataforma (web, mobile)
   - Persistência de histórico
   - Análise de padrões de comunicação

---

**Documentação criada:** 2026-08-11  
**Versão:** 1.0  
**Status:** Pronto para implementação ✅
