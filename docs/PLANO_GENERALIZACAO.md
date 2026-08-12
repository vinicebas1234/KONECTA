# Libras Semantic Augmentation Engine (LSAE) — Arquitetura + Plano de Implementação

> **Versão:** 1.1 (revisão técnica sobre a v1.0)
> **Projeto:** KONECTA — Reconhecimento Inteligente de Libras
> **Autor:** Vinicius Rosa Santos
> **Revisão:** correções de viabilidade, métricas concretas e ordem de implementação para escopo de TCC

Este documento parte da arquitetura LSAE (v1.0) e incorpora as correções discutidas: onde o texto original descreve um passo como se fosse simples mas esconde o problema mais difícil do sistema, como transformar cada validação em algo mensurável, e em que ordem implementar sem perder tempo em partes que ainda não têm motor por trás.

---

## Visão Geral

O **LSAE** é um mecanismo de geração de dados sintéticos para treinamento de modelos de reconhecimento de Libras, criado para resolver o principal problema observado no KONECTA hoje:

> **Baixa capacidade de generalização entre diferentes pessoas.**

Com ~4086 vídeos e ~3 execuções por sinal, o modelo aprende características do sinalizante que gravou (tamanho da mão, comprimento dos dedos, velocidade, ângulo/distância de câmera, estilo individual) em vez do conceito do sinal. Resultado: quem gravou é reconhecido; outra pessoa executando o mesmo sinal, não.

O LSAE ataca isso combinando três camadas — estatística, biomecânica e linguística — para gerar variações sintéticas que preservem a identidade do sinal.

---

## Diagnóstico (por que isso acontece)

```
Pessoa A grava → Modelo aprende → Pessoa A reconhece, Pessoa B falha
```

Causas: poucas amostras por sinal, pouca diversidade entre sinalizantes, overfitting a características individuais.

**Ponto adicional, não presente na v1.0:** a avaliação atual do modelo (`train_test_split` aleatório em `libras_recognizer.py`) separa por amostra, não por pessoa. Isso significa que, mesmo hoje, a acurácia medida pode estar inflada por vazamento entre treino e teste — o modelo pode estar sendo "testado" com variações da mesma pessoa que já viu no treino. **Sem corrigir isso primeiro, nenhuma melhoria do LSAE é mensurável.** Este é o pré-requisito de todo o resto (ver Fase 0 abaixo).

---

## Filosofia do LSAE

> Um sinal não é definido pelas coordenadas exatas dos landmarks — é definido pelos seus parâmetros linguísticos.

"CASA" continua sendo "CASA" independente de altura da pessoa, tamanho da mão, distância da câmera, leve inclinação de corpo ou velocidade de execução. O modelo deve aprender o conceito, não a coordenada.

---

## Arquitetura

```
Vídeo → MediaPipe → Landmarks Reais → Normalização → LSAE
  → Validação Biomecânica → Validação Linguística
  → Landmarks Sintéticos → Treinamento → Modelo Final
```

## Os 3 pilares

### Pilar 1 — Conhecimento Estatístico
Aprende como cada sinal varia naturalmente: posição média, desvio padrão, amplitude, trajetória, velocidade, aceleração, tempo. Aprende a distribuição do movimento, não copia vídeos.

### Pilar 2 — Conhecimento Biomecânico
Conhece limitações físicas da mão/braço: não permite dedos atravessando a mão, rotações impossíveis, punhos invertidos, movimentos incompatíveis com a anatomia. Só gera poses biologicamente plausíveis.

### Pilar 3 — Conhecimento Linguístico
Entende os parâmetros fonológicos da Libras: configuração de mão, orientação, movimento, localização, expressões não-manuais. O sistema pode alterar inclinação de braço, distância de câmera, tamanho de mão, velocidade — mas não pode alterar configuração principal da mão, direção obrigatória do movimento, ou ponto de articulação.

---

## Pipeline de Geração

| Etapa | O que faz | Status na v1.0 | Correção / concretização |
|---|---|---|---|
| 1. Extração | Vídeo → MediaPipe → Landmarks | Já implementado | — |
| 2. Análise estatística | Calcula média, variância, velocidade, aceleração, trajetória, amplitude, distribuição espacial por sinal | A implementar (Pilar 1) | Direto de implementar sobre os dados já coletados |
| 3. Modelo semântico | Representação abstrata do sinal (config. de mão, movimento, orientação, localização, expressões) | A implementar | Ver "Concretização do Pilar 3" abaixo — precisa virar dado estruturado, não só conceito |
| 4. Motor biomecânico | Gera variações: tamanho de mão, comprimento de dedos, rotação 3D, posição de câmera, velocidade, suavização, distância | A implementar (núcleo do sistema) | É a parte com maior retorno imediato — ver Fase 2 |
| 5. Validação linguística | "Ainda representa o mesmo sinal? Mudou config./orientação/movimento/ponto de articulação/significado?" | **Descrita como checklist, mas não é uma pergunta respondível automaticamente sem estrutura por trás** | Ver "Concretização da Etapa 5" abaixo — é o ponto mais crítico do documento |
| 6. Validação estatística | Descarta se a amostra estiver muito distante da distribuição real | Descrita sem métrica definida | Ver "Concretização da Etapa 6" abaixo |
| 7. Inclusão no dataset | Só amostras aprovadas entram no treino | — | Adicionar: nunca incluir sintético no conjunto de teste (só no treino) |

### Concretização da Etapa 5 (Validação Linguística)

Este é o ponto onde a v1.0 é mais otimista do que o problema permite. Não existe um oráculo genérico capaz de responder "isso ainda significa CASA?" a partir de landmarks — isso seria, de novo, uma forma de pedir para um modelo "adivinhar" semântica sem grounding. A forma implementável é diferente: **na hora em que o sinal é cadastrado (etapa de ensino), você define manualmente, por sinal, a faixa de tolerância de cada parâmetro** — por exemplo, "a distância entre a ponta do polegar e a ponta do indicador não pode variar mais que X% do valor de referência", "o ponto de articulação (centro da mão) não pode sair de uma região delimitada em torno do rosto/peito". A validação linguística então vira uma checagem de regras contra essas faixas — determinística e testável — não um julgamento semântico aberto.

Isso é mais trabalho manual inicial (definir a faixa por sinal), mas é o que torna a etapa 5 real em vez de aspiracional.

### Concretização da Etapa 6 (Validação Estatística)

"Muito distante da distribuição real" precisa de uma métrica concreta. Candidatas diretamente implementáveis com o que você já tem:
- **Distância de Mahalanobis** da amostra sintética em relação à média/covariância das amostras reais daquele sinal — descarta outliers estatísticos.
- **Distância DTW** entre a sequência sintética e as sequências reais mais próximas, descartando se ultrapassar um percentil (ex. p90) das distâncias observadas entre as próprias amostras reais do sinal.

---

## Técnicas de Augmentation (mapeadas para implementação)

| Categoria | Técnicas | Observação |
|---|---|---|
| Geométricas | rotação 3D, escala, translação, perspectiva, zoom | usar o eixo `z` do MediaPipe (hoje só x/y são manipulados no augmentation atual) |
| Temporais | velocidade, aceleração, interpolação, compressão temporal | já existe uma versão (`_variacao_temporal`); manter consistência entre o que é usado em treino vs. em inferência real |
| Anatômicas | comprimento dos dedos, largura da mão, tamanho da palma, comprimento do braço | reescala por segmento ("osso"), não escala isotrópica — preserva ângulo das articulações |
| Cinemáticas | pequenas rotações articulares, suavização, jitter controlado | perturbar em espaço de ângulo articular e reconstruir xyz (cinemática direta), evita poses anatomicamente impossíveis por construção |
| Estatísticas | MixUp, interpolação, amostragem da distribuição | interpolar entre as 3 execuções reais existentes por sinal — parte de dado real, não de ruído puro |

---

## Papel da IA (Claude / LLM)

A IA **não gera landmarks diretamente** — geração numérica de coordenadas a partir de texto não tem grounding biomecânico e equivale a alucinar números. Isso é consistente com a regra original do projeto ("a IA nunca deve inventar landmarks").

O papel real da IA no LSAE:
- analisar o dataset e detectar sinais confundíveis;
- sugerir quais variações priorizar por sinal;
- identificar sinais com sinais de overfitting (baixa diversidade nas amostras);
- gerar/revisar o código do motor de augmentation;
- produzir relatórios (matriz de similaridade, qualidade de dataset).

A geração numérica em si permanece 100% sob responsabilidade do motor estatístico/biomecânico — determinístico e auditável.

---

## Módulo MCP

O LSAE pode expor um MCP próprio com ferramentas como `validate_sign()`, `generate_variations()`, `compare_signs()`, `calculate_similarity()`, `semantic_validation()`, `biomechanical_validation()`, `generate_dataset()`, `quality_report()`, `confusion_analysis()`.

**Nota sobre integração externa:** o repositório `librascript-mcp` (fabricioartur), que você tinha cogitado usar aqui, **não serve para esse papel** — ele traduz texto em português para glosa/roteiro de Libras via APIs do VLibras (produção de conteúdo para o avatar Ícaro), não lida com landmarks nem geração biomecânica. É um projeto ortogonal ao LSAE. Ele poderia, no máximo, servir num papel secundário de validação de vocabulário (`lookup_sign`, `dictionary_stats` contra o dicionário oficial), ou como peça separada caso o KONECTA um dia também produza saída em Libras (texto → sinal), mas não substitui nem parte do motor do LSAE.

**Recomendação de escopo:** implemente o motor do LSAE como funções Python testáveis primeiro; exponha como MCP só depois que o motor estiver validado empiricamente. Construir a camada MCP antes de ter geração real por trás é gastar tempo de integração num sistema sem conteúdo.

---

## Fase 0 — Pré-requisito (fora da v1.0, adicionado aqui)

Corrigir o `train_test_split` em `libras_recognizer.py` para separar por **sinalizante** (`GroupShuffleSplit` por `signer_id`), não por amostra aleatória. Sem isso, não há como medir se o LSAE de fato melhora generalização entre pessoas ou apenas parece melhorar por vazamento de dados. Rodar o baseline atual nesse split honesto e registrar o número real antes de qualquer mudança — essa é a linha de base do TCC.

---

## Ordem de Implementação Recomendada

| Fase | Conteúdo | Depende de | Entrega mensurável |
|---|---|---|---|
| 0 | Split de avaliação por sinalizante + baseline honesto | — | Número real de acurácia cross-signer hoje |
| 1 | Pilar 1 (estatístico): calcular média/variância/trajetória por sinal a partir dos dados existentes | Fase 0 | Modelo semântico básico por sinal (Etapa 2–3) |
| 2 | Pilar 2 (biomecânico) + técnicas geométricas/anatômicas/cinemáticas: motor de augmentation | Fase 1 | Geração sintética funcional (Etapa 4) |
| 3 | Etapa 6 concretizada (Mahalanobis ou DTW contra distribuição real) | Fase 2 | Filtro estatístico funcionando |
| 4 | Etapa 5 concretizada (tabela de faixas por sinal, definida manualmente ao cadastrar cada sinal) | Fase 1 (usa o modelo semântico) | Filtro linguístico funcionando |
| 5 | Retreinar com dataset expandido, medir no split da Fase 0 | Fases 0–4 | Evidência empírica de ganho (ou não) de generalização — resultado central do TCC |
| 6 (opcional) | Expor como MCP (`validate_sign`, `generate_variations`, etc.) | Fase 5 validada | Narrativa arquitetural / escalabilidade |

**Fora do caminho crítico:** geração via LLM direto (não recomendada), modelos generativos tipo VAE/Diffusion/Transformer (corretamente colocados em trabalhos futuros — pesados demais para o prazo de TCC), suporte à posição relativa entre as duas mãos e pose/rosto completos (também trabalhos futuros, mas vale registrar que "duas mãos" já está parcialmente implementado hoje — `MP_MAX_HANDS=2` — o que falta é a posição *relativa* entre elas, hoje perdida porque cada mão é normalizada independentemente).

---

## Benefícios Esperados

Aumento de generalização entre sinalizantes, redução de overfitting, menor necessidade de gravação de novos vídeos, maior robustez para diferentes usuários, treinamento mais eficiente, base para pesquisas futuras em reconhecimento automático de Libras.

**Nota de rigor:** qualquer percentual de ganho deve ser tratado como hipótese até ser medido no split por sinalizante (Fase 0). Não reportar números de acurácia no TCC sem essa validação.

---

## Trabalhos Futuros

- Posição relativa entre as duas mãos (não normalizar cada mão isoladamente);
- expressões faciais via MediaPipe Face Mesh;
- pose corporal completa (MediaPipe Pose);
- geração baseada em modelos generativos (VAE, Diffusion ou Transformers para sequências de landmarks);
- adaptação para dialetos regionais da Libras;
- aprendizado contínuo com novos usuários;
- integração com modelos multimodais de visão computacional.

---

## Diferencial Científico

O LSAE une três áreas normalmente tratadas isoladamente: visão computacional (extração/manipulação de landmarks), biomecânica (variações fisicamente plausíveis) e linguística da Libras (preservação dos parâmetros fonológicos e identidade semântica). Vai além do augmentation tradicional ao propor coerência simultânea estatística, anatômica e linguística — desde que a validação linguística e estatística sejam implementadas como regras concretas e mensuráveis (Fases 3 e 4), e o ganho seja demonstrado empiricamente contra uma avaliação honesta por sinalizante (Fase 0), não apenas descrito conceitualmente.
