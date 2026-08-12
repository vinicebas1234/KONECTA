# LSAE — Resultados Experimentais

> Complementa [PLANO_GENERALIZACAO.md](PLANO_GENERALIZACAO.md) (arquitetura) e [README_LSAE.md](README_LSAE.md) (proposta).
> Este documento registra o que foi **implementado e medido**, não o que está planejado.
>
> **Projeto:** KONECTA — Reconhecimento Inteligente de Libras
> **Autor:** Vinicius Rosa Santos
> **Data:** 2026-07-21

---

## Resumo executivo

| Fase | O que foi feito | Resultado |
|---|---|---|
| 0 — Split honesto | `GroupShuffleSplit` por sinalizante em vez de `train_test_split` aleatório | Baseline real: **0.44%** de acurácia cross-signer (dinâmico) |
| 1 — Estatístico | Perfil por sinal (média/desvio/trajetória/velocidade/aceleração/amplitude) | 1364 perfis dinâmicos + 7 estáticos calculados sobre dado real |
| 2 — Biomecânico | Motor de augmentation por cinemática óssea (reescala, jitter, rotação 3D) | 0 rejeições biomecânicas em teste com dado real; garantias verificadas por teste sintético |
| 3 — Estatístico (filtro) | Mahalanobis (variância pooled) + DTW contra amostras reais | 96% de aceitação de sintéticos plausíveis, controle negativo corretamente rejeitado |
| 5 — Retreino | LSTM retreinado com dataset aumentado (2722 → 8154 amostras de treino) | **0.22%** — pior que o baseline. Ver análise abaixo. |

**Conclusão central:** o pipeline LSAE (Pilares 1–3, augmentation biomecânico/estatístico) foi implementado, testado e integrado corretamente — mas **não melhorou a generalização cross-signer** neste dataset. O resultado é negativo e é reportado como tal, com a análise de causa provável na seção da Fase 5.

---

## Fase 0 — Pré-requisito: split honesto por sinalizante

### Problema encontrado

`libras_recognizer.py` usava `train_test_split` aleatório, que separa por *amostra*, não por *pessoa*. Isso permite vazamento: variações da mesma pessoa podem estar em treino e teste ao mesmo tempo, inflando a acurácia medida sem que o modelo generalize de fato.

### O que foi implementado

- `signer_id` reconstruído por amostra:
  - **Dados públicos (V-Librasil):** o log `vlibrasil_converter_20260630_184206.csv` mapeia exatamente cada `public_XXXX.npy` ao vídeo original, cujo nome contém o Articulador (1/2/3) — o sinalizante real do dataset público. Isso deu 3 grupos de sinalizante genuínos para os dados dinâmicos, sem esforço manual algum.
  - **Dados locais:** não há rastreio de quem gravou (múltiplas pessoas gravaram sem identificação). Adicionado campo "ID do sinalizante" na aba de Coleta do app, para que dados futuros já venham identificados. Dados locais existentes caem em `local_desconhecido`.
- `GroupShuffleSplit` (scikit-learn) substituindo `train_test_split`, com fallback explícito e sinalizado no relatório quando não há sinalizantes suficientes (caso atual do modelo estático: só 1 grupo, `local_desconhecido`).
- **Bug de calibração encontrado e corrigido:** com poucos grupos (aqui, 3), passar `test_size` como fração de amostras faz o `GroupShuffleSplit` arredondar (`ceil`) para o número de grupos errado por erro de ponto flutuante — a primeira tentativa treinou com 1/3 dos dados e testou com 2/3 (invertido). Corrigido calculando o número de grupos de teste explicitamente como inteiro.

### Resultado

Split final: treino = Articulador1 + Articulador3 (2722 amostras), teste = Articulador2 (1364 amostras, sinalizante nunca visto no treino).

> **Acurácia cross-signer real: 0.44%** (chance aleatória entre 1364 classes ≈ 0.07%)

`val_loss` cresceu monotonicamente do início ao fim do treino (7.2 → 13.4) enquanto a acurácia de treino subia normalmente — retrato clássico de overfitting ao sinalizante, agora com número real por trás em vez de intuição.

**Modelo estático (RandomForest, A–G):** 98.57% — mas com split aleatório clássico, porque os dados estáticos ainda não têm sinalizante identificado. Esse número deve ser tratado como **não confiável** para generalização até que coletas futuras usem o novo campo de sinalizante.

Código: [OCR/libras_recognizer.py](OCR/libras_recognizer.py) (`GerenciadorDados._resolver_signer_id`, `GerenciadorModelos._split_honesto_por_sinalizante`).

---

## Pilar 1 — Conhecimento estatístico

Módulo: [OCR/lsae/perfil_estatistico.py](OCR/lsae/perfil_estatistico.py)

Para cada sinal, calcula (a partir das amostras reais, reamostradas para 30 pontos por interpolação linear):
- trajetória média e desvio-padrão por posição temporal;
- velocidade e aceleração (primeira e segunda diferença da trajetória);
- amplitude de movimento (min-max por amostra, depois média);
- duração.

**Validação:** testado primeiro com dados sintéticos (reta conhecida → confirma resample/velocidade/aceleração), depois rodado sobre o dataset real: 1364 perfis dinâmicos + 7 estáticos.

**Achado relevante (limitação, não bug):** a estatística de duração saiu completamente degenerada — todo sinal, toda amostra, exatamente 30 frames, desvio-padrão zero. Tanto a coleta local (buffer fixo de 30 frames) quanto o importador do V-Librasil (`_amostrar_indices`) já reamostram para 30 frames *antes* de salvar o `.npy` — a informação de duração original nunca chega a ser persistida. Velocidade/trajetória continuam informativas (ex.: "Às vezes" é o sinal mais rápido do dataset, vel=0.997; "Gay" o mais parado, vel=0.234), só a duração como estatística isolada não presta enquanto o pipeline de captura não mudar.

---

## Pilar 2 — Conhecimento biomecânico (motor de augmentation)

Módulo: [OCR/lsae/motor_biomecanico.py](OCR/lsae/motor_biomecanico.py)

Em vez de somar ruído direto nas coordenadas xyz, opera no espaço de **ossos** da árvore cinemática da mão (21 landmarks do MediaPipe, vetor pai→filho):

- `reescalar_dedos` — muda o comprimento do osso mantendo a direção exatamente igual (ângulo articular preservado por construção).
- `jitter_articular` — gira a direção do osso por um ângulo pequeno e limitado, mantendo o comprimento.
- `rotacionar_3d` / `escalar_isotropico` — transformação rígida da mão inteira (usa o eixo Z de verdade; a versão anterior do augmentation só girava em x/y).
- `validar_biomecanica` — rede de segurança: rejeita se o comprimento de osso variar além da tolerância ou se alguma coordenada explodir.

**Validação:** garantias confirmadas por teste sintético (reescala acerta o fator de comprimento exatamente e preserva ângulo; jitter preserva comprimento e respeita o limite de ângulo; rotação/escala preservam todos os comprimentos de osso). Em cima de dado real (sinal "Abacaxi"): 20 gerações (600 avaliações mão-frame) → **0 descartes biomecânicos**, sem NaN/Inf.

---

## Fase 3 — Validação estatística

Módulo: [OCR/lsae/validacao_estatistica.py](OCR/lsae/validacao_estatistica.py)

### Achado importante: a abordagem "de livro-texto" falha na prática

A ideia óbvia — Mahalanobis com covariância por sinal (Ledoit-Wolf), limiar qui-quadrado — foi testada **antes** de ser adotada, e falhou: com as 2–3 amostras reais por sinal que a maioria dos sinais dinâmicos tem, nenhum estimador de covariância por sinal (nem Ledoit-Wolf, nem diagonal) é confiável. Simulação confirmou: a estimativa de variância de 2–3 pontos em 126 dimensões é tão instável que uma amostra sintética idêntica em distribuição à real era rejeitada quase 100% das vezes — não por ser ruim, mas porque o próprio estimador de variância é ruim nesse regime de amostra pequena.

### Correção adotada (verificada por simulação antes de aplicar)

1. **Média por sinal** (confiável mesmo com N=2–3, vem do Pilar 1).
2. **Variância *pooled*** — agregada de resíduos de todos os ~1364 sinais juntos (cada amostra menos a média do seu próprio sinal), dando milhares de graus de liberdade em vez de 1–2 por sinal.
3. **Correção `variância × (1 + 1/N)`** para compensar a incerteza de estimar a média de um sinal com poucas amostras — sem essa correção o limiar fica mal calibrado (~90% de falsos positivos com N=2; com ela, ~3-4%, batendo com o percentil pedido).

DTW (Dynamic Time Warping) contra as amostras reais do sinal, com limiar dado pelo percentil das distâncias observadas entre as próprias amostras reais — não sofre do mesmo problema (compara sequência inteira, não estima variância por dimensão).

### Resultado

Gerando 5 variações sintéticas (Pilar 2) para 50 sinais reais diferentes: **240/250 (96%) aceitas**. Amostra deliberadamente corrompida usada como controle negativo: corretamente rejeitada (100% dos frames fora da faixa esperada).

---

## Fase 5 — Retreino com dataset aumentado

Integração: `GerenciadorModelos._gerar_amostras_lsae` + parâmetro `augmentar_lsae` em `treinar_dinamico` ([OCR/libras_recognizer.py](OCR/libras_recognizer.py)). A geração acontece **só sobre o conjunto de treino, pós-split** — nunca toca no teste, evitando vazamento. Perfil (Pilar 1) e variância pooled (Fase 3) usados na validação também são calculados só a partir do treino.

### Setup

Mesmo split honesto da Fase 0 (garantido pelo mesmo `random_state=42`): treino = Articulador1+3, teste = Articulador2. Para cada sinal do treino com ≥2 amostras reais, gerado até `2×` amostras sintéticas (aceitas pelo filtro da Fase 3). Resultado: 5432 amostras sintéticas aprovadas para 1358 sinais, treino final de 2722 → 8154 amostras.

### Resultado

> 🎯 **Acurácia cross-signer com LSAE: 0.22%** — pior que o baseline de 0.44% da Fase 0.

Acurácia de treino chegou a 91% já na época 19 (mais rápido que os 70% da Fase 0 no mesmo ponto), enquanto `val_loss` cresceu ainda mais rápido (7.2 → 20.0, contra 7.2 → 13.4 sem LSAE). O modelo overfitou *mais* rápido com o dataset aumentado, não menos.

### Por que isso aconteceu (análise, não é bug de implementação)

O split honesto e a integração foram verificados (mesmo grupo retido, mesmas contagens, teste nunca recebe sintético). A causa mais provável é conceitual: o motor biomecânico (Pilar 2) gera variações **pequenas e locais** em torno das amostras reais de Articulador1/3 — reescala de dedo ±10%, rotação ±8°, jitter ~2°. Isso deixa a distribuição de treino um pouco mais "borrada", mas continua sendo, fundamentalmente, a mesma geometria e o mesmo estilo de execução de Articulador1 e Articulador3. O modelo nunca é exposto a nada que se pareça com o estilo de execução de Articulador2 — uma pessoa diferente, com proporções de mão, velocidade e maneirismos próprios. Mais dados "parecidos com quem já se conhece" reforça o padrão que causa o overfitting, em vez de contrariá-lo.

### Implicação para o TCC

Este é um **resultado negativo, mas defensável e cientificamente útil**: evidência quantitativa de que augmentation biomecânico/geométrico local, sem acesso a variação real de estilo entre pessoas, não resolve o problema de generalização cross-signer neste dataset — mesmo implementado com rigor (validação em cada etapa, split sem vazamento, filtro estatístico calibrado). Isso sustenta com dados, e não apenas intuição, a necessidade de uma das duas rotas já previstas como trabalho futuro no plano original:

1. **Mais sinalizantes reais** — o campo de "ID do sinalizante" adicionado na Fase 0 existe exatamente para viabilizar isso daqui pra frente.
2. **Modelos generativos** (VAE/Diffusion/Transformer) capazes de aprender e extrapolar variação de *estilo*, não só perturbação biomecânica local em torno de uma amostra existente — explicitamente fora do escopo original por serem pesados demais para o prazo do TCC, mas agora com justificativa empírica de por que a alternativa mais simples não basta.

---

## Onde está o código

| Módulo | Conteúdo |
|---|---|
| [OCR/libras_recognizer.py](OCR/libras_recognizer.py) | Split honesto (Fase 0), campo de sinalizante na coleta, hook `augmentar_lsae` no treino (Fase 5) |
| [OCR/lsae/perfil_estatistico.py](OCR/lsae/perfil_estatistico.py) | Pilar 1 — perfil estatístico por sinal |
| [OCR/lsae/motor_biomecanico.py](OCR/lsae/motor_biomecanico.py) | Pilar 2 — motor de augmentation biomecânico |
| [OCR/lsae/validacao_estatistica.py](OCR/lsae/validacao_estatistica.py) | Fase 3 — filtro estatístico (Mahalanobis pooled + DTW) |
| `OCR/modelos/perfil_*.pkl`, `variancia_pooled_*.pkl` | Artefatos calculados sobre o dataset real |

Todos os três módulos em `OCR/lsae/` são funções Python puras (só numpy/scipy/sklearn), testáveis isoladamente sem Tkinter/MediaPipe/TensorFlow, e cada um foi validado primeiro com dados sintéticos controlados antes de ser aplicado ao dataset real — inclusive quando isso revelou que a abordagem inicial estava errada (Fase 3) ou que o resultado esperado não se confirmou (Fase 5).
