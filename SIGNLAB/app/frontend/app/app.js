'use strict';
/* App de gravação do SIGNLAB (PWA instalada no celular).
 *
 * Cada gravação vai primeiro para o IndexedDB e só sai de lá quando o PC
 * confirma. Com o PC desligado ou sem sinal, ela fica guardada e é enviada
 * depois: gravação é o dado mais caro deste projeto e já perdemos 50 vídeos.
 */

const $ = (id) => document.getElementById(id);

// As gravações que treinaram o modelo que já reconhece têm 57–112 quadros
// (mediana 80, ~2,7s). O treino amostra 30 quadros do vídeo inteiro, então
// gravar muito mais longo espalharia o sinal em outra escala de tempo.
const MAX_GRAVACAO_MS = 4000;
const MIN_GRAVACAO_MS = 800;
const LARGURA = 640;
const ALTURA = 480;

const estado = {
  nome: null,
  dados: null,
  sinal: null,
  facing: 'user',
  stream: null,
  video: null,
  pintura: 0,
  gravando: false,
  recorder: null,
  wakeLock: null,
};

/* ---------- utilidades ---------- */

function ler(chave) { try { return localStorage.getItem(chave); } catch { return null; } }
function gravarLocal(chave, valor) { try { localStorage.setItem(chave, valor); } catch { /* sem armazenamento */ } }
const esperar = (ms) => new Promise((ok) => setTimeout(ok, ms));

function mostrar(tela) {
  document.querySelectorAll('.tela').forEach((t) => t.classList.toggle('ativa', t.id === `tela-${tela}`));
}

function faixa(id, texto, tipo = '') {
  const el = $(id);
  el.hidden = !texto;
  el.textContent = texto || '';
  el.className = `faixa ${tipo}`;
}

function aviso(texto, tipo = '') {
  const el = $('aviso');
  el.textContent = texto;
  el.className = `aviso-gravacao ${tipo}`;
}

async function api(caminho, opcoes = {}) {
  let resposta;
  try {
    resposta = await fetch(caminho, { credentials: 'same-origin', ...opcoes });
  } catch {
    const erro = new Error('Sem conexão com o computador.');
    erro.rede = true;
    throw erro;
  }
  if (resposta.status === 401) {
    location.href = '/entrar.html';
    throw new Error('Acesso expirado.');
  }
  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    const erro = new Error((corpo && corpo.detail) || `Erro ${resposta.status}`);
    erro.status = resposta.status;
    // 5xx e 503 ("não configurado") são do lado do PC: a gravação espera.
    erro.rede = resposta.status >= 500;
    throw erro;
  }
  return corpo;
}

/* ---------- fila offline (IndexedDB) ---------- */

const fila = {
  _db: null,
  abrir() {
    if (this._db) return this._db;
    this._db = new Promise((ok, falha) => {
      const pedido = indexedDB.open('signlab-app', 1);
      pedido.onupgradeneeded = () => pedido.result.createObjectStore('fila', { keyPath: 'id', autoIncrement: true });
      pedido.onsuccess = () => ok(pedido.result);
      pedido.onerror = () => falha(pedido.error);
    });
    return this._db;
  },
  async _op(modo, fazer) {
    const db = await this.abrir();
    return new Promise((ok, falha) => {
      const tx = db.transaction('fila', modo);
      const pedido = fazer(tx.objectStore('fila'));
      tx.oncomplete = () => ok(pedido.result);
      tx.onerror = () => falha(tx.error);
    });
  },
  por(item) { return this._op('readwrite', (s) => s.add(item)); },
  tirar(id) { return this._op('readwrite', (s) => s.delete(id)); },
  todos() { return this._op('readonly', (s) => s.getAll()); },
};

let enviando = false;

async function enviarFila() {
  if (enviando) return;
  enviando = true;
  try {
    for (const item of await fila.todos()) {
      const form = new FormData();
      form.append('sinal_id', item.sinalId);
      form.append('sinalizante', item.sinalizante);
      form.append('video', item.blob, item.blob.type.includes('mp4') ? 'gravacao.mp4' : 'gravacao.webm');
      let resultado;
      try {
        resultado = await api('/app-api/gravacoes', { method: 'POST', body: form });
      } catch (erro) {
        if (erro.rede) break; // fica guardada para a próxima tentativa
        // Recusada pelo PC (mãos fora do quadro etc.): reenviar não muda nada,
        // só gravar de novo.
        await fila.tirar(item.id);
        aviso(`"${item.sinalNome}": ${erro.message}`, 'erro');
        continue;
      }
      await fila.tirar(item.id);
      atualizarContagem(item.sinalId, resultado.meus);
      aviso(`"${item.sinalNome}" salvo — ${resultado.meus} de ${meta()}`, 'ok');
    }
  } finally {
    enviando = false;
    await mostrarFila();
  }
}

async function mostrarFila() {
  const pendentes = await fila.todos();
  faixa('faixa-fila', pendentes.length
    ? `${pendentes.length} gravaç${pendentes.length === 1 ? 'ão guardada' : 'ões guardadas'} no celular, `
      + 'esperando o computador. Serão enviadas sozinhas.'
    : '', 'aviso');
  desenharProgresso();
  return pendentes;
}

/* ---------- lista de sinais ---------- */

const meta = () => (estado.dados ? estado.dados.meta : 10);

async function carregar() {
  try {
    estado.dados = await api(`/app-api/estado?sinalizante=${encodeURIComponent(estado.nome)}`);
    gravarLocal('signlab.estado', JSON.stringify(estado.dados));
    faixa('faixa-conexao', '');
  } catch (erro) {
    const guardado = ler('signlab.estado');
    if (!erro.rede || !guardado) throw erro;
    // Sem o PC dá para gravar os sinais já conhecidos: vai tudo para a fila.
    estado.dados = JSON.parse(guardado);
    faixa('faixa-conexao', 'Sem conexão com o computador. Pode gravar: as gravações ficam guardadas.', 'aviso');
  }
  desenharLista();
  await mostrarFila();
}

function desenharLista() {
  const d = estado.dados;
  $('projeto-nome').textContent = d.projeto;
  $('trocar-nome').textContent = `Gravando como ${estado.nome} · trocar`;
  const lista = $('sinais');
  lista.replaceChildren();
  if (!d.sinais.length) {
    const vazio = document.createElement('li');
    vazio.className = 'vazio';
    vazio.textContent = 'Nenhum sinal ainda. Toque em "+ Novo sinal".';
    lista.append(vazio);
  }
  for (const sinal of d.sinais) {
    const li = document.createElement('li');
    const botao = document.createElement('button');
    botao.dataset.id = sinal.id;
    botao.innerHTML = '<span class="cabeca"><strong></strong><span class="conta"></span></span>'
      + '<span class="barra"><i></i></span>';
    botao.querySelector('strong').textContent = sinal.nome;
    botao.addEventListener('click', () => abrirGravacao(sinal));
    li.append(botao);
    lista.append(li);
  }
  desenharProgresso();
  desenharPublicacao(d.publicacao);
}

async function desenharProgresso() {
  if (!estado.dados) return;
  const pendentes = await fila.todos();
  for (const sinal of estado.dados.sinais) {
    const botao = document.querySelector(`#sinais button[data-id="${sinal.id}"]`);
    if (!botao) continue;
    const esperando = pendentes.filter((p) => p.sinalId === sinal.id).length;
    botao.querySelector('.conta').textContent =
      `${sinal.meus} de ${meta()}${esperando ? ` · +${esperando} guardada${esperando > 1 ? 's' : ''}` : ''}`;
    botao.querySelector('.barra i').style.width = `${Math.min(100, (100 * sinal.meus) / meta())}%`;
    botao.classList.toggle('completo', sinal.meus >= meta());
  }
  if (estado.sinal) {
    const atual = estado.dados.sinais.find((s) => s.id === estado.sinal.id);
    if (atual) $('gravar-progresso').textContent = `${atual.meus} de ${meta()} gravações suas`;
  }
}

function atualizarContagem(sinalId, meus) {
  const sinal = estado.dados && estado.dados.sinais.find((s) => s.id === sinalId);
  if (sinal) sinal.meus = meus;
  desenharProgresso();
}

function desenharPublicacao(pub) {
  if (!pub || !pub.estado || pub.estado === 'ocioso') { faixa('faixa-publicacao', ''); return; }
  const hora = pub.quando ? new Date(pub.quando).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '';
  const textos = {
    treinando: ['Atualizando o KONECTA com as gravações novas…', 'aviso'],
    publicado: [`KONECTA atualizado às ${hora}: ${pub.sinais} sinais, acurácia ${Math.round(100 * pub.acuracia)}%.`, 'ok'],
    retido: [`O modelo novo não entrou no KONECTA: ${pub.mensagem}.`, 'aviso'],
    erro: [`Não deu para atualizar o KONECTA: ${pub.mensagem}`, 'erro'],
  };
  const [texto, tipo] = textos[pub.estado] || ['', ''];
  faixa('faixa-publicacao', texto, tipo);
}

async function novoSinal() {
  const nome = (prompt('Nome do sinal') || '').trim();
  if (!nome) return;
  try {
    const sinal = await api('/app-api/sinais', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome }),
    });
    await carregar();
    if (!sinal.novo) alert(`"${sinal.nome}" já existia; suas gravações vão para ele.`);
  } catch (erro) {
    alert(erro.rede ? 'Para criar um sinal novo o computador precisa estar ligado.' : erro.message);
  }
}

/* ---------- câmera e gravação ---------- */

async function abrirGravacao(sinal) {
  estado.sinal = sinal;
  $('gravar-nome').textContent = sinal.nome;
  aviso('');
  mostrar('gravar');
  desenharProgresso();
  try { await screen.orientation.lock('landscape'); } catch { /* só funciona com o app instalado */ }
  try { estado.wakeLock = await navigator.wakeLock.request('screen'); } catch { /* opcional */ }
  await abrirCamera();
}

async function abrirCamera() {
  pararCamera();
  try {
    estado.stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: estado.facing, width: { ideal: 1280 }, height: { ideal: 720 } },
    });
  } catch (erro) {
    aviso(`Não consegui abrir a câmera: ${erro.message}. Libere a câmera para este app nas permissões.`, 'erro');
    return;
  }
  const video = document.createElement('video');
  video.muted = true;
  video.playsInline = true;
  video.srcObject = estado.stream;
  await video.play();
  estado.video = video;
  $('quadro').classList.toggle('espelho', estado.facing === 'user');
  desenhar();
}

function desenhar() {
  const contexto = $('quadro').getContext('2d');
  // Timer, não requestAnimationFrame: o gravador precisa de 30 quadros/s
  // estáveis, não de pintura sincronizada com a tela. E o rAF para quando o
  // navegador acha que a janela não está visível — a gravação saía vazia.
  const passo = () => {
    const v = estado.video;
    if (!v) return;
    const vw = v.videoWidth;
    const vh = v.videoHeight;
    if (vw && vh) {
      // Recorta o centro em 4:3 e reduz para 640x480: é exatamente o que a
      // webcam do KONECTA entrega. O PC recusa vídeo em outra proporção.
      let sw = vw;
      let sh = vh;
      if (vw / vh > LARGURA / ALTURA) sw = (vh * LARGURA) / ALTURA; else sh = (vw * ALTURA) / LARGURA;
      contexto.drawImage(v, (vw - sw) / 2, (vh - sh) / 2, sw, sh, 0, 0, LARGURA, ALTURA);
    }
    $('gire').hidden = !matchMedia('(orientation: portrait)').matches;
  };
  clearInterval(estado.pintura);
  estado.pintura = setInterval(passo, 1000 / 30);
}

function pararCamera() {
  clearInterval(estado.pintura);
  if (estado.stream) estado.stream.getTracks().forEach((t) => t.stop());
  estado.stream = null;
  estado.video = null;
}

function tipoDeVideo() {
  for (const tipo of ['video/webm;codecs=vp8', 'video/webm', 'video/mp4']) {
    if (window.MediaRecorder && MediaRecorder.isTypeSupported(tipo)) return tipo;
  }
  return '';
}

async function gravar() {
  if (estado.gravando) {
    if (estado.recorder && estado.recorder.state !== 'inactive') estado.recorder.stop();
    return;
  }
  if (!estado.video) { await abrirCamera(); if (!estado.video) return; }
  const botao = $('botao-gravar');
  estado.gravando = true;
  botao.disabled = true;
  aviso('');

  const contagem = $('contagem');
  contagem.hidden = false;
  for (const n of [3, 2, 1]) { contagem.textContent = n; await esperar(700); }
  contagem.hidden = true;

  const tipo = tipoDeVideo();
  const trilha = $('quadro').captureStream(30);
  const recorder = new MediaRecorder(trilha, { ...(tipo && { mimeType: tipo }), videoBitsPerSecond: 1_500_000 });
  const pedacos = [];
  recorder.ondataavailable = (e) => { if (e.data.size) pedacos.push(e.data); };
  const terminou = new Promise((ok) => { recorder.onstop = ok; });
  estado.recorder = recorder;
  recorder.start();
  const inicio = performance.now();
  $('quadro').parentElement.classList.add('gravando');
  botao.textContent = 'Parar';
  botao.classList.add('parar');
  botao.disabled = false;
  const limite = setTimeout(() => { if (recorder.state !== 'inactive') recorder.stop(); }, MAX_GRAVACAO_MS);

  await terminou;
  clearTimeout(limite);
  trilha.getTracks().forEach((t) => t.stop());
  $('quadro').parentElement.classList.remove('gravando');
  botao.textContent = 'Gravar';
  botao.classList.remove('parar');
  estado.gravando = false;
  estado.recorder = null;

  if (performance.now() - inicio < MIN_GRAVACAO_MS) {
    aviso('Curta demais. Faça o sinal inteiro depois do 1.', 'erro');
    return;
  }
  const blob = new Blob(pedacos, { type: tipo || 'video/webm' });
  // Vazia = só o cabeçalho WebM (~110 bytes). Uma cena lisa de 1,5s já deu
  // 12 KB no teste, então o corte fica bem abaixo disso para não recusar à toa.
  // Avisa aqui em vez de mandar para o PC e voltar um erro que ela não entende.
  if (blob.size < 2_000) {
    aviso('A gravação saiu vazia. Tente de novo; se repetir, feche e abra o app.', 'erro');
    return;
  }
  await fila.por({
    sinalId: estado.sinal.id,
    sinalNome: estado.sinal.nome,
    sinalizante: estado.nome,
    blob,
    criado: Date.now(),
  });
  aviso('Analisando as mãos…');
  await mostrarFila();
  enviarFila();
}

async function voltar() {
  if (estado.recorder && estado.recorder.state !== 'inactive') estado.recorder.stop();
  pararCamera();
  try { screen.orientation.unlock(); } catch { /* idem */ }
  if (estado.wakeLock) { estado.wakeLock.release().catch(() => {}); estado.wakeLock = null; }
  estado.sinal = null;
  mostrar('lista');
  carregar().catch(() => {});
}

/* ---------- início ---------- */

function pedirNome() {
  $('campo-nome').value = estado.nome || '';
  mostrar('nome');
  $('campo-nome').focus();
}

async function iniciar() {
  estado.nome = ler('signlab.nome');
  if (!estado.nome) { pedirNome(); return; }
  try {
    await carregar();
    mostrar('lista');
  } catch (erro) {
    $('erro-msg').textContent = erro.message;
    mostrar('erro');
  }
}

$('salvar-nome').addEventListener('click', () => {
  const nome = $('campo-nome').value.trim().replace(/\s+/g, ' ');
  if (!nome) return;
  estado.nome = nome;
  gravarLocal('signlab.nome', nome);
  iniciar();
});
$('trocar-nome').addEventListener('click', pedirNome);
$('novo-sinal').addEventListener('click', novoSinal);
$('botao-gravar').addEventListener('click', gravar);
$('voltar').addEventListener('click', voltar);
$('trocar-camera').addEventListener('click', () => {
  estado.facing = estado.facing === 'user' ? 'environment' : 'user';
  abrirCamera();
});
$('tentar-de-novo').addEventListener('click', iniciar);

let pedidoInstalar = null;
addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  pedidoInstalar = e;
  $('instalar').hidden = false;
});
$('instalar').addEventListener('click', () => {
  if (pedidoInstalar) pedidoInstalar.prompt();
  pedidoInstalar = null;
  $('instalar').hidden = true;
});

// Gravação guardada não pode ser despejada pelo Android quando falta espaço.
if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
addEventListener('online', enviarFila);
setInterval(() => {
  enviarFila();
  if (estado.sinal === null && estado.nome && $('tela-lista').classList.contains('ativa')) carregar().catch(() => {});
}, 30_000);

iniciar().then(enviarFila);
