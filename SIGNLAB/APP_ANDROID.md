# App de gravação no celular

Um app instalado pelo Chrome do Android (PWA) em que outra pessoa grava sinais
de Libras. Cada gravação vai para este computador, vira landmarks das mãos, e o
vídeo é apagado. Alguns minutos depois da última gravação, o SIGNLAB treina
sozinho e o KONECTA troca de modelo sem precisar reiniciar.

```
celular (app) ──HTTPS──▶ SIGNLAB ──extrai as mãos, apaga o vídeo──▶ .npy
                                  └─3 min sem gravação nova──▶ treina ──▶ .zip ──▶ KONECTA (em até 10s)
```

## Mudou no seu dia a dia

**O SIGNLAB agora pede login**, também em `localhost:8100`. Ele vai ficar
acessível pela internet, e antes qualquer um que chegasse na porta apagava
projeto. O link de admin sai do `APP_ANDROID.bat` (ou de
`python scripts\link_do_app.py`). Abra uma vez e o navegador lembra por 180 dias.

Depois de atualizar, dê **Ctrl+F5 uma vez** no admin: o navegador pode estar com
o JavaScript antigo em cache. Daqui em diante o servidor manda revalidar sempre.

## Preparar (uma vez)

1. **Tailscale no PC.** Instale em <https://tailscale.com/download/windows> e
   faça login. É o que dá ao SIGNLAB um endereço `https://…ts.net` fixo — o
   Chrome só libera a câmera em HTTPS. Se este PC for da empresa, confira antes
   se pode publicar um serviço dele na internet.
2. **Escolha o projeto** em que ela grava. Pode criar um novo no admin. Depois:

   ```
   APP_ANDROID.bat --projeto 1
   ```

   Na primeira vez o Tailscale mostra um link para habilitar o Funnel; abra,
   habilite, e rode o `.bat` de novo. O que já existe no projeto não dispara
   treino — só o que ela gravar daqui para frente.
3. **Mande para ela** o link "PARA ELA" que o `.bat` mostra, pelo WhatsApp.

Não use o projeto 3 (V-LIBRASIL): ficou fora do TCC por LGPD.

## O que ela faz

1. Abre o link no **Chrome** → digita o nome → toca em **Instalar**.
2. Escolhe um sinal (ou **+ Novo sinal**), gira o celular na horizontal e toca
   em **Gravar**: 3, 2, 1, faz o sinal, para sozinho em 4s.
3. Se as mãos não aparecerem direito, o app avisa na hora para gravar de novo.

A meta padrão é 10 gravações por sinal. Sem conexão com o PC, as gravações
ficam guardadas no celular e são enviadas sozinhas quando ele voltar.

## Cada vez que ela for gravar

O PC precisa estar ligado com o `APP_ANDROID.bat` aberto. Se não estiver, o app
abre e grava normalmente; só o envio espera.

## A atualização automática

- Treina quando as gravações param de chegar por **3 minutos**.
- Só publica se a acurácia passar de **60%**. Abaixo disso, o KONECTA fica com
  o modelo anterior e o app mostra o motivo.
- O `.zip` cai em `KONECTA_V3\models\` com projeto e data no nome. O KONECTA
  aberto troca em até 10s e avisa pela bandeja do Windows.
- A acurácia do treino automático é a do sorteio aleatório — com as mesmas
  pessoas nos dois lados. Para saber se reconhece gente nova, use o
  "Medir acurácia" do KONECTA ou o treino cross-signer do admin.

Os números ficam em `data/app.json` (criado no primeiro `--projeto`):
`meta_por_sinal`, `espera_s`, `acuracia_minima`, `modelo`, `publicar_em`.

## Segurança

Dois códigos em `data/acesso.json` (fora do git):

| | pode |
|---|---|
| admin | tudo |
| gravação (o link dela) | só gravar e criar sinais no projeto do app |

Com o link dela não se lista projeto, não se treina, não se baixa arquivo e não
se apaga nada. Se o link vazar: `APP_ANDROID.bat --novo-codigo` e mande o novo;
o antigo para de valer na hora.

O `.bat` se recusa a publicar se o SIGNLAB que está rodando não pedir senha
(uma versão antiga aberta por outro atalho, por exemplo).

## LGPD

Do vídeo, só a posição das mãos é guardada (`projects/<projeto>/sequences/*.npy`)
e o vídeo é apagado ao chegar — o rosto dela nunca fica armazenado. Ficam também
o nome que ela digitou (para separar sinalizantes no treino) e a data de cada
gravação. O app diz isso a ela na primeira tela.

Para o TCC, colha um termo de consentimento (TCLE) dela antes da coleta, dizendo
o que é guardado e para quê.

Esses `.npy` **não são cache**: são a única cópia das gravações dela. O
`BACKUP_SIGNLAB.bat` copia; nunca os exclua do backup.
