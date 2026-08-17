# 🔎 Architecture Review — KONECTA Intelligence Hub

**Revisado em:** 2026-08-11
**Escopo:** KONECTA_V3 (não toquei em `C:\KONECTA\SIGNLAB`)
**Fontes revisadas:**
- `C:\KONECTA\ARQUITETURA_INTEGRACAO.md` (N8N + 3 motores + banco)
- `C:\KONECTA\APP_CENTRAL_ARQUITETURA.md` (Hub multi-IA paralelo)
- Código real em KONECTA_V3: `app_central/` (`main.py`, `pipeline/recognizer_pipeline.py`, `motors/motor_konecta_v3.py`, `motors/motor_claude_logic.py`), `app_backend/`, `requirements.txt`

---

## 🔴 Resumo executivo

A **visão conceitual está certa** (rápido primeiro → sobe de acuracidade só quando a incerteza exige → cache/N8N em segundo plano). Os problemas reais estão em três camadas:

1. **O código hoje não corresponde à arquitetura documentada** — Gemini, Grok, cache local e cliente N8N são `None` (stubs) no pipeline, e `config/config.yaml` nem existe. Os docs descrevem um sistema que ainda não está montado.
2. **Há um bug que impede o sistema de rodar** — `main.py` chama `asyncio.create_task` sem um event loop ativo. O app abre, mas o reconhecimento nunca executa.
3. **O alvo de <1s contradiz as próprias tabelas e o design de escalada** — o caminho de baixa confiança *aumenta* a latência (até ~1,2-1,5s+ adicionais) justamente no pior caso, estourando o SLA.

Nenhuma das três decisões centrais precisa ser descartada — precisam de correção e de **realismo de SLA** por caminho.

---

## ✅ Validação das decisões centrais

| Decisão | Veredito | Nota |
|---|---|---|
| **Pipeline paralelo** | 🟡 Parcialmente certo | Intenção boa, execução errada: o caminho comum (HIGH) fica **serial** ao aguardar Gemini sem usar o resultado. Ver §3.4. |
| **Decisão por confiança** | 🟡 Certa na intenção, frágil na fundação | Roteamento por limiar de `predict_proba` de um RF/MLP **não é calibrado**; e escalar *adicionando* LLM no pior caso piora o SLA em vez de melhorar a acurácia. Ver §3.5. |
| **Cache local** | 🟠 Bem construído, premissa errada p/ vídeo | Cache de landmark por `blake2b` de frame inteiro: correto e eficiente, mas frames de webcam **nunca são byte-idênticos** → hit rate ~0% e o próprio hash custa tempo no caminho quente. Ver §3.6. |
|**N8N assíncrono** | ✅ Correto no Hub, ⛔ errado no `ARQUITETURA_INTEGRACAO` | Os dois docs se contradizem: um põe N8N **no caminho síncrono** (138-300ms de overhead por chamada), o outro corretamente o trata como side-channel. Unificar. Ver §3.7. |

---

## 🐞 3. Problemas encontrados (por criticidade)

### 3.1 — 🔴 CRÍTICO: `asyncio.create_task` sem event loop ativo (`app_central/main.py`)

```python
# main.py:257 - slot chamado pela worker de vídeo (QThread)
def _process_frame(self, frame: np.ndarray):
    if self.pipeline and self.is_running:
        asyncio.create_task(self._run_pipeline(frame))   # ← sem loop rodando
```

- `VideoCaptureWorker` dispara `frame_ready` numa **QThread**; `app.exec_()` roda o **loop Qt**, não o asyncio.
- `asyncio.create_task` exige um event loop corrente na thread; aqui não há → `RuntimeError: no running event loop` (ou a task nunca é agendada).
- **Resultado:** o app abre, a câmera captura, e nenhum frame chega ao pipeline. O "reconhecimento" não roda.

**Correção (mínima):** um único loop asyncio em thread dedicada, com ponte thread-safe para a UI:

```python
# Em vez de criar task no slot Qt:
class PipelineBridge(QObject):
    result_ready = pyqtSignal(PipelineResult)

    def __init__(self, pipeline):
        super().__init__()
        self.pipeline = pipeline
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._run_loop, daemon=True).start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def process(self, frame):                       # chamado do slot Qt
        fut = asyncio.run_coroutine_threadsafe(
            self.pipeline.process_frame(frame), self.loop)
        # NÃO bloqueia a UI: encadeie a dois-stage com result_ready
```

(Alternativa válida: `qasync`/`asyncqt`, que funde o event loop Qt e o asyncio — menos código de bridge.)

---

### 3.2 — 🔴 CRÍTICO: dependências faltando — `pip install -r requirements.txt` quebra o app

`requirements.txt` (atual) **não inclui**:

- `PyQt5` — importado em `app_central/main.py:26`
- `anthropic` — importado em `app_central/motors/motor_claude_logic.py:7`

```bash
# Instalação limpa hoje
ModuleNotFoundError: No module named 'PyQt5'   # na primeira subida
```

**Correção:** adicionar às dependências e (idealmente) separar runtime de dev (`requirements-runtime.txt` / `requirements-dev.txt`).

---

### 3.3 — 🔴 CRÍTICO: documento ↔ código divergem — motores e config não existem

| Documentado (`APP_CENTRAL_ARQUITETURA.md`) | Realidade no código |
|---|---|
| `config/config.yaml` carregado | Diretório `app_central/config/` **não existe** → `main.py` cai silenciosamente em defaults (`_load_config` `except: return defaults`) |
| `motor_gemini_vision.py` (paralelo a V3) | `pipeline.gemini = None` (stub) |
| `motor_grok_context.py` (confiança < 0.7) | `pipeline.grok = None` (stub) → caminho LOW vira *fallback silencioso* |
| `cache_manager.py` / `n8n_client.py` | `pipeline.cache_manager = None`, `pipeline.n8n_client = None` |

Efeitos práticos:
- **Nenhum caminho é "ensemble" de verdade**: no HIGH, `validated_by="ensemble"` é rótulo falso — é só KONECTA V3.
- **O caminho LOW não enriquece nada**: retorna o sinal original com confiança inalterada (`final_signal = konecta_result.signal`), então as confusões continuam e **sem registro aparente**.

---

### 3.4 — 🔴 ALTO: o falso "paralelismo" do caminho HIGH

`recognizer_pipeline.py` FASE 1:

```python
if gemini_task:
    konecta_result, gemini_result = await asyncio.wait_for(
        asyncio.gather(konecta_task, gemini_task), timeout=1.5)
...
if confidence_level == ConfidenceLevel.HIGH:
    # NÃO usa gemini_result na decisão
```

- Gemini é o **colega lento** (200-1500ms na própria tabela). Como o `gather` espera **ambos**, todo frame HIGH paga a latência do Gemini mesmo quando ele é irrelevante.
- Pior: o timeout de 1.5s **coloca o teto do caso comum exatamente no SLA** — um frame HIGH só por sorte fica abaixo de 1s quando Gemini responde devagar.

**Correção:** no caminho quente, aguarde **só o KONECTA V3**; dispare Gemini *assíncrono* como validador de background e consulte-o apenas no nível MEDIUM:

```python
# Construir resultado assim que o motor rápido responde
konecta_result = await asyncio.wait_for(self.konecta.process(frame), timeout=0.5)

# Gemini vira side-task: ninguém espera por ele no caminho HIGH
gemini_task = asyncio.create_task(self.gemini.validate(frame_b64)) if self.gemini else None

if confidence > 0.85 and (gemini_task is None or gemini_result_is_ok):
    return build_result(konecta_result)          # ~200-300ms, sem esperar Gemini
if 0.7 <= confidence <= 0.85:
    gemini = await gemini_task                    # só aqui a espera é justificada
    ...
```

---

### 3.5 — 🔴 ALTO: roteamento por confiança tem fundação frágil + escalada na direção errada

Dois subproblemas:

**(a) `predict_proba` de RF/MLP não é calibrado.** Um limiar de 0.7/0.85 num classificador não calibrado não significa "70%/85% de chance de estar certo". As fronteiras HIGH/MEDIUM/LOW são, na prática, arbitrárias — a "validação cruzada" decide sobre um número que não quer dizer o que parece.

```python
# Calibrar usando o próprio conjunto de validação (scikit-learn):
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression

calibrated = CalibratedClassifierCV(classifier, method="isotonic", cv=5)
calibrated.fit(X_val, y_val)
# calibrated.predict_proba(...) agora DE FATO significa probabilidade
```
> Requer que o SIGNLAB exponha `X_val, y_val` — alinhar com quem treina os artefatos.

**(b) A escalada LOW adiciona o colega mais lento justamente no pior caso.**

```
HIGH : KONECTA (250ms)                     → ~300ms  ✅
MED  : + Claude (200-500ms, hard timeout)  → ~700ms  🟡
LOW  : + Grok (300-1000ms, timeout 1.2s)   → ~1600ms ❌ estoura SLA
```

Baixa confiança num reconhecedor local costuma significar **captura ruim** (mãos fora do quadro, iluminação, oclusão, `NO_HANDS`), não "contexto ajudaria". Um LLM "enriquecendo contexto" **não conserta frame ruim** — gastar 1.2s para votar no sinal errado não melhora o resultado e degrada a experiência.

**Correção (reordena a escalada):**

```
LOW (0.7):    NÃO chama LLM. Verifica qualidade de captura (hands/peso/iluminação)
              → reaproveita métricas já provisórias do próprio frame:
              - se frame inválido/NO_HANDS → "repita o sinal", latência ~50ms
              - se frame OK mas modelo dividido → só então subir para validação contextual (Claude)
```

Assim, o caso mais comum de "baixa confiança" vira resposta rápida e honesta (pedido de retry), e a escalada contextual fica reservada a frames de qualidade confiável.

---

### 3.6 — 🟠 MÉDIO: cache de landmarks por hash do frame inteiro é ineficaz para vídeo

`motor_konecta_v3.py` (linhas 151-175) implementa um cache LRU de landmarks chaveado por `blake2b(frame_bytes)` — bem escrito, com cópia defensiva e verificação de contiguidade. O problema é a **premissa**:

- Frames consecutivos de webcam mudam a cada milissegundo (ruído, compressão, movimento) → **byte-idênticos é raro → hit rate ≈ 0%**.
- O `blake2b` de um frame de 640×480×3 (~900KB) roda no **caminho quente**, *antes* do MediaPipe, e custa mais do que o lookup que economizaria.

**Correções possíveis (escolher uma):**
- Drop o cache e substitua por **supressão temporal** real: processar a cada N frames (ex.: 3) e reusar o último resultado, ou
- chave estável por descritor pequeno (hash de thumbnail 32×24 quantizado), que *de fato* colide entre frames próximos, ou
- usar o tracking interno do MediaPipe (que já existe e evita re-detecção completa) como mecanismo de cache — o comentário do próprio código já aponta esse caminho.

---

### 3.7 — 🟠 MÉDIO: N8N nos dois papéis contraditórios + sem backpressure

- `ARQUITETURA_INTEGRACAO.md`: N8N **orquestra o fluxo síncrono** (recebe vídeo, chama motor, devolve) — adiciona 138-300ms de overhead por requisição no caminho de latência que é o requisito do produto.
- `APP_CENTRAL_ARQUITETURA.md`: N8N é **side-channel** assíncrono ("não bloqueia a UI") — correto.

**Decisão recomendada:** a propagação `asyncio.create_task(self._update_cache_and_notify(...))` (recognizer_pipeline.py:239) cria **task de background sem fila nem limite** — sob carga alta, milhares de tasks penduradas esperando N8N ficam na memória. Colocar um **bounded queue** (asyncio.Queue(maxsize=100)) + drop policy, e persistir localmente o que não der para mandar (compensação).

---

### 3.8 — 🟠 MÉDIO: estrutura de pastas documentada ≠ pastas reais

`APP_CENTRAL_ARQUITETURA.md` prevê `ui/`, `config/`, `integrations/`, `database.py`, `cache_manager` … O disco tem `main.py` + `motors/` + `pipeline/` + `utils/`. Não é problema em si (o compacto pode até ser melhor), mas a **documentação engana a equipe** — alguém vai procurar `config/config.yaml` e não achar. Alinhar docs ao que existe ou criar o que os docs prometem.

---

### 3.9 — 🟠 MÉDIO: "Gemini Vision" importa `anthropic` e usa Claude (copy-paste)

`APP_CENTRAL_ARQUITETURA.md` (código do `MotorGeminiVision`) importa `anthropic` e chama `self.client.messages.create(model="claude-3-5-sonnet-20241022")` — o **nome é Gemini, o SDK é da Anthropic**. Risco real: o colega que implementar segue o documento e cria um "Gemini Vision" que na verdade é Claude, ou mistura credenciais incompatíveis. Nomear corretamente (ou usar o SDK do Gemini de verdade).

---

### 3.10 — 🟡 BAIXO: segurança e qualidade

- **Sem autenticação** nos endpoints internos (`localhost:8000/5000/6000` assumidos). Se subir para um host compartilhado (Docker/K8s já existem no repo!), vira porta aberta. Adicionar token simples (header `Authorization`) entre serviços.
- **Chaves de IA** documentadas como `api_keys.yaml` (gitignored) — ok, mas lembrar de **não commitar** e usar variáveis de ambiente (o `config.yaml` já referencia `$CLAUDE_API_KEY`, bom).
- **Timeouts hardcoded** no código (`1.0s`, `1.5s`, `0.8s`, `1.2s`) — devem vir do `config.yaml`, que hoje não existe.
- **Contrato entre colegas sem versionamento**: portas e payloads fixados em Markdown. Ter um arquivo `openapi.yaml` ou `contracts/` **no mono-repo KONECTA_V3** como fonte única de verdade (os 3 motores consomem o mesmo arquivo).
- Modelo de rede curto: faltam commits `unittest` com fixtures de landmark reais (o teste atual roda com **frame preto** → sempre `NO_HANDS`), logo não exercita inferência.

---

## 🎯 4. Recomendações priorizadas

### P0 — desbloqueia rodar (hoje)
1. **Consertar o event loop** em `main.py` (2-stage `run_coroutine_threadsafe` + loop dedicado, ou `asyncqt`). Sem isso, nada roda.
2. **Adicionar `PyQt5` e `anthropic`** ao `requirements.txt`.
3. **Criar `app_central/config/config.yaml`** (ou remover a leitura) e mover timeouts para ele — evita defaults ocultos.

### P1 — cumpre o SLA < 1s de verdade
4. **Não esperar Gemini no caminho HIGH**; tratar Gemini como validador de background e consultá-lo só no MEDIUM (§3.4).
5. **Reordenar a escalada LOW**: checar qualidade de captura primeiro (retry barato) e só então LLM (§3.5b).
6. **Calibrar o `predict_proba`** para que os limiares 0.7/0.85 tenham significado (§3.5a).
7. **Substituir/repensar o cache de landmarks** — hash de frame inteiro não colide em vídeo (§3.6).
8. **Colocar fila limitada + drop policy** na notificação N8N/cache (§3.7).

### P2 — robustez e colaboração
9. **Unificar os dois documentos de arquitetura** (N8N async como fonte única; corrigir "Gemini/anthropic").
10. **Criar contrato de API versionado** no mono-repo para os 3 colegas (§3.10).
11. **Auth entre serviços** + variáveis de ambiente p/ chaves (§3.10).
12. **Testes com fixtures reais** e um **gate de CI de latência** (falhar se p95 > 800ms no caminho HIGH).

---

## 🧭 5. Diagrama alternativo

Reduz o caminho quente a **uma espera só**, escalada condicionada a qualidade de captura e fundo garantido:

```
                        CAMERA / MIC
                              │  (worker Qt → ponte asyncio)
                              ▼
┌───────────────────────────────────────────────┐
│  PIPELINE (loop asyncio dedicado)             │
│                                               │
│  ┌─────────────┐    1. motor rápido           │
│  │ KONECTA V3  │────────┐  (apenas ele é      │
│  │ (RF/MLP)    │←───────┘   esperado no hot)  │
│  └─────────────┘                             │
│        │ resultado {sinal, conf_calibrada}    │
│        ▼                                      │
│  ┌────────────────────────────────────────┐   │
│  │ DECISOR (por confiança calibrada)       │   │
│  │  conf > 0.85   → OK imediato            │   │
│  │  0.7–0.85     → busca validação (fundo) │   │
│  │  < 0.7         → checa CAPTURA          │   │
│  └───────┬───────────────────┬────────────┘   │
│          │ frame bom          │ frame ruim/    │
│          ▼                    │ NO_HANDS       │
│  ┌───────────────┐           ▼                │
│  │ VALIDAÇÃO     │     "Repita o sinal"       │
│  │ Claude/Gemini │      (~50ms, honesto)      │
│  │ (só MEDIUM)   │                            │
│  └───────┬───────┘                            │
│          └───────▶ resultado final            │
│                        │                      │
│                        ▼                      │
│  ┌────────────────  FUNDO (não bloqueia) ──┐  │
│  │ BoundedQueue → Cache local → N8N webhook│  │
│  └─────────────────────────────────────────┘  │
└──────────────────────┬────────────────────────┘
                       ▼
                 UI (Qt) exibe resultado 📟
```

Características da alternativa vs. o atual:
- **Uma espera serial só no hot path** (o motor rápido); fundo nunca atrasa a resposta.
- **Escalada é barata antes de ser cara**: qualidade de captura (determinística) precede LLM (lenta).
- **Cache/N8N em fila limitada** → sem acúmulo de tasks.
- **Fundo garantido por caminho** com SLA p95 (hot HIGH ≤ 300ms, MED ≤ 800ms, LOW-decide ≤ 200ms).

---

## ⏱️ 6. SLAs realistas por caminho

| Caminho | Design atual (est.) | Recomendado (est.) |
|---|---|---|
| HIGH (conf > 0.85) | 300–1600ms (espera Gemini) | **≤ 300ms** |
| MEDIUM (0.7–0.85) | ~700ms | **≤ 800ms** |
| LOW, frame ruim | ~1600ms (Grok) | **≤ 200ms** ("repita") |
| LOW, frame bom | ~1600ms | **≤ 1000ms** |
| Full bidirecional (STT→TTS→sinal) | 1983–6100ms (tabela doc) | **SLA separado** (não forçar 1s num pipeline desenhado p/ <3s) |

> O alvo **<1s é atingível** no caminho de reconhecimento (o caso de uso principal). Impor 1s à cadeia completa de conversão (áudio→texto→sinal) é inviável e desnecessário — defina **SLA por produto**, não um único número global.

---

## 📦 7. Contrato mínimo entre colegas (sugestão)

Um único arquivo no mono-repo, consumido por todos:

```yaml
# contracts/openapi.yaml (extrato)
openapi: 3.0.0
paths:
  /recognize:            # KONECTA V3 (Vinicius)
    post:
      requestBody: { video: base64, model_version: v1 }
      responses: { 200: { signal, confidence, latency_ms } }
  /transcribe:           # Colega-X (áudio→texto)
    post:
      requestBody: { audio: base64, language: pt-BR }
      responses: { 200: { text, confidence, words[] } }
  /generate-sign:        # Colega-Y (texto→sinal)
    post:
      requestBody: { text, animation_format }
      responses: { 200: { animation_url, duration_seconds } }
```

Isso substitui os payloads fixos nos Markdown, versiona mudanças (quebras viram PRs) e elimina o risco dos 3 motores discordarem sobre os mesmos campos.

---

## ▶️ Conclusão

A direção está certa e o `motor_konecta_v3.py` já é um código de boa qualidade (lazy-load, profiling por etapa, encerramento explícito de recursos). Mas hoje o sistema **não roda** de ponta a ponta (event loop + deps), e os docs **vendem** uma arquitetura (Gemini/Grok/cache/N8N) que o código ainda só esboça. Prioridades: corrigir o que impede rodar (P0), depois dominar a latência no caminho quente (P1), e só então democratizar robustez/segurança para o trabalho em time (P2).