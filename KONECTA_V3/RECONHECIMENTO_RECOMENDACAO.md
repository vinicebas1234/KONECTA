# Reconhecimento de Libras — qual arquitetura, e por quê

> Recomendação baseada no código do KONECTA V1, no SIGNLAB, nos resultados medidos do LSAE
> e na densidade real do dataset. Nada aqui é preferência de estilo: cada escolha responde a
> um número.

---

## 1. A restrição que decide tudo

Antes de discutir modelo, o dado:

| | Valor |
|---|---|
| Classes (sinais dinâmicos) | **1.365** |
| Amostras por classe | **~6** (a maioria só do V-Librasil) |
| Sinalizantes distintos | **3** (Articulador 1, 2, 3) |
| Amostras por classe **no treino cross-signer** | **~4** (2 sinalizantes) |
| Amostras por classe no teste | ~2 (1 sinalizante nunca visto) |

E o resultado medido em `docs/RESULTADOS_LSAE.md`:

| Abordagem | Acurácia cross-signer |
|---|---|
| LSTM, split honesto por sinalizante | **0,44%** |
| LSTM + augmentation LSAE (2722 → 8154 amostras) | **0,22%** (pior) |
| Acaso, entre 1364 classes | 0,07% |

**Isto não é um problema de modelo mal ajustado.** Pedir a uma rede que separe 1.364 classes a
partir de ~4 exemplos cada, vindos de 2 pessoas, é pedir o impossível: não há informação
suficiente no dado para definir 1.364 fronteiras de decisão. O `val_loss` subindo
monotonicamente (7,2 → 13,4) enquanto a acurácia de treino sobe é exatamente esse retrato.

O experimento do LSAE já provou o ponto de forma cara e honesta: mais amostras *parecidas com
quem já se conhece* reforçam o overfitting em vez de contrariá-lo. Trocar LSTM por
Transformer, ajustar hiperparâmetro ou aumentar época não muda nada disso.

**Conclusão: o que precisa mudar não é o modelo, é a formulação do problema.**

---

## 2. A mudança de formulação

Hoje: *"classifique este vídeo entre 1.364 opções"* — precisa de muitos exemplos por classe.

Proposto: *"quão parecido é este gesto com cada sinal conhecido?"* — precisa de muitos
exemplos **no total**, não por classe.

A diferença é decisiva no seu regime de dados. Num classificador, as 6 amostras de ABACAXI só
ensinam sobre ABACAXI. Numa função de similaridade, **as 8.190 amostras do dataset inteiro
ensinam o que significa "dois gestos serem o mesmo sinal"** — e esse aprendizado se aplica a
qualquer sinal, inclusive aos que ainda não existem.

Três consequências práticas que importam para o seu projeto:

1. **Sinal novo não exige retreino.** Grava, calcula o protótipo, e ele já é reconhecível.
   Com o SIGNLAB gerando vocabulário continuamente, retreinar 1.364 classes a cada adição é
   inviável.
2. **Cross-signer vira objetivo explícito.** Treinando a métrica com pares
   *mesmo sinal, sinalizantes diferentes*, você ensina o modelo a **ignorar estilo pessoal** —
   que é precisamente onde os 0,44% falharam. Augmentation não conseguiu fazer isso porque
   nunca mostrou outra pessoa.
3. **Rejeição fica natural.** "Nenhum protótipo está perto o bastante" é uma resposta válida,
   e vale mais que um palpite errado com 90% de confiança.

---

## 3. Arquitetura recomendada

```
frame → landmarks (MediaPipe, 128 features normalizadas)   ← já existe
          ↓
     segmentação: houve gesto?                              ← barato, decide se vale seguir
          ↓
     [A] protótipos + DTW          ..... funciona HOJE, sem treinar
          ↓
     [B] embedding métrico + kNN   ..... quando houver mais sinalizantes
          ↓
     portão de rejeição LSAE (Mahalanobis + DTW)            ← já validado, 96%
          ↓
     estabilização (limiar + hold)                          ← já implementado, do V1
          ↓
     texto
```

### 3.1 Camada A — protótipos + DTW (comece por aqui)

**Não treina nada.** Compara a sequência observada com o perfil médio de cada sinal usando
DTW, que absorve diferença de velocidade de execução — justamente uma das variações entre
pessoas.

Por que isto é o próximo passo certo, e não uma etapa intermediária descartável:

- **Os artefatos já existem.** `OCR/modelos/perfil_dinamico_sinais.pkl` tem perfil calculado
  para os 1.364 sinais, sobre dado real (Pilar 1 do LSAE). Está pronto no disco.
- **É o baseline honesto que falta.** Ninguém sabe hoje quanto DTW puro entrega cross-signer.
  Se der 15%, já é **34× o LSTM**, e com custo de treino zero. Se der 2%, você aprendeu que o
  problema está na representação, não no classificador — e isso redireciona todo o resto.
- **Custo de descobrir: baixo.** Um script que roda o mesmo split honesto da Fase 0.

Eficiência: DTW contra 1.364 protótipos por consulta é caro se feito ingenuamente. Resolve-se
com filtro grosseiro antes do reranking fino — distância euclidiana entre trajetórias
reamostradas para 8 pontos elimina >95% dos candidatos em microssegundos, e o DTW roda só nos
~50 finalistas. É o padrão de recuperação em dois estágios.

### 3.2 Camada B — embedding métrico (quando houver mais sinalizantes)

Uma rede pequena (BiLSTM ou TCN) treinada com **triplet loss**, onde âncora e positivo são
**sinalizantes diferentes do mesmo sinal**. A função de perda passa a dizer explicitamente:
*"mesma pessoa não importa; mesmo sinal importa"*.

Isso só faz sentido com mais gente gravando. Com 3 sinalizantes você tem pouquíssimos pares
cross-signer para ensinar a invariância. **O campo `signer_id` que você já adicionou na coleta
é o que viabiliza isso** — é o ativo mais importante criado na Fase 0, mais até que o LSAE.

Meta realista: **10–15 sinalizantes** num vocabulário **pequeno** (30–50 sinais) vale muito
mais que 3 sinalizantes em 1.364 sinais. Nenhum sistema de Libras publicado reconhece milhares
de sinais de forma robusta; os que funcionam operam em vocabulário restrito e bem coberto.

---

## 4. Onde o LSAE entra — e onde não entra

Você pediu para usar o LSAE. Ele tem três pilares, e a evidência de vocês diz coisas
diferentes sobre cada um.

| Pilar | Evidência | Papel recomendado |
|---|---|---|
| **P1 — Perfil estatístico** | 1.364 perfis calculados sobre dado real | **Vira o protótipo da Camada A.** Deixa de alimentar treino e passa a ser a referência de comparação |
| **P2 — Augmentation biomecânico** | Retreino piorou: 0,44% → 0,22% | **Não usar para generalização cross-signer.** Continua útil para robustez a ruído de captura, não a estilo de pessoa |
| **P3 — Validação (Mahalanobis + DTW)** | 96% de aceitação, controle negativo rejeitado | **Vira o portão de rejeição em tempo de inferência** — o uso de maior valor imediato |

### O P3 é o ganho que ninguém está aproveitando

Ele foi construído para filtrar amostras sintéticas. Mas o que ele responde é:
*"esta sequência é plausível como o sinal X?"* — e essa é exatamente a pergunta que falta na
inferência.

Num produto assistivo, **errar com confiança é pior que não responder**. Se o sistema exibe
"HOSPITAL" quando a pessoa sinalizou outra coisa, o ouvinte recebe informação falsa e não tem
como saber. Com o portão do P3, casos fora da faixa viram "não reconhecido" — o interlocutor
percebe que precisa repetir.

E há um efeito colateral valioso: **isso transforma o 0,44% de acurácia em algo utilizável**.
Um sistema que acerta pouco mas cala quando não sabe é usável em um vocabulário reduzido; um
que sempre responde, não.

Vale dizer com todas as letras: o resultado negativo do P2 **não invalida o LSAE**. Ele
invalida um uso do LSAE. Os pilares 1 e 3 continuam sendo o que o projeto tem de mais sólido
em modelagem estatística, e ambos foram validados com controle negativo — coisa rara.

---

## 5. Ordem recomendada

| # | O que fazer | Custo | O que você aprende |
|---|---|---|---|
| 1 | Medir DTW+protótipos cross-signer, mesmo split da Fase 0 | Baixo | Se a representação presta. É o número que falta |
| 2 | Ligar o portão P3 na inferência do V3 | Baixo | Falso positivo vira "não reconhecido" |
| 3 | Recortar vocabulário para 30–50 sinais de uso real | Nenhum | Acurácia sobe por redução do espaço, não por truque |
| 4 | Coletar 10–15 sinalizantes nesse vocabulário | Alto (tempo) | Única rota comprovada para cross-signer |
| 5 | Treinar embedding com triplet cross-signer | Médio | Invariância a estilo, agora com dado que a sustenta |

Os passos 1 a 3 usam o que já existe. O passo 4 é o gargalo real do projeto — e é trabalho de
coleta, não de engenharia.

---

## 5.1 MEDIDO — resultado do passo 1

Experimento: `experimentos/dtw_prototipos.py`. Mesmo split honesto da Fase 0 (treino =
Articulador 1+3, teste = Articulador 2). Protótipos calculados **só com o treino** — reusar
`perfil_dinamico_sinais.pkl` teria contaminado o teste, porque ele foi computado sobre o
dataset inteiro. **Nenhum treinamento.**

### Vocabulário completo (1.364 sinais)

| Método | Acurácia cross-signer | Sobre o acaso | Treino |
|---|---|---|---|
| LSTM (Fase 0) | 0,44% | 6× | horas |
| LSTM + LSAE (Fase 5) | 0,22% | 3× | horas |
| **DTW + protótipo médio** | **1,32%** | 18× | **nenhum** |
| **DTW + vizinho mais próximo** | **1,54%** | 21× | **nenhum** |

**Comparação por similaridade entrega 3,5× a LSTM treinada, sem treinar nada, em 46 segundos.**
A premissa da recomendação se confirmou.

### A curva de vocabulário (kNN, top-1 e top-5)

| Sinais | Top-1 | Top-5 |
|---|---|---|
| 20 | **47,4%** | **78,9%** |
| 50 | 20,4% | 38,8% |
| 200 | 7,6% | 21,2% |
| 1.364 | 1,5% | — |

### Duas descobertas dentro do experimento

**1. Média entre sinalizantes destrói o template.** Usar cada amostra como referência própria
(kNN) em vez da média bate a média em toda a faixa: 31,6% → 47,4% em 20 sinais. Faz sentido —
a média entre dois estilos de execução pode não se parecer com nenhum dos dois.

**2. O filtro grosseiro estava cortando a resposta certa.** Na primeira medição do vocabulário
completo, kNN parecia *pior* que a média (1,03% contra 1,32%). Era artefato: com kNN há o
dobro de referências, mas o corte para 50 candidatos continuava fixo — proporcionalmente muito
mais agressivo. Com 200 candidatos, kNN passa para 1,54%. Custo: 92ms por consulta em vez de
36ms.

### O que estes números dizem

- **A informação está na representação; o ranqueamento é que é fraco.** Em 20 sinais, o sinal
  certo está entre os 5 primeiros em 79% dos casos, mas em primeiro em apenas 47%. Isso é
  exatamente o que uma métrica aprendida (Camada B) existe para corrigir — e agora há
  evidência de que há sinal a extrair, em vez de aposta.
- **Nem 47% em 20 sinais é produto.** Numa conversa, errar uma palavra em duas inviabiliza.
- **O gargalo é coleta, agora medido e não afirmado.** Nenhuma escolha de método sobreviveu a
  2 amostras por classe vindas de 2 pessoas. Foi assim com LSTM, com augmentation, com
  protótipo e com kNN.

## 6. O que eu não sei

- **Se DTW+protótipos vai bem.** Nunca foi medido cross-signer. Pode dar 15% ou 2%. A
  recomendação é medir primeiro justamente porque é barato e nenhuma decisão posterior faz
  sentido sem esse número.
- **Qual vocabulário importa.** Quais 30–50 sinais cobrem o uso real é decisão de quem
  convive com a necessidade, não minha.
- **Se o P3 calibra bem em tempo real.** Foi validado sobre sequências completas de dataset,
  não sobre janela deslizante de câmera ao vivo. O limiar provavelmente precisa recalibrar.

---

## 7. Resumo em três frases

O gargalo não é o modelo, é ter 1.364 classes com 4 amostras de 2 pessoas — e o experimento
do LSAE já provou isso com número. Trocar classificação por similaridade faz o dataset inteiro
ensinar cada sinal, permite adicionar vocabulário sem retreinar e ataca cross-signer
diretamente. Do LSAE, aproveite o P1 como protótipo e o P3 como portão de rejeição — e aceite
o resultado do P2 como o que ele é: uma pergunta bem feita cuja resposta foi não.
