# Texto para Libras

O avatar 3D do VLibras faz o sinal do que você digita — ou do que estiver
tocando no computador (call do Teams/Meet, vídeo, qualquer áudio).

```
áudio do PC ─loopback→ Whisper ─POST /publicar─┐
                                                ├→ servidor ─WS→ avatar 3D
caixa de texto ────────────────────────────────┘
Python externo ──────────WebSocket─────────────┘
```

## Rodar

```bash
python app.py
```

Abre a janela com a caixa de texto e o avatar. **A escuta do áudio começa
sozinha, sem clicar em nada.** O áudio continua saindo normal pelas caixas —
a captura é loopback, não intercepta nada.

Duas esperas na primeira vez: o avatar (~15s) e o modelo de voz (baixa ~500MB).
O rodapé mostra o estado da escuta.

## De onde o texto pode vir

**Áudio do PC** — automático, é o `transcricao_tempo_real.py` (código do
Guilherme/Konecta). Só as frases fechadas viram sinal; as parciais são
ignoradas para não cortar a animação no meio.

**Caixa de texto** — digite e Enter.

**Outro código Python:**

```python
from cliente import AvatarVLibras

avatar = AvatarVLibras()
await avatar.falar("amor")
```

**HTTP** (mesmo contrato do serviço central do Konecta):

```bash
curl -X POST http://127.0.0.1:8300/publicar -H "Content-Type: application/json" \
  -d "{\"origem\":\"audio\",\"tipo\":\"final\",\"texto\":\"bom dia\"}"
```

## Arquivos

| Arquivo | O que é |
|---|---|
| `app.py` | O app desktop. É o que você roda |
| `server.py` | Serve a página, recebe `/publicar`, distribui por WebSocket |
| `transcricao_tempo_real.py` | Captura o áudio do PC e transcreve (faster-whisper + VAD) |
| `static/` | A página com o avatar VLibras |
| `cliente.py` | Para outro código Python mandar texto |

## Notas

- Precisa de internet: a tradução para Libras é a API oficial do VLibras
  (`traducao2.vlibras.gov.br`) e o avatar vem de `vlibras.gov.br`.
  A transcrição do áudio, essa sim, roda 100% local.
- Sem GPU NVIDIA nesta máquina, então `DEVICE = "cpu"` / `int8` no
  `transcricao_tempo_real.py`. Se a transcrição ficar lenta, troque
  `MODELO_WHISPER` de `"small"` para `"base"`.
- `PARCIAIS_ATIVAS = False`: as transcrições parciais alimentam a legenda ao
  vivo do terminal, que aqui ninguém lê, e rodam no mesmo laço que lê os frames
  — enquanto uma roda, o fim da fala demora mais para ser detectado. Desligá-las
  derrubou o pior caso de 4,3s para 1,8s. Ligue de volta se quiser a legenda
  incremental no terminal.
- Porta 8300 (SIGNLAB usa 8100, KONECTA_V2 usa 8000/5173).
