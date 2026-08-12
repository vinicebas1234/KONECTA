const alvo = document.getElementById("texto");
const status = document.getElementById("status");

// Fala chega mais rápido do que o avatar sinaliza. Sem fila, cada frase nova
// cortava a anterior no meio; com fila sem limite, o avatar iria ficando cada
// vez mais atrasado em relação ao áudio. Guardamos poucas e descartamos as
// mais antigas — numa legenda ao vivo o que importa é o que está sendo dito
// agora.
const MAX_FILA = 5;

const fila = [];
let plugin = null;
let consumindo = false;

function definirStatus(texto, classe) {
  status.textContent = texto;
  status.className = classe;
}

// O widget só instancia o player (window.plugin) depois de aberto, e só passa a
// responder ao clique após seu próprio window.onload — daí a retentativa.
function aguardarPlugin() {
  return new Promise((resolve) => {
    const checar = () => {
      if (window.plugin?.translate) return resolve(window.plugin);
      document.querySelector("[vw-access-button]")?.click();
      setTimeout(checar, 1000);
    };
    checar();
  });
}

// O player não avisa quando termina de sinalizar: rastreando todos os eventos,
// todos disparam junto no instante do translate() (o gloss:end de 0s é o fim da
// frase ANTERIOR, que o novo translate interrompeu) e nada mais chega depois.
// player.status também não serve — trava em "playing" e nunca volta a "idle".
// Então estimamos a duração pelo tamanho da frase. Se o avatar cortar frases
// longas ou ficar parado à toa entre elas, ajuste MS_POR_PALAVRA.
const MS_ATE_COMECAR = 1200; // round-trip da API de tradução antes de sinalizar
const MS_POR_PALAVRA = 1700; // medido a 1x
const MS_MIN = 3000;
const MS_MAX = 20000;

// 1 / 1.5 / 2. Em áudio contínuo a fala sempre corre mais rápido que a Libras,
// então acelerar o avatar reduz o atraso e o descarte da fila — ao custo de
// legibilidade. 1.5 é o meio-termo; quem decide de verdade é quem lê os sinais.
const VELOCIDADE = 1.5;

function duracaoEstimada(texto) {
  const palavras = texto.trim().split(/\s+/).length;
  // só a parte animada escala com a velocidade; o preparo dos sinais não.
  const estimada = MS_ATE_COMECAR + (palavras * MS_POR_PALAVRA) / VELOCIDADE;
  return Math.min(Math.max(estimada, MS_MIN), MS_MAX);
}

function aguardarFimDoSinal(texto) {
  return new Promise((resolve) => setTimeout(resolve, duracaoEstimada(texto)));
}

async function consumirFila() {
  if (consumindo) return;
  consumindo = true;
  while (fila.length) {
    const texto = fila.shift();
    alvo.textContent = texto;
    aplicarVelocidade(0); // vira no-op assim que o rótulo bate
    plugin.translate(texto);
    await aguardarFimDoSinal(texto);
  }
  consumindo = false;
}

function traduzir(texto) {
  fila.push(texto);
  while (fila.length > MAX_FILA) fila.shift();
  if (plugin) consumirFila();
  else alvo.textContent = texto;
}

function conectar() {
  const sock = new WebSocket(`ws://${location.host}/ws`);

  sock.onopen = () => definirStatus(plugin ? "pronto" : "carregando avatar…", "on");
  sock.onmessage = (evento) => traduzir(evento.data);
  sock.onclose = () => {
    definirStatus("desconectado — tentando novamente…", "off");
    setTimeout(conectar, 2000);
  };
}

// player.setSpeed() chega ao avatar, mas o botão do widget mantém o rótulo
// dele: ficaria escrito "1x" rodando a 1.5x, e o próximo clique do usuário
// partiria do estado errado. Clicar no botão mantém rótulo e player em sincronia.
// Insiste até o rótulo bater: o botão só é desenhado depois que o avatar carrega
// e, mesmo depois de existir, ainda passa um tempo com o clique sem efeito —
// por isso conferimos o resultado a cada tentativa em vez de clicar 3x e torcer.
function aplicarVelocidade(tentativas = 90) {
  const botao = document.querySelector(".vpw-button-speed");
  if (botao?.textContent.trim() === `${VELOCIDADE}x`) return;
  botao?.click();
  if (tentativas > 0) setTimeout(() => aplicarVelocidade(tentativas - 1), 500);
}

aguardarPlugin().then((p) => {
  plugin = p;
  aplicarVelocidade();
  definirStatus("pronto", "on");
  consumirFila();
});
conectar();

window.traduzir = traduzir;
