# LSAE — Contexto completo do projeto (para discussão com terceiros/outras IAs)

> Este documento é autocontido: reúne o problema original, a arquitetura proposta, o que foi de fato implementado, os números reais medidos, os bugs encontrados e corrigidos, o mapa de código, e as decisões em aberto. Não assume que quem lê teve acesso à conversa que gerou isso.
>
> **Projeto:** KONECTA — sistema de reconhecimento de Libras por visão computacional (Python, OpenCV, MediaPipe, TensorFlow/Keras, scikit-learn, Tkinter), TCC de Vinicius Rosa Santos.
> **Data deste documento:** 2026-07-23
> **Arquivos relacionados no repositório:** [PLANO_GENERALIZACAO.md](PLANO_GENERALIZACAO.md) (proposta original v1.1, texto integral), [README_LSAE.md](README_LSAE.md) (pitch curto), [RESULTADOS_LSAE.md](RESULTADOS_LSAE.md) (relatório de resultados, mais enxuto que este).

---

## 1. O sistema existente (antes do LSAE)

`OCR/libras_recognizer.py` (2300 linhas) é uma aplicação Tkinter completa que:

- Captura vídeo da webcam, extrai landmarks de mão via MediaPipe HandLandmarker (21 pontos × 3 coordenadas × até 2 mãos = 126 features por frame), normalizados por mão (centralizado no pulso, escalado pela distância pulso→base do dedo médio, clipado em [-3,3]).
- Tem uma aba de **Coleta** (grava exemplos ao vivo, salvos como `.npy` em `dados_libras/{estaticos,dinamicos}/<sinal>/local/`), uma aba de **Treino** (treina um RandomForest para sinais estáticos — letras/números — e uma BiLSTM para sinais dinâmicos — palavras com movimento) e uma aba de **Reconhecer** (inferência ao vivo).
- Tem um dataset híbrido: dados **locais** (gravados pela interface) + dados **públicos** importados do **V-Librasil** (corpus da UFPE, ~4086 vídeos, ~3 execuções por sinal, 1364 sinais dinâmicos + letras estáticas A-G com 350 amostras locais).
- Antes deste trabalho, o treino usava `train_test_split` aleatório (separa por amostra, não por pessoa).

## 2. O problema que motivou o LSAE

> **Baixa capacidade de generalização entre diferentes sinalizantes.**

Com poucas execuções por sinal (~3 no V-Librasil), o modelo tem material de sobra para aprender características de QUEM gravou (tamanho de mão, velocidade, estilo) e pouco material para aprender o que define o sinal em si. Resultado hipotetizado: quem gravou é reconhecido, outra pessoa executando o mesmo sinal falha.

**Agravante identificado antes de qualquer correção:** a avaliação do modelo (`train_test_split` aleatório) mistura amostras da mesma pessoa entre treino e teste — então mesmo a acurácia "medida" podia estar inflada por vazamento, não só a generalização real.

## 3. A ideia do LSAE — arquitetura proposta

**LSAE = Libras Semantic Augmentation Engine.** Gera dados sintéticos de treino que preservam a identidade do sinal, combinando três camadas:

| Pilar | O que faz |
|---|---|
| **1. Estatístico** | Aprende como cada sinal varia naturalmente entre execuções reais: média, desvio-padrão, trajetória, velocidade, aceleração, amplitude — a distribuição do movimento, não cópias de vídeo. |
| **2. Biomecânico** | Conhece limites físicos da mão/braço. Não gera dedo atravessando a palma, rotação de punho impossível, etc. — só poses biologicamente plausíveis. |
| **3. Linguístico** | Entende parâmetros fonológicos da Libras (configuração de mão, orientação, movimento, localização, expressões não-manuais). Pode variar inclinação/distância/velocidade; não pode alterar configuração de mão, direção obrigatória do movimento ou ponto de articulação — isso descaracterizaria o sinal. |

Pipeline proposto: `Vídeo → MediaPipe → Landmarks → Normalização → LSAE → Validação Biomecânica → Validação Linguística → Validação Estatística → Landmarks Sintéticos Aprovados → Treinamento`.

**Papel explícito da IA no sistema:** a IA (LLM) **nunca gera landmarks diretamente** — coordenadas geradas por texto não têm grounding biomecânico, equivaleria a alucinar números. O papel da IA é analisar dataset, detectar sinais confundíveis, sugerir priorização, revisar/gerar código do motor, produzir relatórios. A geração numérica é sempre responsabilidade do motor determinístico/auditável.

### Ordem de implementação definida no plano original

| Fase | Conteúdo | Depende de | Status neste documento |
|---|---|---|---|
| 0 | Split de avaliação por sinalizante + baseline honesto | — | ✅ Feito |
| 1 | Pilar estatístico (média/variância/trajetória por sinal) | Fase 0 | ✅ Feito |
| 2 | Pilar biomecânico + augmentation geométrico/anatômico/cinemático | Fase 1 | ✅ Feito |
| 3 | Validação estatística concretizada (Mahalanobis/DTW) | Fase 2 | ✅ Feito |
| 4 | Validação linguística (tabela de tolerância manual por sinal) | Fase 1 | ⛔ **Pulada deliberadamente** (decisão do autor — ver seção 8) |
| 5 | Retreinar com dataset expandido, medir no split honesto | Fases 0-4 | ✅ Feito (sem a Fase 4) |
| 6 | Expor como MCP | Fase 5 validada | Não iniciado |

---

## 4. O que foi implementado, fase a fase

### Fase 0 — Split honesto por sinalizante (pré-requisito)

**Arquivo:** `OCR/libras_recognizer.py`

Problema técnico enfrentado: o sistema não guardava identidade de sinalizante em lugar nenhum. Solução encontrada:

- **Dados públicos (V-Librasil):** o log de conversão `vlibrasil_converter_20260630_184206.csv` (gerado por uma execução anterior do pipeline de importação, achado no repositório) mapeia exatamente cada `public_XXXX.npy` ao vídeo original, cujo nome contém o sinalizante real do V-Librasil (`Articulador1/2/3`). Isso deu 3 grupos de sinalizante genuínos para os ~4086 dados dinâmicos públicos, sem esforço manual.
- **Dados locais:** ninguém rastreava quem gravou (múltiplas pessoas gravaram sem identificação, confirmado pelo autor). Adicionado campo "ID do sinalizante" na aba de Coleta — dados futuros ficam identificados; dados antigos caem em `local_desconhecido`.
- `GroupShuffleSplit` (scikit-learn) no lugar de `train_test_split`, com fallback explícito quando há só 1 grupo (caso do modelo estático hoje).

**Bug encontrado e corrigido durante a implementação:** com poucos grupos (aqui, 3), passar `test_size` como fração de amostras faz o `GroupShuffleSplit` arredondar (`ceil`) para o número de grupos errado por erro de ponto flutuante — a primeira tentativa treinou com 1/3 dos dados e testou com 2/3 (invertido). Corrigido calculando o número de grupos de teste como inteiro explícito: `n_test_grupos = max(1, min(n_grupos-1, round(test_size*n_grupos)))`.

**Resultado (dinâmico, LSTM, 1364 classes):** split final = treino Articulador1+3 (2722 amostras) / teste Articulador2 (1364 amostras, nunca visto).

> 🎯 **Acurácia cross-signer real: 0.44%** (chance aleatória entre 1364 classes ≈ 0.07%)

`val_loss` cresceu monotonicamente do início ao fim do treino (7.2 → 13.4) enquanto a acurácia de treino subia normalmente — overfitting ao sinalizante, agora com número real.

**Estático (RandomForest, letras A-G, 350 amostras):** 98.57% — mas com split aleatório clássico (só existe 1 grupo de sinalizante, `local_desconhecido`, nos dados estáticos). Esse número é tratado como **não confiável** até haver sinalizantes distintos identificados.

### Pilar 1 — Conhecimento estatístico

**Arquivo:** `OCR/lsae/perfil_estatistico.py` (253 linhas)

Funções Python puras (só numpy), sem Tkinter/MediaPipe/TensorFlow. Para cada sinal (a partir das amostras reais, reamostradas para 30 pontos por interpolação linear): trajetória média/desvio-padrão por posição temporal, velocidade e aceleração (1ª e 2ª diferença), amplitude de movimento, duração.

Testado com dados sintéticos primeiro (reta conhecida confirma resample/velocidade/aceleração), depois rodado sobre o dataset real: **1364 perfis dinâmicos + 7 estáticos** calculados e salvos em `OCR/modelos/perfil_dinamico_sinais.pkl` / `perfil_estatico_sinais.pkl`.

**Achado (limitação, não bug):** a estatística de duração saiu degenerada — todo sinal, toda amostra, exatamente 30 frames, desvio-padrão zero. Tanto a coleta local (buffer fixo de 30 frames) quanto o importador do V-Librasil (`_amostrar_indices`) já reamostram para 30 frames *antes* de salvar — a duração original nunca é persistida. Velocidade/amplitude continuam informativas (ex.: "Às vezes" é o sinal mais rápido do dataset, vel=0.997; "Gay" o mais parado, vel=0.234).

### Pilar 2 — Motor biomecânico

**Arquivo:** `OCR/lsae/motor_biomecanico.py` (324 linhas)

Em vez de somar ruído direto em xyz, opera no espaço de **ossos** da árvore cinemática da mão (21 landmarks MediaPipe, vetor pai→filho, raiz = pulso):

- `reescalar_dedos` — muda comprimento do osso mantendo a direção (ângulo articular preservado por construção, não por checagem).
- `jitter_articular` — gira a direção do osso por ângulo pequeno e limitado (Rodrigues), mantém o comprimento.
- `rotacionar_3d` / `escalar_isotropico` — transformação rígida da mão inteira, usa eixo Z de verdade (a versão anterior do augmentation só girava em x/y).
- `validar_biomecanica` — rede de segurança: rejeita se o comprimento de osso variar além da tolerância (35% default) ou coordenada explodir.

Validado: garantias confirmadas por teste sintético (reescala acerta fator de comprimento exatamente e preserva ângulo; jitter preserva comprimento e respeita limite de ângulo; rotação/escala preservam todos os comprimentos de osso — matematicamente, uma transformação rígida não pode alterar comprimento). Em dado real (sinal "Abacaxi"): 20 gerações (600 avaliações mão-frame) → **0 descartes biomecânicos**, sem NaN/Inf.

### Fase 3 — Validação estatística

**Arquivo:** `OCR/lsae/validacao_estatistica.py` (296 linhas)

**Achado importante, documentado no próprio módulo:** a abordagem "de livro-texto" (Mahalanobis com covariância por sinal via Ledoit-Wolf, limiar qui-quadrado) foi testada **antes de ser adotada** e **falhou**. Com as 2-3 amostras reais por sinal que a maioria dos sinais dinâmicos tem, nenhum estimador de covariância por sinal é confiável — simulação confirmou que uma amostra sintética idêntica em distribuição à real era rejeitada ~100% das vezes, não por ser ruim, mas porque o estimador de variância é ruim nesse regime de amostra pequena (N≪F, F=126 dimensões).

**Correção adotada** (verificada por simulação antes de aplicar):
1. Média por sinal (confiável mesmo com N=2-3, vem do Pilar 1).
2. Variância **pooled** — agregada dos resíduos de todos os ~1364 sinais juntos (cada amostra menos a média do seu próprio sinal), dando milhares de graus de liberdade em vez de 1-2 por sinal.
3. Correção `variância × (1 + 1/N)` para compensar a incerteza de estimar a média de um sinal com poucas amostras (sem isso, ~90% de falsos positivos com N=2; com ela, ~3-4%, batendo com o percentil pedido).

DTW (Dynamic Time Warping) contra amostras reais do sinal, limiar = percentil das distâncias observadas entre as próprias amostras reais.

**Resultado real:** gerando 5 variações sintéticas (Pilar 2) para 50 sinais reais → **240/250 (96%) aceitas**. Controle negativo (amostra deliberadamente corrompida): corretamente rejeitado (100% dos frames fora da faixa).

### Fase 5 — Retreino com dataset aumentado

**Integração:** `GerenciadorModelos._gerar_amostras_lsae` + parâmetro `augmentar_lsae`/`fator_lsae` em `treinar_dinamico`, dentro de `OCR/libras_recognizer.py`. A geração acontece **só sobre o treino, pós-split** — nunca toca no teste (evita vazamento). Perfil (Pilar 1) e variância pooled (Fase 3) usados na validação também vêm só do treino.

Mesmo split honesto da Fase 0 (garantido pelo mesmo `random_state=42`). Para cada sinal do treino com ≥2 amostras reais, gerado até 2× amostras sintéticas aceitas pelo filtro da Fase 3. Resultado: **5432 amostras sintéticas aprovadas para 1358 sinais**, treino final 2722 → 8154 amostras.

> 🎯 **Acurácia cross-signer com LSAE: 0.22%** — **pior** que o baseline de 0.44% da Fase 0.

Acurácia de treino chegou a 91% já na época 19 (mais rápido que os 70% da Fase 0 no mesmo ponto), `val_loss` cresceu ainda mais rápido (7.2 → 20.0 contra 7.2 → 13.4). O modelo overfitou *mais* rápido com o dataset aumentado.

**Análise da causa provável (não é bug de implementação — split e integração foram verificados: teste nunca recebe sintético, mesmo grupo retido, mesmas contagens):** o motor biomecânico gera variações **pequenas e locais** em torno das amostras reais de Articulador1/3 — reescala de dedo ±10%, rotação ±8°, jitter ~2°. Isso deixa a distribuição de treino um pouco mais "borrada", mas continua sendo, fundamentalmente, a mesma geometria e o mesmo estilo de execução de Articulador1/3. O modelo nunca é exposto a nada parecido com o estilo de Articulador2 (outra pessoa, outras proporções, outros maneirismos). Mais dados "parecidos com quem já se conhece" reforça o padrão que causa overfitting, em vez de contrariá-lo.

**Conclusão que o autor quer discutir:** este é um resultado negativo, mas defensável — evidência quantitativa de que augmentation biomecânico/geométrico local, sem acesso a variação real de estilo entre pessoas, não resolve generalização cross-signer neste dataset, mesmo implementado com rigor (split sem vazamento, motor validado, filtro calibrado). Sustenta com dados a necessidade de uma das duas rotas já previstas como trabalho futuro no plano original: (1) mais sinalizantes reais (o campo de ID de sinalizante existe agora para viabilizar isso), ou (2) modelos generativos (VAE/Diffusion/Transformer) capazes de aprender/extrapolar variação de *estilo*, não só perturbação local — explicitamente fora do escopo original por peso computacional, mas agora com justificativa empírica.

---

## 5. QA — bugs encontrados e corrigidos

Depois da Fase 5, foi feita uma bateria de 26 testes de borda (2 arquivos de teste cobrindo os 4 módulos) que não tinham sido exercitados durante o desenvolvimento incremental. Dois bugs reais apareceram e foram corrigidos:

1. **Treino podia abortar por completo com `augmentar_lsae=True`** se nenhum sinal do treino tivesse ≥2 amostras reais (dataset pequeno/degenerado) — `ValueError` não tratado derrubava o treino inteiro. Corrigido: agora loga aviso e segue sem augmentation extra (`try/except` em volta da chamada + `except ValueError` dentro de `estimar_variancia_pooled_dinamica`).
2. **`resample_sequencia` com sequência de 0 frames devolvia shape errado silenciosamente** (`np.repeat` de array vazio continua vazio) em vez de erro claro. Corrigido para levantar `ValueError` explícito na origem.

Depois dos fixes: 26/26 testes passam, e os resultados reais (Fase 0, Fase 3, estático) foram re-executados para confirmar que nada regrediu.

---

## 6. Mapa de código

```
OCR/
├── libras_recognizer.py          # App principal (Tkinter). Fase 0 (split honesto, signer_id,
│                                  # campo de coleta) + hook augmentar_lsae/fator_lsae em
│                                  # treinar_dinamico (Fase 5) vivem aqui.
├── main.py                       # Launcher portátil (detecta BASE_DIR, roda libras_recognizer.py
│                                  # via runpy.run_path — ver nota de empacotamento na seção 8).
├── Libras_OCR.spec                # Spec do PyInstaller para gerar o .exe.
├── dados_libras/
│   ├── estaticos/<SINAL>/local/   # Amostras estáticas (só local, 7 letras, 350 amostras)
│   └── dinamicos/<SINAL>/{local,public}/  # Amostras dinâmicas (1364 sinais, 4086 públicas)
├── vlibrasil_converter_20260630_184206.csv  # Log de conversão V-Librasil — fonte do signer_id público
├── lsae/                          # Pacote novo, funções Python puras (numpy/scipy/sklearn),
│   │                               # sem Tkinter/MediaPipe/TensorFlow — testável isoladamente.
│   ├── perfil_estatistico.py      # Pilar 1
│   ├── motor_biomecanico.py       # Pilar 2
│   └── validacao_estatistica.py   # Fase 3
└── modelos/
    ├── modelo_estatico.pkl, encoder_estatico.pkl           # RandomForest
    ├── modelo_dinamico.keras, encoder_dinamico.pkl, normalizacao_dinamico.npz  # LSTM
    ├── perfil_estatico_sinais.pkl, perfil_dinamico_sinais.pkl   # Saída do Pilar 1
    └── variancia_pooled_estatica.pkl, variancia_pooled_dinamica.pkl  # Saída da Fase 3
```

### Funções/pontos de entrada centrais

| Função | Arquivo | O que faz |
|---|---|---|
| `GerenciadorDados._resolver_signer_id` | libras_recognizer.py | Reconstrói signer_id por amostra (público via CSV, local via nome de arquivo) |
| `GerenciadorModelos._split_honesto_por_sinalizante` | libras_recognizer.py | `GroupShuffleSplit` com correção de arredondamento de grupos |
| `GerenciadorModelos._gerar_amostras_lsae` | libras_recognizer.py | Orquestra Pilares 1-3 sobre o treino pós-split, gera amostras sintéticas aprovadas |
| `calcular_perfil_dinamico` / `calcular_perfil_estatico` | perfil_estatistico.py | Pilar 1 |
| `augmentar_sequencia` / `augmentar_pose` | motor_biomecanico.py | Pilar 2 — ponto de entrada principal do motor |
| `validar_estatisticamente_dinamico` | validacao_estatistica.py | Fase 3 — combina Mahalanobis + DTW |
| `estimar_variancia_pooled_dinamica` | validacao_estatistica.py | A correção central da Fase 3 (variância pooled) |

---

## 7. Estado atual da interface (Tkinter)

- Aba **Coleta**: novo campo "ID do sinalizante" (opcional; vazio = `local_desconhecido`).
- Aba **Treino**: log mostra contagem de sinalizantes detectados, se o split foi honesto ou caiu em fallback aleatório, e rotula a acurácia final como "🎯 CROSS-SIGNER" quando aplicável.
- **`augmentar_lsae` não está exposto na UI ainda** — só acessível chamando `treinar_dinamico(..., augmentar_lsae=True, fator_lsae=2)` diretamente via script/Python. Não há botão/checkbox para isso na aba Treino.

---

## 8. O que NÃO foi feito / decisões e riscos em aberto

Estes são pontos genuinamente não resolvidos — bons candidatos para discutir com outra IA ou revisar:

1. **Fase 4 (validação linguística) foi pulada deliberadamente.** O documento original pede uma tabela de tolerância definida manualmente por sinal (ex.: "distância polegar-indicador não pode variar mais que X%"). Com 1364 sinais dinâmicos, isso não foi feito — decisão consciente do autor para chegar mais rápido ao resultado central (Fase 5). Pergunta em aberto: a Fase 4 teria mudado o resultado da Fase 5? Provavelmente não resolveria o problema de fundo (falta de variação de *estilo* entre sinalizantes), já que a Fase 4 restringe variação, não a expande — mas vale uma segunda opinião.

2. **O resultado da Fase 5 é negativo.** LSAE (Pilares 1-3) piorou a acurácia cross-signer (0.44% → 0.22%). A hipótese de causa (augmentation local em torno dos mesmos 2 sinalizantes não injeta variação de estilo real) não foi testada isoladamente — por exemplo, não foi feito um experimento controlado variando só `fator_lsae` (1x, 2x, 4x...) para ver se o efeito é monotônico ou se há um ponto ótimo pequeno.

3. **Estático nunca foi aumentado.** Pilares 2-3 têm funções equivalentes para pose única (`validar_mahalanobis_estatico`, `reescalar_dedos`/`jitter_articular` funcionam em poses estáticas também), mas não existe um `_gerar_amostras_lsae`-equivalente para o modelo estático, e ele ainda não tem sinalizante identificado (só 1 grupo, `local_desconhecido`) — não dá pra medir se ajudaria até existir diversidade real de sinalizante nos dados locais.

4. **Performance da geração LSAE (~3 min para os 1364 sinais).** Gargalo real: `validar_mahalanobis_dinamico` reamostra as amostras reais do zero a cada tentativa de geração, quando poderia reamostrar uma vez por sinal e reaproveitar. Não corrigido ainda — afeta velocidade de iteração se alguém quiser variar hiperparâmetros do LSAE repetidamente.

5. **Seed fixa (42) na geração sintética** (`_gerar_amostras_lsae`) — toda geração com LSAE é determinística/idêntica entre execuções. Bom para reprodutibilidade, ruim se algum dia quiser ensemble ou análise de variância entre execuções.

6. **Risco de empacotamento (PyInstaller):** `main.py` executa `libras_recognizer.py` via `runpy.run_path` (não import estático), o que esconde os imports da análise do PyInstaller — por isso `Libras_OCR.spec` lista `hiddenimports` manualmente para cv2/mediapipe/tensorflow/sklearn/numpy. **`scipy`** (usado por `validacao_estatistica.py` via `scipy.stats.chi2`) não está nessa lista. Hoje isso não quebra nada porque `augmentar_lsae` não está exposto na UI — mas se isso mudar e o .exe for regerado a partir do spec atual, vai falhar com `ImportError` na primeira tentativa de treino com LSAE ativado.

7. **`_gerar_amostras_lsae` usa pesos flat (`peso_base = média × 0.9`)** para as amostras sintéticas — não replica a lógica mais fina de `_calcular_pesos_amostras` (que dá peso extra a `rotulos_prioritarios`). Se o treino combinar LSAE com priorização de sinais locais, essa interação não foi testada.

8. **Duração como estatística é degenerada** (ver Pilar 1) — todo o dataset dinâmico já vem reamostrado para exatamente 30 frames antes de chegar em qualquer código deste projeto. Para uma estatística de duração real, seria preciso capturar o frame-count original antes do resample, tanto na coleta local quanto no importador do V-Librasil — nenhum dos dois foi alterado.

---

## 9. Perguntas para discutir com outras IAs

- O resultado negativo da Fase 5 é esperado dado o desenho do experimento, ou há alguma variação de augmentation biomecânico (não testada aqui) que poderia ajudar mesmo sem variar estilo entre pessoas?
- Vale a pena tentar um `fator_lsae` bem menor (ex. 0.5x) antes de descartar a abordagem biomecânica por completo, ou o argumento teórico (augmentation local não substitui diversidade real de sinalizante) já é suficiente para não perder tempo nisso?
- Dado que só há 3 sinalizantes reais no dataset inteiro (V-Librasil), qualquer split honesto vai ser "leave-one-of-three-out" — isso é suficiente para uma conclusão de TCC, ou o argumento fica mais forte só depois de coletar dados de mais pessoas reais (usando o campo de ID de sinalizante agora disponível)?
- A Fase 4 (validação linguística manual) faria sentido pular popular via IA para um subconjunto de sinais (ex.: os 7 estáticos + um punhado de dinâmicos prioritários), como prova de conceito, mesmo sem cobrir os 1364 sinais inteiros?
- O caminho de modelos generativos (VAE/Transformer para sequências de landmarks) citado como trabalho futuro é viável dentro do prazo de TCC, ou é melhor direcionar o esforço restante para expandir a coleta de sinalizantes reais?
