# KONECTA — Contexto completo do projeto (sistema inteiro + LSAE)

> Documento autocontido para discussão externa (outras IAs, orientador, colegas). Cobre o projeto **KONECTA** como um todo — não só o LSAE — sua história, arquitetura atual verificada, dataset, empacotamento, e a frente de trabalho LSAE (problema, arquitetura, implementação, resultados reais, QA). Quem ler só este arquivo tem contexto suficiente para discutir qualquer parte do projeto.
>
> **Autor:** Vinicius Rosa Santos (TCC) · **GitHub:** [vinicebas1234/KONECTA](https://github.com/vinicebas1234/KONECTA)
> **Data deste documento:** 2026-07-23
> **Documentos relacionados no repositório** (mais focados, este é o mais completo): [PLANO_GENERALIZACAO.md](PLANO_GENERALIZACAO.md), [README_LSAE.md](README_LSAE.md), [RESULTADOS_LSAE.md](RESULTADOS_LSAE.md), [CONTEXTO_LSAE_COMPLETO.md](CONTEXTO_LSAE_COMPLETO.md) (só a parte LSAE), [README.md](README.md), [TECNICO.md](TECNICO.md), [EXE_PORTAVEL.md](EXE_PORTAVEL.md) (parcialmente desatualizados — ver seção 3).

---

## 1. O que é o KONECTA

Sistema de **reconhecimento de Libras (Língua Brasileira de Sinais) por visão computacional**, TCC de Vinicius Rosa Santos. Propósito: capturar vídeo de webcam em tempo real, detectar landmarks de mão, classificar o sinal (letra, número ou palavra/gesto com movimento) e converter para texto — foco em acessibilidade e inclusão digital para comunicação entre pessoas surdas e ouvintes.

Stack: **Python, OpenCV (captura), MediaPipe (landmarks de mão), scikit-learn (RandomForest), TensorFlow/Keras (BiLSTM), Tkinter (interface local)**.

## 2. Histórico e evolução (do git log)

O projeto passou por várias reformulações antes de chegar ao estado atual — importante pra não confundir documentação antiga com o sistema de hoje:

1. **Início:** captura + MediaPipe Holistic (mãos + pose corporal, 225 features) + KNN k=1 por similaridade coseno. Documentado em `TECNICO.md` (hoje **desatualizado** — fala de 225 features, KNN, só 2 sinais dinâmicos de exemplo).
2. **Otimização:** trocou Holistic por só-mãos (126 features: 2 mãos × 21 landmarks × xyz) — "Otimiza arquitetura Holistic: 1629→225 features, remove rosto custoso" e trocas subsequentes.
3. **Modelo:** RandomForest (estático) + tentativas de KNN/DTW para dinâmico, depois consolidado em **BiLSTM** (3 camadas, `_criar_modelo_dinamico`) — é o que está em produção hoje.
4. **Import de dataset externo:** integração do corpus **V-Librasil** (UFPE) via múltiplos scripts de importação (ver seção 3.4 — há 3 variantes, só uma é a fonte real dos dados atuais).
5. **Interface de transcrição em tempo real**, feedback de reconhecimento, correções de UX.
6. **Empacotamento em EXE portátil** (commits mais recentes antes deste trabalho): `main.py` como launcher universal + `Libras_OCR.spec` (PyInstaller) — ver seção 5.
7. **Exploração inicial do LSAE** (`lsae_demo/`, `LSAE-repo/`) — uma prova de conceito em pequena escala, feita antes da frente de trabalho documentada nas seções 7-11 deste documento.
8. **Este trabalho** (sessão atual): implementação completa e rigorosa do LSAE (Fases 0, 1, 2, 3, 5), com split honesto por sinalizante, motor biomecânico, filtro estatístico, retreino, e QA.

## 3. Arquitetura atual (verificada por leitura direta do código, não por documentação)

### 3.1 Pipeline de captura e features

`OCR/libras_recognizer.py` → classe `DetectorMaos`: MediaPipe `HandLandmarker` (não mais Holistic), até 2 mãos, 21 landmarks × 3 coords = 63 por mão, 126 total (`TOTAL_FEATURES`). Normalização por mão em `_normalizar_mao`: centraliza no pulso (landmark 0), escala pela distância pulso→base do dedo médio (landmark 9), clipa em [-3, 3]. Mão não detectada = vetor de zeros.

### 3.2 Dados

`dados_libras/{estaticos,dinamicos}/<SINAL>/{local,public}/*.npy`:
- **Estáticos** (pose única, 126 features): só sinais **locais**, 7 letras (A-G), 50 amostras cada = 350 amostras. Sem dado público.
- **Dinâmicos** (sequência, salva como (n_frames, 126)): **4086 amostras públicas** (V-Librasil, 1364 sinais, ~3 execuções/sinal) + ~90 amostras locais (que falham na validação de frames mínimos hoje — ver seção 8).
- Toda sequência dinâmica, seja local ou pública, já chega reamostrada para **exatamente 30 frames** antes de ser salva (buffer fixo na coleta local; `_amostrar_indices` no importador do V-Librasil) — implicação discutida na seção 9.

### 3.3 Modelos

- **Estático:** `RandomForestClassifier` (300 árvores, max_depth 25) — `GerenciadorModelos.treinar_estatico`.
- **Dinâmico:** BiLSTM (`_criar_modelo_dinamico`) — 3 camadas Bidirectional LSTM (128→256→256) + BatchNorm + Dropout, softmax sobre 1364 classes, `EarlyStopping`/`ReduceLROnPlateau`/`ModelCheckpoint`, até 150 épocas.
- Persistidos em `OCR/modelos/` (`.pkl` para estático, `.keras` + encoder + normalização para dinâmico).

### 3.4 Import do dataset público — atenção a scripts redundantes/legados

Existem **3 scripts de importação do V-Librasil** no diretório `OCR/`, de gerações diferentes:
- `importar_dataset_libras.py` / `importar_dataset_libras_CORRIGIDO.py` / `importar_dataset_libras_CORRIGIDO (1).py` — versões mais antigas, leem `annotations.csv` (que tem uma coluna `user_id` = `Articulador1/2/3`), mas salvam os `.npy` com nome sequencial (`001.npy`, `002.npy`...) sem preservar de forma recuperável qual vídeo virou qual arquivo.
- **`vlibrasil_converter.py`** (raiz do projeto, também copiado em `OCR/`) — é o script que **de fato gerou os dados públicos atualmente em disco**: processa vídeos por pasta de sinal, salva como `public_XXXX.npy`, e crucialmente **grava um log CSV** (`vlibrasil_converter_20260630_184206.csv`) mapeando cada `public_XXXX.npy` ao nome do vídeo original (que contém `Articulador1/2/3`). Confirmado por auditoria: as 4086 linhas `,ok,` do CSV batem exatamente com os 4086 arquivos `public_*.npy` em disco.

**Conclusão prática:** `vlibrasil_converter.py` + seu CSV é a fonte de verdade hoje. Os outros três scripts de importação (e os arquivos `libras_recognizer_backup*.py`, `libras_recognizer_corrigido.py`, `corrigir_libras_recognizer.py`, `gerar_libras_recognizer_corrigido.py`) parecem ser **artefatos de sessões de correção anteriores** — vale confirmar com o autor se ainda servem para algo ou podem ser arquivados/removidos, porque hoje competem visualmente com o código atual sem estarem em uso.

### 3.5 Interface (Tkinter, `LibrasApp`)

Três abas:
- **📦 Coleta** — grava amostras ao vivo. Campo novo (desta sessão): **ID do sinalizante**.
- **🧠 Treino** — botões "Treinar Estático"/"Treinar Dinâmico", configuração de peso híbrido local/público, log detalhado (agora inclui contagem de sinalizantes e modo de split — ver seção 7).
- **🔍 Reconhecer** — inferência ao vivo, com limiar de confiança e tempo de confirmação configuráveis.

## 4. Diretórios auxiliares — o que são (para não confundir escopo)

- **`lsae_demo/` e `LSAE-repo/`** — uma **prova de conceito anterior a este trabalho**: demo isolado (`lsae_demo.py`) que já validava, em pequena escala (1 sinal, "AMOR", 30 execuções reais), o mecanismo central do LSAE — reescala por osso, rotação 3D, jitter, e um filtro DTW simples. O próprio README desse demo já dizia explicitamente: *"não mede ganho de acurácia cross-signer — depende de retreinar com split por sinalizante, próxima etapa"*. É exatamente o que as seções 7-11 deste documento descrevem ter sido feito, em escala real (1364 sinais) e com rigor adicional (split corrigido, Mahalanobis calibrado, retreino real).
- **`vlibra/`** — **não é código do autor**: é o repositório oficial vendorizado do **VLibras Translator (API)**, o tradutor texto→glosa/avatar do governo. Serve só como referência/comparação (o `PLANO_GENERALIZACAO.md` já nota que esse projeto é ortogonal ao LSAE — ele produz saída em Libras a partir de texto, não reconhece landmarks).
- **`libras_v2/`** — pasta com `backend/`, `frontend/`, `docker-compose.yml`, README vazio. Propósito não fica claro só pela estrutura; parece uma tentativa paralela de versão web/API do sistema, não integrada ao app Tkinter atual. Vale esclarecer com o autor se está ativa.
- **`Datasets/`** — dados brutos (vídeos do V-Librasil, mais um dataset `LIBRAS-HC-RGBDS-2011` e uma pasta `test/` com imagens por letra) — matéria-prima, não código.
- **`dist/Libras_OCR/`** — build gerado do EXE (PyInstaller), contém `main.py`, `libras_recognizer.py`, `Libras_OCR.exe`, `dados_libras/`, `modelos/`, `_internal/` (dependências congeladas).

## 5. Empacotamento (EXE portátil)

`main.py` é um launcher que detecta `BASE_DIR` (funciona rodado como script ou como `.exe` congelado), seta `LIBRAS_BASE_DIR`, tenta instalar dependências faltantes, e então executa `libras_recognizer.py` via **`runpy.run_path`** — ou seja, o app real roda como **código-fonte solto ao lado do EXE**, não congelado dentro dele. Essa é a solução documentada em `EXE_PORTAVEL.md` para o erro "ordinal 380" que ocorria antes.

**Implicação técnica relevante:** como `runpy.run_path` executa o arquivo em runtime, o PyInstaller **não consegue** descobrir os imports de `libras_recognizer.py` por análise estática — por isso `Libras_OCR.spec` lista manualmente em `hiddenimports`/`collect_all`: `cv2`, `mediapipe`, `tensorflow`, `sklearn`, `numpy`, `tkinter`, `PIL`. **`scipy`** (nova dependência do LSAE, usada em `validacao_estatistica.py`) não está nessa lista — risco documentado na seção 11.

## 6. O problema que motivou o LSAE

> **Baixa capacidade de generalização entre diferentes sinalizantes.**

Com poucas execuções por sinal (~3 no V-Librasil), o modelo tem material de sobra pra aprender características de QUEM gravou (tamanho de mão, velocidade, estilo) e pouco material pra aprender o que define o sinal. Agravante: a avaliação (`train_test_split` aleatório, antes deste trabalho) misturava amostras da mesma pessoa entre treino e teste — a acurácia "medida" podia estar inflada por vazamento, não só a generalização real ruim.

## 7. LSAE — arquitetura proposta

**LSAE = Libras Semantic Augmentation Engine.** Gera dados sintéticos de treino que preservam a identidade do sinal, combinando três camadas:

| Pilar | O que faz |
|---|---|
| **1. Estatístico** | Aprende como cada sinal varia naturalmente entre execuções reais: média, desvio-padrão, trajetória, velocidade, aceleração, amplitude. |
| **2. Biomecânico** | Conhece limites físicos da mão/braço — só poses biologicamente plausíveis. |
| **3. Linguístico** | Parâmetros fonológicos da Libras (configuração de mão, orientação, movimento, localização) — não pode alterar o que define o sinal. |

**Papel explícito da IA no sistema:** nunca gera landmarks diretamente (coordenadas via texto não têm grounding biomecânico). Analisa dataset, detecta sinais confundíveis, revisa/gera código do motor. A geração numérica é sempre do motor determinístico/auditável.

### Ordem de implementação do plano original

| Fase | Conteúdo | Status |
|---|---|---|
| 0 | Split de avaliação por sinalizante + baseline honesto | ✅ Feito |
| 1 | Pilar estatístico | ✅ Feito |
| 2 | Pilar biomecânico + augmentation | ✅ Feito |
| 3 | Validação estatística (Mahalanobis/DTW) | ✅ Feito |
| 4 | Validação linguística (tolerância manual por sinal) | ⛔ Pulada deliberadamente (decisão do autor) |
| 5 | Retreinar com dataset expandido, medir no split honesto | ✅ Feito (sem a Fase 4) |
| 6 | Expor como MCP | Não iniciado |

## 8. LSAE — o que foi implementado, com resultados reais

### Fase 0 — Split honesto por sinalizante

**Arquivo:** `OCR/libras_recognizer.py`. O sistema não guardava identidade de sinalizante em lugar nenhum. Solução:

- **Público:** o CSV do `vlibrasil_converter.py` (seção 3.4) mapeia cada `.npy` ao vídeo original → Articulador1/2/3 = 3 grupos de sinalizante reais, sem esforço manual.
- **Local:** ninguém rastreava quem gravou. Adicionado campo "ID do sinalizante" na Coleta — dados novos ficam identificados, antigos caem em `local_desconhecido`.
- `GroupShuffleSplit` no lugar de `train_test_split`, com fallback sinalizado quando há só 1 grupo (caso do estático hoje).

**Bug encontrado e corrigido:** com poucos grupos (3), passar `test_size` como fração de amostras faz o `GroupShuffleSplit` arredondar (`ceil`) errado por ponto flutuante — 1ª tentativa treinou com 1/3 dos dados, testou com 2/3 (invertido). Corrigido calculando `n_test_grupos` como inteiro explícito.

**Resultado (dinâmico, split: treino Articulador1+3 = 2722 amostras / teste Articulador2 = 1364, nunca visto):**

> 🎯 **Acurácia cross-signer real: 0.44%** (chance ≈ 0.07% entre 1364 classes)

`val_loss` cresceu monotonicamente (7.2→13.4) enquanto acc de treino subia normalmente — overfitting ao sinalizante confirmado com número real.

**Estático:** 98.57%, mas com split aleatório clássico (só 1 grupo de sinalizante, `local_desconhecido`) — número **não confiável** para generalização ainda.

### Pilar 1 — `OCR/lsae/perfil_estatistico.py` (253 linhas)

Funções Python puras (numpy só). Por sinal: trajetória média/desvio (reamostrada pra 30 pontos), velocidade/aceleração (1ª/2ª diferença), amplitude, duração. Testado com dados sintéticos, depois com dado real: **1364 perfis dinâmicos + 7 estáticos**.

**Achado:** duração é degenerada (todo sinal, toda amostra, exatamente 30 frames, std=0) — tanto a coleta local quanto o importador já reamostram antes de salvar; a duração original nunca é persistida. Velocidade/amplitude continuam informativas ("Às vezes" é o mais rápido, vel=0.997; "Gay" o mais parado, vel=0.234).

### Pilar 2 — `OCR/lsae/motor_biomecanico.py` (324 linhas)

Opera no espaço de **ossos** da árvore cinemática da mão (21 landmarks, vetor pai→filho): `reescalar_dedos` (comprimento muda, ângulo preservado por construção), `jitter_articular` (direção gira pouco, comprimento preservado), `rotacionar_3d`/`escalar_isotropico` (transformação rígida, usa eixo Z de verdade — antes só x/y), `validar_biomecanica` (rede de segurança).

Validado por teste sintético (garantias matemáticas confirmadas) e em dado real ("Abacaxi": 20 gerações, 600 avaliações mão-frame → **0 descartes biomecânicos**, sem NaN/Inf).

### Fase 3 — `OCR/lsae/validacao_estatistica.py` (296 linhas)

**Achado importante:** a abordagem de livro-texto (Mahalanobis por sinal via Ledoit-Wolf) foi testada e **falhou** — com 2-3 amostras reais por sinal, nenhum estimador de covariância por sinal é confiável (simulação: amostra idêntica em distribuição à real rejeitada ~100% das vezes). Corrigido com:
1. Média por sinal (confiável mesmo com N=2-3, vem do Pilar 1).
2. Variância **pooled** entre todos os ~1364 sinais (milhares de graus de liberdade em vez de 1-2 por sinal).
3. Correção `variância × (1+1/N)` pra compensar incerteza da média com poucas amostras (sem isso, ~90% falso-positivo com N=2; com ela, ~3-4%).

DTW contra amostras reais, limiar = percentil da distância real-real.

**Resultado real:** 50 sinais × 5 variações sintéticas → **240/250 (96%) aceitas**. Controle negativo (amostra corrompida): corretamente rejeitado.

### Fase 5 — Retreino com dataset aumentado

Integração via `GerenciadorModelos._gerar_amostras_lsae` + parâmetro `augmentar_lsae`/`fator_lsae` em `treinar_dinamico`. Geração só sobre o treino pós-split (nunca toca teste). Mesmo split da Fase 0 (`random_state=42` idêntico). 5432 amostras sintéticas aprovadas para 1358 sinais, treino 2722→8154.

> 🎯 **Acurácia cross-signer com LSAE: 0.22%** — **pior** que 0.44% sem LSAE.

Treino chegou a 91% acc já na época 19 (mais rápido que 70% da Fase 0), `val_loss` cresceu ainda mais rápido (7.2→20.0). **Análise:** o motor gera variação pequena e local em torno de Articulador1/3 — nunca expõe o modelo a nada parecido com o estilo de Articulador2 (outra pessoa). Mais dados "parecidos com quem já se conhece" reforça o overfitting em vez de contrariá-lo. Split e integração foram verificados (sem vazamento) — o resultado negativo é real, não bug.

**Conclusão a discutir:** evidência quantitativa de que augmentation biomecânico/geométrico local, sem variação real de estilo entre pessoas, não resolve generalização cross-signer aqui — sustenta a necessidade de (1) mais sinalizantes reais (campo de ID existe agora) ou (2) modelos generativos capazes de extrapolar estilo, não só perturbar localmente.

## 9. QA — bugs encontrados e corrigidos

26 testes de borda (2 arquivos, cobrindo os 4 módulos) revelaram 2 bugs reais, ambos corrigidos:

1. **Treino podia abortar por completo com `augmentar_lsae=True`** se nenhum sinal do treino tivesse ≥2 amostras reais — `ValueError` não tratado. Corrigido: loga aviso, segue sem augmentation extra.
2. **`resample_sequencia` com sequência de 0 frames devolvia shape errado silenciosamente** (`np.repeat` de vazio continua vazio). Corrigido para levantar erro claro.

Depois dos fixes: 26/26 testes passam; Fase 0/3/estático re-executados contra dado real sem regressão.

## 10. Mapa de código completo

```
KONECTA/
├── README.md, TECNICO.md, IMPLEMENTACAO.md, SETUP.md   # docs — parcialmente desatualizados (ver seção 2-3)
├── EXE_PORTAVEL.md, GERAR_EXE.md                        # empacotamento
├── PLANO_GENERALIZACAO.md, README_LSAE.md                # proposta LSAE (v1.1 e pitch)
├── RESULTADOS_LSAE.md, CONTEXTO_LSAE_COMPLETO.md         # resultados/contexto só-LSAE (mais enxutos que este)
├── vlibrasil_converter.py + .csv                          # importador REAL do V-Librasil (fonte de verdade)
├── lsae_demo/, LSAE-repo/                                 # prova de conceito ANTERIOR a este trabalho (1 sinal)
├── vlibra/                                                # vendorizado — VLibras oficial, não é código do autor
├── libras_v2/                                             # web/API paralela, propósito a esclarecer
├── Datasets/                                              # dados brutos (vídeos, datasets externos)
├── dist/Libras_OCR/                                       # build do EXE
└── OCR/                                                   # app principal
    ├── libras_recognizer.py     (2300 linhas) # App Tkinter. Fase 0 (split, signer_id, campo
    │                                          # de coleta) + hook augmentar_lsae (Fase 5) aqui.
    ├── main.py                                # Launcher portátil (runpy.run_path)
    ├── Libras_OCR.spec                        # Spec PyInstaller
    ├── importar_dataset_libras*.py            # Importadores LEGADOS (ver seção 3.4)
    ├── libras_recognizer_backup*.py, *_corrigido.py, corrigir_*.py, gerar_*_corrigido.py  # artefatos de correções anteriores — confirmar se ainda servem
    ├── dados_libras/                          # dataset (350 estático local, 4086 dinâmico público + ~90 local)
    ├── lsae/                                   # PACOTE NOVO desta sessão — funções puras, testáveis isoladamente
    │   ├── perfil_estatistico.py    (253 linhas)  # Pilar 1
    │   ├── motor_biomecanico.py     (324 linhas)  # Pilar 2
    │   └── validacao_estatistica.py (296 linhas)  # Fase 3
    └── modelos/                                # modelo_estatico.pkl, modelo_dinamico.keras,
                                                  # perfil_*.pkl, variancia_pooled_*.pkl
```

### Funções/pontos de entrada centrais (LSAE)

| Função | Arquivo | O que faz |
|---|---|---|
| `GerenciadorDados._resolver_signer_id` | libras_recognizer.py | Reconstrói signer_id por amostra |
| `GerenciadorModelos._split_honesto_por_sinalizante` | libras_recognizer.py | `GroupShuffleSplit` com correção de arredondamento |
| `GerenciadorModelos._gerar_amostras_lsae` | libras_recognizer.py | Orquestra Pilares 1-3 sobre o treino pós-split |
| `calcular_perfil_dinamico`/`_estatico` | perfil_estatistico.py | Pilar 1 |
| `augmentar_sequencia`/`augmentar_pose` | motor_biomecanico.py | Pilar 2 |
| `validar_estatisticamente_dinamico` | validacao_estatistica.py | Fase 3 (Mahalanobis + DTW) |
| `estimar_variancia_pooled_dinamica` | validacao_estatistica.py | A correção central da Fase 3 |

## 11. Riscos e decisões em aberto

1. **Fase 4 (validação linguística) foi pulada deliberadamente** — tabela de tolerância manual por sinal, inviável a mão pra 1364 sinais. Pergunta: teria mudado o resultado da Fase 5? Provavelmente não resolve o problema de fundo (falta de variação de estilo), já que restringe variação em vez de expandi-la.
2. **O resultado da Fase 5 é negativo** (0.44%→0.22%) e a causa (augmentation local não substitui estilo real) não foi isolada experimentalmente — não foi testado variar só `fator_lsae` (0.5x, 1x, 4x) pra ver se o efeito é monotônico.
3. **Estático nunca foi aumentado** — funções do Pilar 2/3 funcionam em pose única, mas não há `_gerar_amostras_lsae`-equivalente pro estático, e ele não tem sinalizante identificado ainda.
4. **Performance da geração LSAE (~3min/1364 sinais)** — gargalo real é reamostragem redundante das amostras reais a cada tentativa dentro de `validar_mahalanobis_dinamico`, não o DTW. Não corrigido.
5. **Seed fixa (42)** em `_gerar_amostras_lsae` — geração determinística/idêntica entre execuções.
6. **Risco de empacotamento:** `scipy` não está em `hiddenimports` do `Libras_OCR.spec` (seção 5) — quebraria se `augmentar_lsae` for exposto na UI e o EXE regerado sem esse ajuste.
7. **Scripts/arquivos órfãos:** múltiplos importadores legados e arquivos `*_backup*`/`*_corrigido*` (seção 3.4, 10) — não confirmado se ainda são necessários.
8. **`libras_v2/` sem README preenchido** — propósito/status não está claro a partir do repositório.
9. **Duração como estatística é degenerada** (seção 8, Pilar 1) — todo o dataset dinâmico já vem reamostrado pra 30 frames antes de chegar em qualquer código deste projeto.

## 12. Estado atual da interface

- Aba **Coleta**: campo "ID do sinalizante" (opcional; vazio = `local_desconhecido`).
- Aba **Treino**: log mostra sinalizantes detectados, modo de split (honesto/fallback), acurácia rotulada como "🎯 CROSS-SIGNER" quando aplicável.
- **`augmentar_lsae` não está exposto na UI** — só acessível via chamada direta de `treinar_dinamico(..., augmentar_lsae=True, fator_lsae=2)`.

## 13. Perguntas para discutir com outras IAs

- O resultado negativo da Fase 5 é esperado dado o desenho do experimento, ou há alguma variação de augmentation biomecânico não testada que poderia ajudar mesmo sem variar estilo entre pessoas?
- Vale tentar um `fator_lsae` bem menor antes de descartar a abordagem biomecânica, ou o argumento teórico já basta?
- Com só 3 sinalizantes reais no dataset inteiro, qualquer split honesto é "leave-one-of-three-out" — isso é suficiente pra uma conclusão de TCC, ou o argumento fica mais forte só depois de coletar mais sinalizantes reais (campo de ID agora disponível)?
- A Fase 4 faria sentido popular via IA pra um subconjunto pequeno de sinais, como prova de conceito, mesmo sem cobrir os 1364 inteiros?
- Modelos generativos (VAE/Transformer pra sequências de landmarks) são viáveis no prazo do TCC, ou é melhor direcionar esforço pra expandir coleta de sinalizantes reais?
- Os scripts legados de importação e os arquivos `*_backup*`/`*_corrigido*` em `OCR/` ainda servem pra alguma coisa, ou podem ser arquivados pra limpar o repositório antes da entrega?
