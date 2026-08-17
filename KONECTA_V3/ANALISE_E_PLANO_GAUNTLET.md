# KONECTA V3 — Análise e Plano de Evolução

> Resposta à §22 do `KONECTA_V3_GAUNTLET_LOOP.md`: diagnóstico antes de implementar.
> Tudo aqui foi verificado no código, não inferido. Cada afirmação traz como foi comprovada.
>
> Escopo: **somente `KONECTA_V3/`**. SIGNLAB e TEXTO_PARA_LIBRAS não são tocados.

---

## Resumo

O `app_central` **roda** e processa frames — verificado com um smoke test de processo real
(10/10 frames). O que ele não faz é aguentar carga: com um pipeline que bloqueia a thread
(que é o caso do motor real), **47% dos frames nunca chegam a ser processados** e o atraso
cresce indefinidamente. O `vision_lab/` é código bom e aproveitável. E a premissa central da
spec — KONECTA como cliente fino que chama motores via API — **não existe hoje em nenhuma
linha do projeto**: não há um único cliente HTTP no `app_central`.

> **Correção de uma versão anterior deste documento.** Eu havia registrado como achado
> crítico que o app abortava no primeiro frame por chamar `asyncio.create_task()` dentro de
> um slot Qt. **Isso está errado para o código atual.** Eu havia lido uma versão anterior do
> `main.py`; o código de hoje mantém um loop asyncio em thread dedicada e usa
> `run_coroutine_threadsafe`, que é o padrão correto. O smoke test confirma. O problema real
> é o de contrapressão descrito em 5.1.

---

## 1. Arquitetura atual

Não há uma arquitetura; há **três projetos convivendo** no mesmo repositório, com sete
pontos de entrada:

| Entrada | Linhas | O que é |
|---|---|---|
| `app_central/main.py` | 370 | GUI PyQt5 + pipeline multi-motor. É o "Intelligence Hub" |
| `app_gui.py` | 258 | Outra GUI desktop "KONECTA V3" |
| `app_gui_v2.py` | 454 | Terceira GUI desktop "KONECTA V3" |
| `vision_lab/app.py` | 259 | API FastAPI de visão computacional |
| `vision_lab/cli.py` | 263 | CLI do vision_lab |
| `app_backend/main.py` | 157 | API FastAPI de CRUD/telemetria |
| `run_realtime_webcam.py` | 54 | Script de webcam |

Volume: `app_central` 3.661 linhas, `vision_lab` 3.405, `app_backend` 1.880, `tests` 3.946.

Três GUIs disputam o mesmo papel e duas APIs FastAPI diferentes coexistem sem contrato entre si.
O `.claude/launch.json` aponta só para o `vision_lab`, sugerindo que era o foco mais recente.

## 2. Tecnologias

Python 3.11, PyQt5 (GUI), OpenCV + MediaPipe (visão), scikit-learn/joblib e Keras/TensorFlow
(classificadores), FastAPI + Uvicorn (duas APIs), SQLAlchemy + Alembic + SQLite (`app_backend`),
pytest (287 testes), Docker + GitHub Actions (CI/CD), SDK `anthropic`.

## 3. Módulos existentes

```
app_central/    GUI, pipeline de decisão por confiança, 4 "motores", métricas, captura
vision_lab/     landmarks, processing, features, training, temporal, realtime,
                cross_signer, experiments, dataset, visualization, app (API), cli
app_backend/    models, schemas, routes, services, middleware, migrations
tests/          23 arquivos, 287 testes
```

## 4. Funcionalidades que realmente funcionam

- **`app_central/motors/motor_konecta_v3.py`** — **é aqui que está a visão computacional
  real.** Usa `mp.solutions.hands`, converte BGR→RGB, extrai 63 features por mão e tem cache
  de landmarks. Falta só o modelo treinado (ver 5.5).
- **`app_backend/`** — CRUD e telemetria funcionando, com migrations e middleware.
- **Suíte de testes** — roda em 12,8s, sem depender de APIs reais. Boa infraestrutura.

> **Correção de uma versão anterior deste documento.** Eu havia escrito que o `vision_lab/`
> era "o ativo técnico real do projeto". **Está errado** — ver 5.10. Eu tinha lido os nomes
> dos módulos e a estrutura, não o corpo do método que importa.

## 5. Problemas encontrados

### 5.1 CRÍTICO — sem contrapressão: metade dos frames nunca é processada

`_process_frame` agenda uma corrotina por frame via `run_coroutine_threadsafe`, sem limite,
sem descarte e sem controle de taxa. `VideoCaptureWorker._capture_loop` emite a cada
iteração, o mais rápido que a câmera entregar.

**Como comprovei** (`tests/probe_backpressure.py`, câmera falsa a 30fps, pipeline de 100ms):

| Pipeline | Frames | Iniciados | Concluídos | Pico em voo |
|---|---|---|---|---|
| não-bloqueante (`asyncio.sleep`) | 150 | 150 | 150 | 4 |
| **bloqueante (imita MediaPipe/sklearn)** | **150** | **81** | **80** | **1** |

Com trabalho que segura a thread — que é o caso do motor real — **69 frames ficaram
enfileirados** e nunca rodaram. A fila cresce ~2 frames/s indefinidamente: depois de um
minuto o sinal exibido está ~12s atrasado em relação ao que a pessoa sinalizou.

Numa aplicação de comunicação em tempo real, atraso acumulado é falha funcional, não
degradação: a resposta deixa de corresponder à pergunta.

### 5.2 ALTO — a suíte não cobre comportamento sob carga

287 testes passam em 12,8s e nenhum exercita o app como processo sob carga contínua. O
problema 5.1 não é detectável por teste unitário de `_process_frame` — só aparece com câmera
produzindo mais rápido que o pipeline consome, por tempo suficiente.

Adicionei dois roteiros que faltavam: `tests/smoke_app_central.py` (o app sobrevive e
processa frames de verdade) e `tests/probe_backpressure.py` (mede perda sob carga).

### 5.3 CRÍTICO — a premissa da spec não existe no código

A spec quer o KONECTA como intermediário que chama motores via API. Verificado:
**não há um único `import requests`/`httpx`/`aiohttp` em todo o `app_central/`.** Os motores
são objetos in-process que carregam modelos e chamam SDKs diretamente. Não há
`AudioToTextProvider`, `SignLanguageToTextProvider` nem `TextToSignProvider`.

### 5.4 CRÍTICO — não existe API de reconhecimento

O `app_backend` expõe apenas: `GET /health`, `POST /metrics`, `GET /models/available`,
`GET /signals`, `POST /webhook/signal-recognized`. **Não há endpoint que receba um frame e
devolva o sinal reconhecido.** O "motor de reconhecimento via API" do seu pedido não existe
como API — o reconhecimento está embutido no cliente.

### 5.5 ALTO — o motor primário não tem modelo

`MotorKonectaV3` carrega de `models/v1`. **A pasta `models/` está vazia.** O motor primário do
pipeline não tem o que carregar; todo o resto do pipeline foi construído sobre ele.

### 5.6 ALTO — o motor "Gemini Vision" chama Claude

`app_central/motors/motor_gemini_vision.py:52` faz `anthropic.Anthropic(api_key=api_key)` com
default `claude-3-5-sonnet-20241022`. Não há import de SDK do Google no arquivo. O motor está
mal rotulado — e tem 11 testes passando sobre esse comportamento, o que consolida o engano.

### 5.7 ALTO — nada da infraestrutura que a spec exige existe

Verificado por busca em todo o código: `SessionManager`, `ConversationManager`,
`PermissionManager`, `ConfigurationManager`, `VideoCallAdapter`, `TeamsAdapter`, `ZoomAdapter`,
`MeetAdapter`, `RetryManager`, `CircuitBreaker`, `keyring` — **todos ausentes**.

Credenciais vêm de `os.getenv` direto no ponto de uso, sem armazenamento seguro (§8 da spec).

### 5.10 CRÍTICO — o `vision_lab` não extrai landmarks: devolve números aleatórios

`vision_lab/landmarks.py:56`, dentro de `LandmarkExtractor.extract`:

```python
# For now, generate dummy landmarks for testing
frame.landmarks = np.random.randn(228).astype(np.float32)
frame.confidence = np.random.rand()
```

MediaPipe nunca é chamado. `_init_detectors` apenas faz `self.hands = True`. Todo o resto do
`vision_lab` — features, treino, buffer temporal, cross-signer, experimentos — opera sobre
ruído gaussiano. As métricas de acurácia produzidas por esse caminho não significam nada.

São 3.405 linhas construídas sobre um extrator que é `TODO`. É o achado mais sério do
projeto, e o mais fácil de não perceber: a estrutura parece completa e os testes passam,
porque testar ruído aleatório é perfeitamente possível.

**Consequência para o plano:** o provider local usa `MotorKonectaV3` (MediaPipe real), não o
`vision_lab`. O `vision_lab` precisa de decisão à parte: implementar o extrator de verdade ou
aposentar o módulo.

### 5.8 MÉDIO — captura de vídeo sem controle de taxa

`VideoCaptureWorker._capture_loop` emite `frame_ready` a cada iteração, sem throttle, sem
FPS alvo efetivo e sem descarte. Com o pipeline atrás, isso gera pressão ilimitada.
A spec (§4) pede explicitamente frame sampling, FPS configurável e evitar envio desnecessário.

### 5.9 MÉDIO — três GUIs e 23 arquivos de documentação de status

`FINAL_STATUS_6_FASES.md`, `FINAL_STATUS_7_FASES.md`, `FINAL_STATUS_8_FASES_COMPLETO.md`,
`PRODUCTION_READY.md`, `STATUS_FINAL.md`… documentos que declaram conclusão de um sistema que
não processa um frame. Custo de manutenção e confusão sobre qual é o app real.

## 6. Riscos

| Risco | Impacto |
|---|---|
| Testes dão confiança falsa | Já causou "pronto para produção" em app que aborta |
| Reescrever tudo | A spec (§21) proíbe; `vision_lab` seria perdido sem motivo |
| Acoplar a uma plataforma de vídeo | Teams/Zoom/Meet têm mecanismos distintos e restritivos |
| Câmera/microfone sempre ligados | Privacidade (§9) e consumo de CPU |
| Latência acumulada | Cada salto (captura→API→IA→render) soma; hoje não é medida ponta a ponta |

## 7. Dependências

Externas: MediaPipe, OpenCV, scikit-learn, TensorFlow/Keras, PyQt5, FastAPI, SQLAlchemy, anthropic.

Internas do ecossistema (fora deste repo, **não serão modificadas**):
- **SIGNLAB** — produz os modelos que o motor consome.
- **TEXTO_PARA_LIBRAS** — já implementa a perna Texto→Libras: expõe `POST /publicar` e
  WebSocket em `127.0.0.1:8300`, com avatar VLibras funcionando. **É a "Texto para Libras API"
  do diagrama, e já está pronta.** O KONECTA V3 deve consumi-la, não reimplementá-la.

## 8. Pontos reutilizáveis

- **`MotorKonectaV3`** — a extração MediaPipe real. É o núcleo do reconhecimento e o que o
  provider local deve usar.
- **`vision_lab/`** — só a *estrutura* (dataset, treino, experimentos) se presta a reúso, e
  apenas depois de trocar o extrator de ruído por MediaPipe de verdade (5.10).
- **`app_backend/`** — base sólida para servir a API de reconhecimento (já tem middleware,
  auth, rate limit, migrations).
- **`tests/`** — a infraestrutura é boa; o que falta é cobrir os caminhos certos.
- **`app_central/utils/metrics.py`** — coleta de latência, útil para a §13.
- **`RecognizerPipeline`** — a árvore de decisão por confiança é uma ideia válida; o que muda
  é de onde vêm os resultados (API, não in-process).

## 9. Pontos a refatorar

- `app_central/main.py` — base de concorrência trocada (ver §11).
- `VideoCaptureWorker` — throttle, FPS efetivo, descarte de frames.
- `motor_*` — viram *providers* atrás de interface, com um adaptador HTTP.
- `app_gui.py` / `app_gui_v2.py` — decidir qual morre. Manter três GUIs não se sustenta.
- Documentos de status — consolidar em um.

## 10. Arquitetura proposta

### 10.1 Conflito com a spec que precisa de decisão sua

A spec (§26) diz: *"o KONECTA não deve ser responsável por implementar diretamente os modelos
de IA"*. Mas o KONECTA V3 **contém** o motor de Libras (`vision_lab`). Há duas saídas:

- **(A) Separar** — `vision_lab` vira um serviço próprio (`Libras → Texto API`), e o
  `app_central` passa a ser cliente fino. Fica fiel à spec, permite rodar o motor numa máquina
  mais forte, e é o que o diagrama sugere. Custo: mais um processo para instalar/rodar.
- **(B) Embutir com interface** — mantém `vision_lab` in-process, mas atrás da mesma interface
  `SignLanguageToTextProvider`. Menor latência (sem rede), instalação mais simples, e trocar
  para API depois é só outra implementação do provider.

**Recomendo (B) primeiro, com a interface desenhada para (A).** Motivo baseado em evidência:
nesta máquina não há GPU NVIDIA, e a latência que medimos no TEXTO_PARA_LIBRAS já soma 4–6s
ponta a ponta; acrescentar um salto de rede local a cada frame piora sem necessidade agora.
A interface garante que migrar para (A) não custe reescrita.

### 10.2 Estrutura

```
app_central/
├── core/         SessionManager, ConfigManager, PermissionManager
├── providers/    interfaces + implementações (local e HTTP)
│   ├── base.py           AudioToText | SignToText | TextToSign
│   ├── local_sign.py     usa vision_lab
│   ├── http_sign.py      usa a API quando existir
│   └── http_text_sign.py usa TEXTO_PARA_LIBRAS (8300)
├── capture/      camera (com throttle) e microfone
├── videocall/    VideoCallAdapter + adaptadores por plataforma
├── ui/           GUI única
└── infra/        retry, circuit breaker, credenciais (keyring), logging
```

### 10.3 A base de concorrência: manter, com contrapressão

O desenho atual (loop asyncio em thread dedicada + `run_coroutine_threadsafe`) está correto e
**não deve ser trocado** — trocar por `qasync` seria mudança sem ganho, e a §21 da spec pede
evitar mudanças desnecessárias.

O que falta não é o loop, é a política de fila. Numa legenda ao vivo o frame velho não tem
valor: processar o mais recente e descartar o resto é melhor do que processar todos com
atraso crescente. Regra a adotar: **no máximo um frame em processamento; o que chegar
enquanto isso substitui o anterior na espera.**

Para o motor pesado, a lição do TEXTO_PARA_LIBRAS se aplica: o que segura CPU por centenas de
ms vai para fora da thread do loop (executor ou processo), senão trava tudo o mais.

## 11. Plano de implementação

Ordem deliberada: **nada de features novas antes do app rodar**.

| Ciclo | Entrega | Critério de pronto |
|---|---|---|
| **0** | Contrapressão: FPS alvo, descarte do frame velho, no máximo 1 em voo | `probe_backpressure` sem acúmulo; frame processado é sempre o mais recente |
| **1** | Latência ponta a ponta medida por etapa e exposta na UI (§13) | Captura/IA/render visíveis, com orçamento definido |
| **2** | Interfaces dos providers + `local_sign` sobre `vision_lab` | Motor trocável por config, sem tocar no core |
| **3** | `ConfigManager` + credenciais no Windows Credential Manager | Nenhum segredo em código ou log |
| **4** | `SessionManager` + estados de câmera/microfone/conexão na UI (§11) | Usuário vê o que está ativo, desliga na hora |
| **5** | `http_text_sign` consumindo TEXTO_PARA_LIBRAS | Ouvinte fala → surdo vê Libras |
| **6** | `infra/` retry, backoff, circuit breaker, mensagens amigáveis | API fora do ar não derruba o app |
| **7** | `VideoCallAdapter` + investigação do que cada plataforma permite | Limitações documentadas com evidência |
| **8** | Consolidar GUIs e documentação | Um app, um README |

Ciclo 7 exige pesquisa antes de código: Teams, Zoom e Meet têm restrições reais para injeção
de texto. A spec (§5) manda documentar a limitação em vez de improvisar engenharia reversa.

## 12. Estratégia de testes

O que falhou não foi a quantidade, foi o alvo. Regras a adotar:

1. **Todo teste de código que roda sob Qt deve rodar sob um `QApplication` real**, não dentro
   de um `async def`. O teste 5.2 precisa ser reescrito para falhar sem a correção.
2. **Teste de fumaça de processo**: subir o app com câmera falsa e verificar que sobrevive N
   segundos. Um teste que rodasse isso teria pego o bug crítico.
3. **Providers com mock de API** (a spec §15 já pede) — incluindo resposta lenta, inválida e
   timeout.
4. **Latência**: medir por etapa e falhar se passar de um orçamento definido.
5. Manter a suíte sem depender de API real.

## 13. Estratégia do Gauntlet Loop

Por ciclo: **BUILD → TEST → CRITIC → FIX → TEST → CRITIC**.

O Critic (§17) deve começar por onde este diagnóstico já mostrou fragilidade:

- O teste que cobre esta mudança **falha se a correção for revertida**? (foi o furo do 5.2)
- O que acontece com câmera desconectada no meio, API lenta, internet caindo?
- Algum segredo apareceu em log?
- A CPU se mantém estável em 10 minutos de sessão?

Regra que proponho adotar, vinda deste diagnóstico: **nenhum módulo é declarado pronto sem um
teste que falhe ao reverter a correção.** Foi exatamente isso que faltou nos 287 testes.

---

---

# O que foi entregue

Suíte: **287 → 339 testes**, todos passando. Nada foi tocado fora de `KONECTA_V3/`.

| Ciclo | Entrega | Comprovação |
|---|---|---|
| **0** | Contrapressão em `_process_frame` | 150 frames a 30fps com pipeline bloqueante: antes 69 presos na fila, agora **0**. O guarda reprova se a correção for revertida |
| **1** | Latência ponta a ponta por etapa | Medido: total 142ms = fila 33ms + IA 109ms. Visível na UI com cor por faixa |
| **2** | `providers/` — contratos dos 3 motores + `SinaisLocais` | 10 testes. Motor trocável sem tocar no núcleo |
| **3** | `core/config.py` — config central + `keyring` | Ambiente > YAML > padrão. Teste garante que segredo não entra em log |
| **4** | `core/sessao.py` — `GerenciadorSessao` | Estados da §11, desligamento imediato, observador quebrado não derruba |
| **5** | `providers/http_texto_sinais.py` | **Testado contra o TEXTO_PARA_LIBRAS real**: texto chegou ao avatar |
| **6** | `infra/resiliencia.py` — retry, backoff, circuit breaker | Circuito aberto não toca a rede; mensagens sem stack trace |
| **7** | `videocall/adaptadores.py` — Zoom, Teams, Meet | 13 testes. Pesquisa oficial antes do código |
| **8** | Este documento | — |

## Ciclo 7: o que a pesquisa mostrou

| Plataforma | Injeção direta | Mecanismo |
|---|---|---|
| **Zoom** | Sim | Closed Captioning REST API: host gera *caption URL*, POST de texto UTF-8 com `seq` crescente |
| **Teams** | Sim | Endpoint CART; organizador gera a URL de ingestão |
| **Google Meet** | **Não** | Sem API pública para app externo inserir legenda |

Para o Meet, `injecao_direta = False` e o texto vai para a área de transferência, com a
limitação declarada em `AdaptadorMeet.LIMITACAO`. Pior que legenda automática — e honesto
quanto a isso, em vez de aparentar suporte que não existe.

## Ciclo 9 — reconhecimento real com os modelos do SIGNLAB

Investigando por que `models/` estava vazio, apareceram dois impedimentos que nenhuma
arquitetura resolve sozinha:

**1. O `MotorKonectaV3` não roda neste ambiente.** Ele usa `mp.solutions.hands`, a API antiga
do MediaPipe. O pacote instalado é o `mediapipe 1.0.0`, que expõe apenas `Image`, `ImageFormat`
e `tasks` — **`mp.solutions` não existe**. O motor cai no caminho de indisponibilidade e nunca
extrai landmark nenhum. (Mesmo tropeço que derrubou o KONECTA V1 nesta máquina.)

**2. Os formatos de feature não conversavam.** O `MotorKonectaV3` monta 63 features cruas de
uma mão; os modelos do SIGNLAB esperam 128:

```
vetor[0:63]    mão esquerda xyz normalizado
vetor[63:126]  mão direita xyz normalizado
vetor[126:128] flags de presença
normalização:  punho na origem, escala punho → MCP do médio
```

**Entrega:** `providers/signlab_sinais.py` — usa a API `tasks` (a mesma do SIGNLAB, o que
mantém a extração idêntica à que gerou os modelos) e produz o vetor de 128 no layout exato.
Com isso os modelos já treinados passam a servir ao KONECTA, sem tocar no SIGNLAB.

| Verificação | Resultado |
|---|---|
| Modelo real do SIGNLAB carrega | ABACAXI, ABELHA, ABRAÇO |
| Nosso vetor alimenta o modelo real | predição e confiança válidas |
| Contrato confere com o `feature_config` gravado | teste falha se o SIGNLAB divergir |
| Latência (aquecida, 480×640) | **mediana 16ms → ~63 fps** |

O código de normalização é replicado, não importado, para o KONECTA não depender do diretório
do SIGNLAB em execução. O teste de contrato compara com o `feature_config` de dentro do
modelo: se o SIGNLAB mudar a extração, ele acusa — em vez de o reconhecimento degradar em
silêncio, que é o modo de falha pior.

## Integração no `main.py` — e dois defeitos que ela revelou

Os módulos passaram a ser usados de verdade pela janela: `Config` no arranque, `Motores`
escolhidos por configuração, `GerenciadorSessao` refletido na UI, sinal reconhecido enviado à
videochamada, motores encerrados no fechamento.

Ligar tudo expôs dois problemas que só aparecem com o app rodando:

**1. Acesso a widget fora da thread da GUI.** O `GerenciadorSessao` é notificado também pela
thread do asyncio (quando um sinal é reconhecido), e o observador tocava `motors_display`
direto. No Qt isso é comportamento indefinido. Corrigido com sinal Qt: o observador só emite,
e o slot roda na thread certa.

**2. O arranque cegava o app.** `disponivel()` chamava `joblib.load` dentro de método async,
segurando a thread do loop. Medido pelo smoke: **9 de 10 frames descartados** durante o
carregamento. Com a carga movida para executor: **10 de 10 processados**.

O segundo só apareceu porque o smoke passou a exigir contabilidade fechada
(`processados + descartados == emitidos`). Antes ele só verificava "processou algum frame" e
teria aprovado o app cego.

## Áudio → texto: o fluxo do ouvinte fechado

`providers/audio_local.py` implementa `AudioParaTextoProvider` com faster-whisper local.
É a implementação disponível hoje; quando o motor do time virar API, é escrever outra classe
com o mesmo contrato.

**Verificação real, não simulada:** o sintetizador de voz do Windows falou uma frase, o
loopback capturou e o provider transcreveu de volta.

```
ESPERADO:   "o konecta traduz libras em tempo real"
TRANSCRITO: "O Conecta traduz Libras em Tempo Real."
```

1406ms para 8s de áudio. Só o nome próprio escapou.

**Defeito que a integração revelou:** com áudio ligado o app **travava no encerramento**
(exit 139). Causa: `disponivel()` carregava o modelo — centenas de MB — e o Python espera as
threads do executor ao sair. Contradizia o que o próprio `base.py` define: *"checagem barata
de saúde"*. Corrigido: a checagem só confirma que dá para transcrever; o modelo carrega na
primeira transcrição de verdade.

Desligado por padrão (`KONECTA_AUDIO_ATIVO=true` liga): quem só precisa de Libras→texto não
deve pagar ~500MB de memória por um motor que não vai usar.

## Reconhecimento: export do SIGNLAB + lógica do KONECTA V1

Duas mudanças pedidas depois: consumir os **arquivos exportados pelo SIGNLAB** e reaproveitar
a **lógica de reconhecimento do V1**, que é a que se mostrou utilizável na prática.

### O que o SIGNLAB exporta

A rota `/experiments/{id}/export` entrega um `.zip` por experimento:

| Modalidade | Arquivo | Conteúdo |
|---|---|---|
| Estático (imagem) | `model.joblib` | bundle `{model, class_names}`, predição por frame |
| Temporal (vídeo) | `model.keras` | rede de sequência; `labels` no metadata dá a ordem do softmax |

Mais `metadata.json` com `classes`, `feature_config`, `metrics` e `model_type`.

`providers/export_signlab.py` lê as três formas que circulam entre as máquinas do time: o
`.zip`, a pasta descompactada e o `.joblib` cru. Recusa com mensagem clara o que não dá para
usar — zip corrompido, layout de features diferente, temporal sem `labels` (que produziria
índices sem nome em vez de palavras).

### O que veio do V1

`core/estabilizador.py` traz a lógica de `libras_recognizer.py` que faltava:

- **Limiar de confiança** — descarta predição fraca.
- **Hold-to-confirm** — a predição precisa persistir antes de virar texto. Sem isso, a 15fps
  saem dezenas de palavras por segundo e a legenda fica ilegível.
- **Frame ruim no meio não zera o progresso** — um frame fraco durante um sinal estável não
  obriga a pessoa a recomeçar.
- **Não repete o mesmo sinal em seguida** — mão parada não escreve a palavra várias vezes.
- **Reset ao perder as mãos** — tirar a mão e refazer o sinal é intenção de repetir.

E o provider passou a suportar **sinais dinâmicos**: `reconhecer_sequencia` monta a janela de
frames que a rede temporal espera, com o mesmo ajuste do V1 (repete o último quando falta,
corta pelo fim quando sobra, preservando o começo do gesto).

O estabilizador fica fora do provider de propósito: o provider responde *"o que é este
frame"*; o estabilizador responde *"o que a pessoa quis dizer"*.

### Uma instabilidade de teste, resolvida

Dois testes falhavam de forma intermitente (1 em 4 execuções). A corrida estava **no teste**,
não no código: ele afirmava sobre `_frame_pendente` enquanto o consumidor real drenava a fila
em outra thread. Tornados determinísticos, a suíte fecha **380 testes em 5/5 execuções**.

## Os dois fluxos no mesmo app

O KONECTA V3 passou a fazer os dois sentidos da conversa:

```
usuário SURDO    câmera → sinal → estabilizador → texto → videochamada
usuário OUVINTE  áudio do PC → texto → avatar em Libras
```

`capture/audio.py` captura o **loopback** (o que está tocando), não o microfone: numa
videochamada, quem o surdo precisa entender chega pela saída de áudio. A captura é segmentada
por VAD antes de transcrever — fluxo contínuo desperdiçaria CPU em silêncio e produziria
frases cortadas.

A câmera passou a usar o provider (que consome export do SIGNLAB) com o estabilizador do V1;
o `RecognizerPipeline` antigo virou fallback para quem ainda depende dele.

**Verificado com áudio real** (`tests/smoke_dois_fluxos.py`): o sintetizador do Windows fala,
o loopback captura, o Whisper transcreve, o avatar recebe — e o sinal da câmera chega à
videochamada **uma única vez apesar de 40 frames**, provando que o hold-to-confirm segura.

### Um crash que não foi diagnosticado — e o que se fez

Com os dois fluxos juntos, o app quebrava com **segmentation fault** (2 de 2), sempre ao
carregar o Whisper com câmera e captura ativas.

Bissecção feita, e **nenhuma reproduziu o crash**: Whisper sozinho; `cv2`+`mediapipe` antes do
Whisper; `soundcard` em `QThread` sob Qt; `soundcard` em thread comum; o formato exato do app
(Qt + QThread + executor do loop asyncio); e o mesmo com `webrtcvad` a cada frame. Todos
passaram.

**A causa raiz não foi encontrada.** O que se sabe: o mesmo modelo, no mesmo Python, roda
estável quando fica sozinho num processo — é assim que o TEXTO_PARA_LIBRAS opera há horas.
`providers/whisper_worker.py` isola a transcrição num processo, e o crash desapareceu.

Isso é isolamento, não diagnóstico, e está registrado como tal no cabeçalho do módulo. Se o
crash voltar em outra combinação, o bissetor terá de recomeçar de um ponto melhor: sabe-se que
não é import, não é `QThread`, e não é o VAD.

## O que ficou pendente, e por quê

- **Ciclo 8 não removeu `app_gui.py` e `app_gui_v2.py`.** Apagar código é decisão sua;
  as três GUIs seguem no repositório. O ponto de entrada real é `app_central/main.py`.
- **`vision_lab` continua com o extrator de ruído** (5.10). Consertar ou aposentar é decisão
  de produto, não de implementação.
- **`models/` continua vazio, mas deixou de bloquear**: o `SinaisSignlab` consome direto os
  modelos treinados em `SIGNLAB/projects/*/models/*.joblib`. Os modelos disponíveis hoje
  cobrem poucos sinais (o `exp_1` tem três) — ampliar vocabulário é treino no SIGNLAB, não
  trabalho de arquitetura aqui.
- **Providers de áudio→texto não implementados**: o motor é do Guilherme, e o contrato
  (`AudioParaTextoProvider`) já está pronto para recebê-lo.

## Duas correções que fiz neste documento

Registro porque a §17 pede rigor, e ambas foram erros meus:

1. Afirmei que o app abortava no primeiro frame por `asyncio.create_task` em slot Qt. **Falso
   para o código atual** — eu havia lido uma versão anterior do `main.py`. O desenho atual
   (loop em thread dedicada) está correto.
2. Afirmei que o `vision_lab` era "o ativo técnico real do projeto". **Falso** — ele devolve
   `np.random.randn(228)`. Eu havia lido a estrutura dos módulos, não o corpo do método.

Ambas as vezes o erro veio de concluir a partir de nomes e estrutura em vez de ler o código
que executa. É o mesmo tipo de engano que os 287 testes verdes produziram no projeto.

---

## O que eu não vou fazer

- Não vou tocar em SIGNLAB nem em TEXTO_PARA_LIBRAS.
- Não vou reescrever o `vision_lab` — ele é o ativo do projeto (§21 da spec).
- Não vou implementar integração com Teams/Zoom/Meet antes de investigar o que cada
  plataforma permite oficialmente.
- Não vou declarar nada pronto com base em teste verde: o projeto já tem 287 deles.
