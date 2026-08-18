# KONECTA V3 — onde estamos

> Resumo de estado para retomar o trabalho sem reler o histórico.
> Última atualização: 2026-08-17.

## O reconhecimento funciona

Medido no log de hoje (19:55 → 21:27): **695 predições, 79 confirmadas**.

| Sinal confirmado | Vezes |
|---|---|
| filha | 36 |
| mae | 26 |
| pai | 16 |
| filho | 1 |

**Ressalva importante:** "confirma" não é o mesmo que "acerta". O log não sabe
qual sinal a pessoa fez de verdade. A predominância de *filha* é suspeita —
filho/filha já eram os dois piores F1 no treino (0,80 e 0,86). Para medir
acurácia real é preciso anotar o que foi sinalizado e comparar.

## Como rodar

```
C:\KONECTA\KONECTA_V3\TESTE_INTERPRETE.bat
```
Ou o atalho **KONECTA V3 - Reconhecimento** na área de trabalho.

O lançador confere ambiente, modelo, venv temporal e sobe o servidor do avatar
sozinho. Ajustes sem editar código:

```
set KONECTA_LIMIAR=0.50      (padrão 0.60; abaixe se não confirmar)
set KONECTA_HOLD_S=0.5       (padrão: automático — 0.25s se o modelo é temporal)
set KONECTA_AUDIO_ATIVO=false (desliga a escuta do áudio)
```

## Fluxo completo, ponta a ponta

```
SIGNLAB (treina)  →  Exportar .zip  →  KONECTA_V3\models\  →  TESTE_INTERPRETE.bat
```

Modelo em uso: `signlab_experimento_9.zip` — 5 sinais dinâmicos (pai, mae,
filho, filha, cachorro), BiLSTM, 92,3% de acurácia **no mesmo sinalizante**.

## Decisões de arquitetura que não são óbvias

| Decisão | Por quê |
|---|---|
| Keras/TensorFlow numa venv **separada** (`.venv-temporal`) | TF não carrega junto com PyQt5: a DLL falha e derruba o MediaPipe junto. Medido: com TF na venv principal, 0 frames processados; sem, 1315 |
| Whisper em **subprocesso** | In-process dava segmentation fault com câmera + captura ativas. Causa raiz não encontrada; o isolamento resolve |
| Predição temporal em **subprocesso** | Mesma razão do TF acima |
| `disponivel()` **não carrega modelo** | Carregar no arranque travava o encerramento do app e cegava a captura |
| Contrapressão: só o frame mais recente | Sem ela, 69 de 150 frames ficavam presos na fila e o atraso crescia sem parar |
| Hold curto para modelo temporal | A janela de 30 frames já dá estabilidade; hold longo rejeitava predições de 100% |
| `sem_maos` ≠ `acumulando` | Tratar os dois como "sem mão" reiniciava o candidato a cada 2 frames — nenhuma predição confirmava |

## Testes

**378 passando.** A suíte completa não encerra sozinha (todos passam, o
processo fica preso no fim — causa não identificada). Contorno:

```
python -m pytest tests/test_main.py -q
python -m pytest tests/ --ignore=tests/test_main.py -q
```

## Em aberto

1. **Acurácia real nunca foi medida com a intérprete.** É o próximo passo:
   anotar o sinal feito e comparar com o confirmado.
2. **Vocabulário de 5 sinais.** Ampliar é treino no SIGNLAB.
3. **Portão de rejeição do LSAE** (§ RECONHECIMENTO_RECOMENDACAO.md) — hoje o
   app sempre escolhe um dos 5, mesmo para um sinal que não conhece. Foi o que
   apareceu no teste com `sinal_editado.mp4`.
4. **Cross-signer**: 1,3–1,5% medido no V-Librasil. Se quem treina não é quem
   usa, a acurácia despenca. Coleta com mais sinalizantes é o gargalo real.
5. **Modelos não são versionados** — `models/` está no `.gitignore`. Quem
   clonar o repositório precisa exportar do SIGNLAB de novo.

## Documentos

- `ANALISE_E_PLANO_GAUNTLET.md` — diagnóstico, plano e o que foi entregue
- `RECONHECIMENTO_RECOMENDACAO.md` — por que similaridade > classificação, com medições
- `models/LEIA-ME.md` — como colocar o modelo treinado
