# Vocabulário VLibras — proveniência

Lista de nomes de sinais do dicionário oficial do VLibras. Serve como **espaço
de rótulos** do reconhecimento: se as classes do modelo usarem esta mesma
nomenclatura, a saída do reconhecedor (`pessoa sinalizando → glosa`) alimenta
direto o avatar (`glosa → sinal`), e as duas pontas do KONECTA se encaixam sem
tabela de tradução no meio.

## Arquivo

| | |
|---|---|
| Arquivo | `vlibras_bundles.json` |
| Origem | `GET https://dicionario2.vlibras.gov.br/bundles` |
| Baixado em | 2026-08-12 |
| Tamanho | 342.750 bytes |
| SHA-256 | `98b38399b218816245c6ac051ab21c2f16cd3912850f91229a60d4d6bf43e8d0` |
| Formato | JSON: lista plana de strings, sem aninhamento |
| Entradas | 24.213, sem duplicatas |

O endpoint responde sem autenticação. A URL foi lida do próprio bundle do
widget (`vlibras-plugin.chunk.js`, módulo `9517`), junto de `DICTIONARY_URL` e
`REVIEW_URL` — não é uma API privada descoberta por tentativa.

**O arquivo está aqui exatamente como foi servido**, sem reordenar nem
normalizar. Qualquer transformação deve gerar um arquivo derivado ao lado, para
que este continue conferindo com o SHA-256 acima.

## O que tem dentro

Só os **nomes** dos sinais. A animação de cada sinal é um Unity AssetBundle
separado (`.../2018.3.1/WEBGL/BR/<NOME>`), com curvas de quaternion para o rig
do avatar — não é vídeo nem landmark de pessoa real, e por isso **não serve
como dado de treino para reconhecimento**. O valor desta lista é ser o
vocabulário, não o dataset.

Composição:

| Padrão | Qtd. | Exemplo |
|---|---|---|
| Total | 24.213 | `AZUL` |
| Desambiguação com `&` | 3.251 | `ABA&INFORMÁTICA`, `ABAETETUBA&CIDADE` |
| Compostos com `_` | 3.617 | `1_HORA`, `0_QUILÔMETRO` |
| Verbos direcionais | 368 | `1P_AJUDAR_2S` (1ª pessoa → 2ª pessoa singular) |
| Caracteres isolados | 38 | `A`, `B`, `0`, `%` |
| Com acento | 7.076 | `ABRANGÊNCIA` |

Três coisas que afetam o desenho das classes:

1. **`&` separa homônimos.** `ABA&INFORMÁTICA` e uma `ABA` de roupa são sinais
   diferentes para a mesma palavra escrita. Rótulo é o nome inteiro, com o `&`.
2. **Verbos direcionais mudam de forma conforme quem faz e quem recebe.**
   `1P_AJUDAR_2S` e `1P_AJUDAR_3P` são classes distintas, não flexões de uma só.
3. **Acentos fazem parte do nome.** Normalizar para ASCII quebra o casamento com
   o dicionário — cuidado com `unicodedata.normalize` no pipeline de rótulos.

## Licença e uso

O código do portal VLibras é **LGPL-3.0** (`github.com/spbgovbr-vlibras/vlibras-portal`).
Para os dados do dicionário não localizei declaração explícita de licença.

Esta lista é uma enumeração factual de nomes de sinais, servida publicamente por
um serviço do governo federal, e está aqui apenas como referência de vocabulário.
Ainda assim, **antes de publicar o TCC, confirme os termos com a equipe do
VLibras** e cite a fonte com a data e o hash acima.

## Como atualizar

O dicionário muda com o tempo. Para pegar uma versão nova:

```bash
curl -sS -o OCR/vocabulario/vlibras_bundles.json \
  https://dicionario2.vlibras.gov.br/bundles
sha256sum OCR/vocabulario/vlibras_bundles.json   # atualize a tabela acima
```

É **uma** requisição, de ~340 KB. Não faça isso em laço, e não baixe os 24 mil
bundles de animação em rajada: é servidor público, e o custo da varredura
recai sobre um serviço de acessibilidade que outras pessoas dependem.

## Recursos relacionados (não baixados)

| Endpoint | O que é |
|---|---|
| `dicionario2.vlibras.gov.br/static/TREES/2018.3.1.json` | Árvore de prefixos para busca incremental (~3,4 MB) |
| `dicionario2.vlibras.gov.br/2018.3.1/WEBGL/BR/<SINAL>` | AssetBundle da animação, um por sinal |
| `traducao2.vlibras.gov.br/translate` | `POST {text, domain}` → glosa em texto puro |
