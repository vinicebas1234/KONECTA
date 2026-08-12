# 🤟 LSAE — Libras Semantic Augmentation Engine

> Um mecanismo de geração de dados sintéticos que preserva **identidade linguística**, **plausibilidade biomecânica** e **coerência estatística** para treinar modelos de reconhecimento de Libras com poucos dados.

**Projeto:** KONECTA — Reconhecimento Inteligente de Libras
**Autor:** Vinicius Rosa Santos
**Status:** proposta arquitetural / em desenvolvimento (TCC)

---

## O problema

Sistemas de reconhecimento de Libras por visão computacional costumam sofrer do mesmo sintoma: funcionam bem para a pessoa que gravou o dataset, e falham quando outra pessoa executa exatamente o mesmo sinal.

```
Pessoa A grava → modelo aprende → Pessoa A é reconhecida, Pessoa B falha
```

A causa não é falta de esforço no treino — é que, com poucas execuções por sinal, o modelo tem material de sobra para aprender características do sinalizante (tamanho da mão, comprimento dos dedos, velocidade, ângulo e distância da câmera, estilo pessoal) e pouco material para aprender o que de fato define o sinal. É overfitting ao sinalizante, não ao vocabulário.

No caso do KONECTA, isso acontece com ~4.086 vídeos e apenas ~3 execuções por sinal — volume razoável de vocabulário, mas baixíssima diversidade de sinalizantes por sinal.

Gravar mais vídeos ajudaria, mas escala mal: expandir para uma diversidade real de corpos, alturas e estilos exigiria filmar centenas de intérpretes diferentes para cada sinal.

## A ideia central

> Um sinal não é definido pelas coordenadas exatas dos landmarks — é definido pelos seus parâmetros linguísticos.

"CASA" continua sendo "CASA" independentemente da altura da pessoa, do tamanho da mão, da distância da câmera, de uma leve inclinação do corpo ou de uma execução mais lenta. O LSAE parte desse princípio para gerar variações sintéticas plausíveis de cada sinal, em vez de depender só de gravar mais vídeos.

## Os 3 pilares

**Estatístico** — aprende como cada sinal varia naturalmente no próprio dataset (posição média, desvio padrão, amplitude, trajetória, velocidade, aceleração), em vez de tratar cada vídeo como um ponto isolado.

**Biomecânico** — conhece os limites físicos da mão e do braço. Não gera dedos atravessando a palma, rotações de punho impossíveis ou movimentos incompatíveis com a anatomia humana — só variações biologicamente plausíveis.

**Linguístico** — entende os parâmetros fonológicos da Libras (configuração de mão, orientação, movimento, localização, expressões não-manuais). Pode alterar inclinação de braço, distância de câmera, tamanho de mão e velocidade; não pode alterar a configuração principal da mão, a direção obrigatória do movimento ou o ponto de articulação — o que descaracterizaria o sinal.

## Arquitetura

```
Vídeo → MediaPipe → Landmarks Reais → Normalização
   → Motor LSAE (estatístico + biomecânico)
   → Validação Biomecânica → Validação Linguística → Validação Estatística
   → Landmarks Sintéticos Aprovados
   → Treinamento → Modelo
```

O ponto central da arquitetura: nenhuma amostra sintética entra no dataset sem passar pelas três validações. O motor gera livremente dentro do espaço biomecânico plausível; as validações é que restringem esse espaço ao que ainda é, linguística e estatisticamente, o mesmo sinal.

## Técnicas de augmentation

| Categoria | Técnicas |
|---|---|
| Geométricas | rotação 3D, escala, translação, perspectiva |
| Temporais | variação de velocidade/aceleração, interpolação, compressão temporal |
| Anatômicas | reescala por segmento ósseo (dedo, palma, braço) — preserva ângulos articulares em vez de escalar tudo isotropicamente |
| Cinemáticas | perturbação em espaço de ângulo articular + reconstrução por cinemática direta, jitter controlado |
| Estatísticas | MixUp e interpolação entre execuções reais existentes do mesmo sinal, amostragem da distribuição aprendida |

## Como a validação funciona na prática

A parte mais fácil de subestimar nesse tipo de sistema é a validação linguística — "isso ainda representa o mesmo sinal?" não é uma pergunta que um classificador genérico responde bem sem estrutura por trás. A abordagem do LSAE é tornar isso determinístico: ao cadastrar um sinal, definem-se faixas de tolerância por parâmetro (ex.: a distância entre pontas de dedos não pode variar além de X% do valor de referência; o ponto de articulação não pode sair de uma região delimitada do corpo). A validação linguística vira checagem de regras contra essas faixas — auditável, não um julgamento semântico opaco.

A validação estatística usa distância de Mahalanobis (contra a distribuição real do sinal) ou distância DTW (contra as execuções reais mais próximas), descartando amostras que se afastam demais do que já foi observado.

## Papel da IA no sistema

O LSAE não usa um LLM para gerar landmarks diretamente — coordenadas geradas por texto não têm grounding biomecânico e equivaleriam a alucinar números. A IA entra como camada de apoio: analisar o dataset, detectar sinais confundíveis entre si, sugerir quais variações priorizar, gerar/revisar código do motor de augmentation e produzir relatórios de qualidade. A geração numérica em si é sempre responsabilidade do motor estatístico/biomecânico, determinístico e auditável.

## Diferencial científico

A maioria das soluções de aumento de dados para reconhecimento de gestos aplica transformações geométricas genéricas (rotação, ruído, espelhamento) sem qualquer noção do que o gesto significa. O LSAE propõe unir três áreas normalmente tratadas isoladamente — visão computacional, biomecânica e linguística da Libras — para que cada amostra sintética seja simultaneamente plausível fisicamente e correta linguisticamente, não apenas estatisticamente diversa.

## Trabalhos futuros

- Posição relativa entre as duas mãos (hoje cada mão é normalizada independentemente);
- expressões faciais via MediaPipe Face Mesh;
- pose corporal completa via MediaPipe Pose;
- geração via modelos generativos (VAE, Diffusion ou Transformers) para sequências de landmarks;
- adaptação a variações regionais da Libras;
- aprendizado contínuo com novos usuários.

## Nota de rigor

Esta é uma proposta arquitetural em desenvolvimento como parte de um Trabalho de Conclusão de Curso. Qualquer ganho de acurácia relatado deve ser validado com uma avaliação que separa treino e teste por sinalizante (não por amostra aleatória) — é a única forma de medir generalização real entre pessoas diferentes, em vez de desempenho inflado por vazamento de dados entre conjuntos de treino e teste da mesma pessoa.

---

## Sobre o projeto KONECTA

O LSAE é um componente do **KONECTA**, projeto de TCC de reconhecimento de sinais em Libras por visão computacional (Python, OpenCV, MediaPipe, TensorFlow), com foco em acessibilidade e inclusão digital.

**Autor:** Vinicius Rosa Santos
**GitHub:** [vinicebas1234](https://github.com/vinicebas1234)

## Licença

Conteúdo de finalidade acadêmica e educacional.
