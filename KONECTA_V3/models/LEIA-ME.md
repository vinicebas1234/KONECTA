# models/ — onde colocar o que sai do SIGNLAB

Largue aqui o arquivo do experimento treinado. O app encontra sozinho ao abrir:
não precisa editar configuração nem definir variável de ambiente.

## O caminho normal

1. Treine o experimento no SIGNLAB.
2. Exporte (`Exportar` na tela do experimento) — baixa `signlab_experimento_N.zip`.
3. Copie o `.zip` para esta pasta.
4. Abra o KONECTA V3.

No log aparece qual foi carregado:

```
Modelo do SIGNLAB encontrado em models/: signlab_experimento_7.zip
Modelo SIGNLAB carregado: signlab_experimento_7.zip (12 sinais, temporal)
```

## Formatos aceitos

| Arquivo | Origem | Reconhece |
|---|---|---|
| `exp_N.zip` | botão Exportar | estático ou temporal, conforme o experimento |
| `exp_N.joblib` | `SIGNLAB/projects/<projeto>/models/` | estático (por frame) |
| `exp_N.keras` | idem, junto com `exp_N.meta.json` | temporal (por sequência) |
| pasta descompactada | zip extraído | ambos |

**Prefira o `.zip`.** Ele carrega o `metadata.json` junto — classes, métricas e
configuração de features. O `.keras` cru depende do `exp_N.meta.json` estar ao
lado; sem ele, o app não sabe o nome das classes e recusa carregar em vez de
exibir números.

## Qual arquivo é escolhido

Havendo mais de um, vence o `.zip` mais recente. Treinar de novo e copiar o novo
arquivo passa a valer sem precisar apagar o anterior — útil para voltar atrás
rapidamente.

Para forçar um específico, sem mexer na pasta:

```
set KONECTA_MODELO_SIGNLAB=C:\caminho\para\exp_3.zip
```

## Modelos temporais precisam de uma venv SEPARADA

Sinais dinâmicos (`.keras`) exigem Keras/TensorFlow — mas **o TensorFlow não
pode estar na venv do app**. Medido nesta máquina: com TF instalado ao lado do
PyQt5, o MediaPipe falha ao carregar (`DLL load failed while importing
_pywrap_tensorflow_internal`) e o app processa **0 frames**; sem TF, processa
**1315 em 45s**. O MediaPipe importa TF sozinho quando o pacote existe, então
nem adianta não usar.

Por isso o Keras roda num processo à parte, com interpretador próprio:

```
python -m venv .venv-temporal
.venv-temporal\Scripts\pip install keras tensorflow-cpu numpy
```

O app encontra essa venv sozinho. Sem ela, modelos estáticos continuam
funcionando normalmente e os temporais avisam no log.

**Nunca instale `tensorflow` ou `keras` na `.venv` principal** — quebra o
reconhecimento inteiro, inclusive o estático.

## Esta pasta não vai para o git

Modelos são binários grandes e mudam a cada treino. O `.gitignore` do projeto
ignora o conteúdo daqui — só este LEIA-ME é versionado.
