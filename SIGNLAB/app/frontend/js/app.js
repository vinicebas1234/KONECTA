/* SIGNLAB — aplicação principal (SPA com roteamento por hash). */
const $app = document.getElementById('app');
const $fileInput = document.getElementById('file-input');

const state = {
  project: null,     // projeto aberto (com classes)
  examples: {},      // classId -> lista de exemplos
  tab: 'exemplos',
  uploadClassId: null,
};

/* ===== Utilidades ===== */
function esc(text) {
  const div = document.createElement('div');
  div.textContent = text ?? '';
  return div.innerHTML;
}

function toast(message, type = '') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function formatDate(sqliteDate) {
  const d = new Date(sqliteDate.replace(' ', 'T') + 'Z');
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' });
}

function plural(n, singular, pluralWord) {
  return `${n} ${n === 1 ? singular : (pluralWord || singular + 's')}`;
}

/* ===== Modais ===== */
function modalPrompt(title, placeholder, initial = '') {
  return new Promise(resolve => {
    const root = document.getElementById('modal-root');
    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    overlay.innerHTML = `
      <div class="modal">
        <h3>${esc(title)}</h3>
        <input type="text" placeholder="${esc(placeholder)}" value="${esc(initial)}" maxlength="100">
        <div class="modal-actions">
          <button class="btn btn-ghost" data-r="cancel">Cancelar</button>
          <button class="btn btn-primary" data-r="ok">Confirmar</button>
        </div>
      </div>`;
    root.appendChild(overlay);
    const input = overlay.querySelector('input');
    input.focus();
    input.select();

    function done(value) { overlay.remove(); resolve(value); }
    overlay.addEventListener('click', e => {
      if (e.target === overlay) return done(null);
      const btn = e.target.closest('[data-r]');
      if (!btn) return;
      done(btn.dataset.r === 'ok' ? input.value.trim() || null : null);
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') done(input.value.trim() || null);
      if (e.key === 'Escape') done(null);
    });
  });
}

function modalConfirm(title, message) {
  return new Promise(resolve => {
    const root = document.getElementById('modal-root');
    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    overlay.innerHTML = `
      <div class="modal">
        <h3>${esc(title)}</h3>
        <p>${esc(message)}</p>
        <div class="modal-actions">
          <button class="btn btn-ghost" data-r="cancel">Cancelar</button>
          <button class="btn btn-danger" data-r="ok">Excluir</button>
        </div>
      </div>`;
    root.appendChild(overlay);
    overlay.addEventListener('click', e => {
      if (e.target === overlay) { overlay.remove(); resolve(false); return; }
      const btn = e.target.closest('[data-r]');
      if (!btn) return;
      overlay.remove();
      resolve(btn.dataset.r === 'ok');
    });
  });
}

/* ===== Roteamento ===== */
window.addEventListener('hashchange', route);

function route() {
  const hash = location.hash || '#/';
  const match = hash.match(/^#\/p\/(\d+)/);
  if (match) {
    state.tab = 'exemplos';
    loadProject(Number(match[1]));
  } else {
    renderHome();
  }
}

/* ===== Home ===== */
async function renderHome() {
  $app.innerHTML = '<div class="loading">Carregando…</div>';
  let projects;
  try {
    projects = await api.listProjects();
  } catch (err) {
    $app.innerHTML = `<div class="empty">Erro ao carregar projetos: ${esc(err.message)}</div>`;
    return;
  }

  const cards = projects.map(p => `
    <div class="project-card" data-action="open-project" data-id="${p.id}">
      <h3>
        <span>${esc(p.name)}</span>
        <button class="icon-btn danger" data-action="delete-project" data-id="${p.id}"
                title="Excluir projeto">🗑</button>
      </h3>
      <div class="meta">${plural(p.class_count, 'classe')} • ${plural(p.example_count, 'exemplo')}</div>
      <div class="date">Atualizado em ${formatDate(p.updated_at)}</div>
    </div>`).join('');

  $app.innerHTML = `
    <section class="hero">
      <h1>Crie um modelo de reconhecimento de <span>Libras</span></h1>
      <p>Ensine o computador a reconhecer sinais usando imagens, vídeos e a sua webcam —
         sem precisar saber Machine Learning.</p>
      <button class="btn btn-primary btn-lg" data-action="new-project">+ Novo projeto</button>
      <div class="flow-hint">
        <span class="chip">Criar classes</span><span class="arrow">→</span>
        <span class="chip">Adicionar exemplos</span><span class="arrow">→</span>
        <span class="chip">Treinar</span><span class="arrow">→</span>
        <span class="chip">Testar</span><span class="arrow">→</span>
        <span class="chip">Exportar</span>
      </div>
    </section>
    <h2 class="section-title">Projetos recentes</h2>
    ${projects.length
      ? `<div class="project-list">${cards}</div>`
      : '<div class="empty">Nenhum projeto ainda. Clique em “+ Novo projeto” para começar.</div>'}
  `;
}

/* ===== Projeto ===== */
async function loadProject(id) {
  $app.innerHTML = '<div class="loading">Carregando…</div>';
  try {
    state.project = await api.getProject(id);
    const lists = await Promise.all(
      state.project.classes.map(c => api.listExamples(c.id))
    );
    state.examples = {};
    state.project.classes.forEach((c, i) => { state.examples[c.id] = lists[i]; });
  } catch (err) {
    $app.innerHTML = `<div class="empty">Erro: ${esc(err.message)} — <a href="#/">voltar</a></div>`;
    return;
  }
  renderProject();
}

function refreshProject() {
  if (state.project) loadProject(state.project.id);
}

function renderProject() {
  const p = state.project;
  const tabs = [
    ['exemplos', '01', 'Exemplos'],
    ['treino', '02', 'Treinamento'],
    ['teste', '03', 'Teste'],
    ['exportar', '04', 'Exportar'],
  ];

  $app.innerHTML = `
    <div class="project-head">
      <div>
        <a class="back" href="#/">← Projetos</a>
        <div class="project-title">
          <h2>${esc(p.name)}</h2>
          <button class="icon-btn" data-action="rename-project" title="Renomear projeto">✏️</button>
        </div>
      </div>
    </div>
    <nav class="stepper">
      ${tabs.map(([key, num, label]) => `
        <button class="step ${state.tab === key ? 'active' : ''}" data-action="tab" data-tab="${key}">
          <span class="num">${num}</span>${label}
        </button>`).join('')}
    </nav>
    <div id="tab-content"></div>
  `;
  renderTab();
}

function renderTab() {
  const container = document.getElementById('tab-content');
  if (!container) return;
  if (state.tab === 'exemplos') container.innerHTML = viewExamples();
  else if (state.tab === 'treino') container.innerHTML = viewTraining();
  else if (state.tab === 'teste') container.innerHTML = viewTest();
  else container.innerHTML = viewExport();
}

/* ===== Aba 01 — Exemplos ===== */
function thumbHtml(example) {
  const url = api.fileUrl(example.rel_path);
  const media = example.kind === 'image'
    ? `<img src="${url}" loading="lazy" alt="">`
    : `<video src="${url}" preload="metadata" muted></video>`;
  const badge = example.kind === 'video' ? '<span class="badge">▶ vídeo</span>'
    : example.source === 'webcam' ? '<span class="badge">📷</span>' : '';
  return `
    <div class="thumb">
      ${media}${badge}
      <button class="del" data-action="del-example" data-id="${example.id}" title="Excluir exemplo">✕</button>
    </div>`;
}

function classCardHtml(cls) {
  const examples = state.examples[cls.id] || [];
  const shown = examples.slice(0, examples.length > 8 ? 7 : 8);
  const rest = examples.length - shown.length;

  const counts = `
    <div class="class-counts">
      <span class="count-chip total">${plural(cls.total, 'exemplo')}</span>
      ${cls.images ? `<span class="count-chip">${plural(cls.images, 'imagem', 'imagens')}</span>` : ''}
      ${cls.videos ? `<span class="count-chip">${plural(cls.videos, 'vídeo')}</span>` : ''}
      ${cls.captures ? `<span class="count-chip">${plural(cls.captures, 'captura')}</span>` : ''}
    </div>`;

  const gallery = examples.length
    ? `<div class="thumb-grid">
         ${shown.map(thumbHtml).join('')}
         ${rest > 0 ? `<div class="thumb more">+${rest}</div>` : ''}
       </div>`
    : '<div class="dropzone-hint">Arraste imagens ou vídeos aqui<br>ou use os botões abaixo</div>';

  return `
    <div class="class-card" data-class-id="${cls.id}">
      <div class="class-card-head">
        <h3 class="class-name">${esc(cls.name)}</h3>
        <div>
          <button class="icon-btn" data-action="rename-class" data-id="${cls.id}" title="Renomear">✏️</button>
          <button class="icon-btn danger" data-action="delete-class" data-id="${cls.id}" title="Excluir classe">🗑</button>
        </div>
      </div>
      ${counts}
      ${gallery}
      <div class="class-actions">
        <button class="btn btn-ghost" data-action="upload" data-id="${cls.id}">📁 Arquivos</button>
        <button class="btn btn-ghost" data-action="webcam" data-id="${cls.id}" data-name="${esc(cls.name)}">📷 Webcam</button>
      </div>
    </div>`;
}

function viewExamples() {
  const classes = state.project.classes;
  return `
    <div class="class-grid">
      ${classes.map(classCardHtml).join('')}
      <button class="add-class-card" data-action="add-class">
        <span class="plus">＋</span> Nova classe
      </button>
    </div>`;
}

/* ===== Aba 02 — Treinamento (análise do dataset; treino chega na Fase 2) ===== */
function datasetAnalysis() {
  const classes = state.project.classes;
  const items = [];

  if (classes.length < 2) {
    items.push(['warn', '⚠', 'Crie pelo menos 2 classes para poder treinar um modelo.']);
  }
  const totals = classes.map(c => c.total);
  const totalExamples = totals.reduce((a, b) => a + b, 0);

  for (const c of classes) {
    if (c.total === 0) {
      items.push(['warn', '⚠', `A classe “${c.name}” não possui exemplos.`]);
    } else if (c.total < 30) {
      items.push(['warn', '⚠', `A classe “${c.name}” possui poucos exemplos (${c.total}). Sugestão: pelo menos 30.`]);
    }
  }

  const nonEmpty = totals.filter(t => t > 0);
  if (nonEmpty.length >= 2 && Math.max(...nonEmpty) >= 3 * Math.min(...nonEmpty)) {
    items.push(['warn', '⚠', 'O dataset está desbalanceado: há grande diferença de exemplos entre classes.']);
  }

  const images = classes.reduce((a, c) => a + c.images, 0);
  const videos = classes.reduce((a, c) => a + c.videos, 0);
  const captures = classes.reduce((a, c) => a + c.captures, 0);
  items.push(['info', 'ℹ', `Dataset atual: ${plural(classes.length, 'classe')}, ` +
    `${plural(images, 'imagem', 'imagens')}, ${plural(videos, 'vídeo')} e ${plural(captures, 'captura')} de webcam.`]);

  if (classes.length >= 2 && totalExamples > 0 &&
      !items.some(([type]) => type === 'warn')) {
    items.push(['ok', '✓', 'Dataset processável. Pronto para o pipeline de treinamento.']);
  }
  items.push(['info', '💡', 'O LSAE poderá aumentar a diversidade espacial e temporal deste dataset (Fase 4).']);

  return items.map(([type, icon, text]) =>
    `<div class="analysis-item ${type}"><span>${icon}</span><span>${esc(text)}</span></div>`).join('');
}

function viewTraining() {
  return `
    <div class="panel">
      <span class="phase-badge">Disponível na Fase 2 — Imagens</span>
      <h3>Treinamento</h3>
      <p class="note">
        Aqui o SIGNLAB vai processar seus exemplos (MediaPipe → landmarks → features),
        aplicar o LSAE e treinar o modelo automaticamente. Enquanto o pipeline não chega,
        a análise do dataset já está ativa:
      </p>
      <div class="analysis">${datasetAnalysis()}</div>
      <div class="train-cta">
        <button class="btn btn-primary btn-lg" disabled title="Disponível na Fase 2">
          ⚡ Treinar modelo
        </button>
      </div>
    </div>`;
}

/* ===== Aba 03 — Teste ===== */
function viewTest() {
  return `
    <div class="panel">
      <span class="phase-badge">Disponível nas Fases 2, 3 e 6</span>
      <h3>Teste</h3>
      <p class="note">
        Depois de treinar, você poderá testar o modelo com uma <b>imagem</b>, um
        <b>vídeo</b> ou em <b>tempo real pela webcam</b>, vendo a confiança de cada classe.
      </p>
    </div>`;
}

/* ===== Aba 04 — Exportar ===== */
function viewExport() {
  return `
    <div class="panel">
      <span class="phase-badge">Disponível após o treinamento</span>
      <h3>Exportar</h3>
      <p class="note">
        O modelo treinado poderá ser exportado (TensorFlow, Keras, TensorFlow.js, ONNX)
        junto com configuração, classes, features, normalização e metadados —
        pronto para ser usado no KONECTA.
      </p>
    </div>`;
}

/* ===== Ações ===== */
$app.addEventListener('click', async e => {
  const target = e.target.closest('[data-action]');
  if (!target) return;
  const { action, id, tab, name } = target.dataset;

  try {
    if (action === 'new-project') {
      const projName = await modalPrompt('Novo projeto', 'Ex.: Sinais básicos de Libras');
      if (!projName) return;
      const project = await api.createProject(projName);
      location.hash = `#/p/${project.id}`;

    } else if (action === 'open-project') {
      if (e.target.closest('[data-action="delete-project"]')) return;
      location.hash = `#/p/${id}`;

    } else if (action === 'delete-project') {
      e.stopPropagation();
      const ok = await modalConfirm('Excluir projeto',
        'Todas as classes e exemplos deste projeto serão apagados definitivamente.');
      if (ok) { await api.deleteProject(id); toast('Projeto excluído.', 'success'); renderHome(); }

    } else if (action === 'rename-project') {
      const newName = await modalPrompt('Renomear projeto', '', state.project.name);
      if (!newName) return;
      await api.renameProject(state.project.id, newName);
      refreshProject();

    } else if (action === 'tab') {
      state.tab = tab;
      renderProject();

    } else if (action === 'add-class') {
      const clsName = await modalPrompt('Nova classe', 'Ex.: OBRIGADO');
      if (!clsName) return;
      await api.createClass(state.project.id, clsName);
      refreshProject();

    } else if (action === 'rename-class') {
      const cls = state.project.classes.find(c => c.id === Number(id));
      const newName = await modalPrompt('Renomear classe', '', cls ? cls.name : '');
      if (!newName) return;
      await api.renameClass(id, newName);
      refreshProject();

    } else if (action === 'delete-class') {
      const ok = await modalConfirm('Excluir classe',
        'Todos os exemplos desta classe serão apagados definitivamente.');
      if (ok) { await api.deleteClass(id); toast('Classe excluída.', 'success'); refreshProject(); }

    } else if (action === 'upload') {
      state.uploadClassId = Number(id);
      $fileInput.value = '';
      $fileInput.click();

    } else if (action === 'webcam') {
      Webcam.open(Number(id), name, captured => {
        if (captured > 0) toast(`${captured} captura(s) adicionada(s).`, 'success');
        refreshProject();
      });

    } else if (action === 'del-example') {
      await api.deleteExample(id);
      refreshProject();
    }
  } catch (err) {
    toast(err.message, 'error');
  }
});

$fileInput.addEventListener('change', async () => {
  const files = [...$fileInput.files];
  if (!files.length || !state.uploadClassId) return;
  await uploadFiles(state.uploadClassId, files);
});

async function uploadFiles(classId, files) {
  toast(`Enviando ${plural(files.length, 'arquivo')}…`);
  try {
    const result = await api.uploadExamples(classId, files);
    if (result.saved.length) {
      toast(`${plural(result.saved.length, 'exemplo adicionado', 'exemplos adicionados')}.`, 'success');
    }
    if (result.rejected.length) {
      toast(`Formato não suportado: ${result.rejected.join(', ')}`, 'error');
    }
    refreshProject();
  } catch (err) {
    toast('Falha no envio: ' + err.message, 'error');
  }
}

/* ===== Drag & drop nos cards de classe ===== */
$app.addEventListener('dragover', e => {
  const card = e.target.closest('.class-card');
  if (!card) return;
  e.preventDefault();
  card.classList.add('dragover');
});

$app.addEventListener('dragleave', e => {
  const card = e.target.closest('.class-card');
  if (card && !card.contains(e.relatedTarget)) card.classList.remove('dragover');
});

$app.addEventListener('drop', e => {
  const card = e.target.closest('.class-card');
  if (!card) return;
  e.preventDefault();
  card.classList.remove('dragover');
  const files = [...e.dataTransfer.files];
  if (files.length) uploadFiles(Number(card.dataset.classId), files);
});

/* ===== Início ===== */
route();
