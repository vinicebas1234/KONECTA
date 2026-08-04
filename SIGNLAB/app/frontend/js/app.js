/* SIGNLAB — aplicação principal (SPA com roteamento por hash). */
const $app = document.getElementById('app');
const $fileInput = document.getElementById('file-input');
const $testFileInput = document.getElementById('test-file-input');

const state = {
  project: null,      // projeto aberto (com classes)
  examples: {},       // classId -> lista de exemplos
  experiments: [],    // experimentos do projeto (mais recente primeiro)
  tab: 'exemplos',
  mediaTab: 'image',      // modalidade ativa na etapa Exemplos
  trainModality: 'image', // modalidade do treinamento: 'image' | 'video'
  uploadClassId: null,
  testExpId: null,        // experimento selecionado na aba Teste
  testResult: null,
  testStream: null,       // stream da webcam de teste
  testRecorder: null,     // MediaRecorder do teste temporal
  selectedCameraId: null, // ID do dispositivo de câmera selecionado
  availableCameras: [],   // lista de câmeras disponíveis
  pollTimer: null,
  training: false,
  lsae: {                 // configuração do LSAE enviada ao treinar
    enabled: false, auto: true, intensity: 0.5, factor: 3,
    spatial: true, scale: true, noise: true, temporal: true,
  },
};

const MODEL_LABELS = { rf: 'Random Forest', mlp: 'MLP', bilstm: 'BiLSTM', lstm: 'LSTM' };
const MODEL_MODALITY = { rf: 'image', mlp: 'image', bilstm: 'video', lstm: 'video' };

function classKindCounts(clsId) {
  const all = state.examples[clsId] || [];
  return {
    images: all.filter(e => e.kind === 'image').length,
    videos: all.filter(e => e.kind === 'video').length,
  };
}

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

function pct(x) { return (x * 100).toFixed(1).replace('.', ',') + '%'; }

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

function stopTestCam() {
  if (state.testRecorder) {
    state.testRecorder.onstop = null;
    try { state.testRecorder.stop(); } catch (_) {}
    state.testRecorder = null;
  }
  if (state.testStream) {
    state.testStream.getTracks().forEach(t => t.stop());
    state.testStream = null;
  }
}

function route() {
  stopTestCam();
  const hash = location.hash || '#/';
  const match = hash.match(/^#\/p\/(\d+)/);
  if (match) {
    state.tab = 'exemplos';
    loadProject(Number(match[1]));
  } else {
    state.project = null;
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
      : '<div class="empty">Nenhum projeto ainda. Clique em "+ Novo projeto" para começar.</div>'}
  `;
}

/* ===== Projeto ===== */
async function loadProject(id) {
  $app.innerHTML = '<div class="loading">Carregando…</div>';
  try {
    const [project, experiments] = await Promise.all([
      api.getProject(id),
      api.listExperiments(id),
    ]);
    state.project = project;
    state.experiments = experiments;
    if (!state.experiments.some(e => e.id === state.testExpId)) {
      state.testExpId = experiments.length ? experiments[0].id : null;
    }
    const lists = await Promise.all(
      project.classes.map(c => api.listExamples(c.id))
    );
    state.examples = {};
    project.classes.forEach((c, i) => { state.examples[c.id] = lists[i]; });
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
  stopTestCam();
  const p = state.project;
  const tabs = [
    ['exemplos', '01', 'Exemplos'],
    ['treino', '02', 'Treinamento'],
    ['analise', '03', 'Análise'],
    ['teste', '04', 'Teste'],
    ['exportar', '05', 'Exportar'],
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
  else if (state.tab === 'analise') container.innerHTML = viewAnalysis();
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
  const kind = state.mediaTab;
  const all = state.examples[cls.id] || [];
  const examples = all.filter(e => e.kind === kind);
  const shown = examples.slice(0, examples.length > 8 ? 7 : 8);
  const rest = examples.length - shown.length;

  const counts = `
    <div class="class-counts">
      <span class="count-chip total">
        ${kind === 'image' ? plural(examples.length, 'imagem', 'imagens')
                           : plural(examples.length, 'vídeo')}
      </span>
      <span class="count-chip">${plural(cls.total, 'exemplo')} no total</span>
    </div>`;

  const emptyHint = kind === 'image'
    ? 'Arraste imagens aqui,<br>ou use os botões abaixo'
    : 'Arraste vídeos aqui — você pode<br>enviar vários de uma vez';
  const gallery = examples.length
    ? `<div class="thumb-grid">
         ${shown.map(thumbHtml).join('')}
         ${rest > 0 ? `<div class="thumb more">+${rest}</div>` : ''}
       </div>`
    : `<div class="dropzone-hint">${emptyHint}</div>`;

  const actions = kind === 'image'
    ? `<button class="btn btn-ghost" data-action="upload" data-id="${cls.id}">📁 Imagens</button>
       <button class="btn btn-ghost" data-action="webcam" data-id="${cls.id}" data-name="${esc(cls.name)}">📷 Webcam</button>`
    : `<button class="btn btn-ghost" data-action="upload" data-id="${cls.id}">📁 Vídeos</button>
       <button class="btn btn-ghost" data-action="webcam" data-id="${cls.id}" data-name="${esc(cls.name)}">🎥 Gravar</button>`;

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
      <div class="class-actions">${actions}</div>
    </div>`;
}

function viewExamples() {
  const classes = state.project.classes;
  const allExamples = Object.values(state.examples).flat();
  const nImages = allExamples.filter(e => e.kind === 'image').length;
  const nVideos = allExamples.filter(e => e.kind === 'video').length;
  return `
    <div class="media-tabs">
      <button class="media-tab ${state.mediaTab === 'image' ? 'active' : ''}"
              data-action="media-tab" data-kind="image">🖼 Imagens (${nImages})</button>
      <button class="media-tab ${state.mediaTab === 'video' ? 'active' : ''}"
              data-action="media-tab" data-kind="video">🎥 Vídeos (${nVideos})</button>
    </div>
    <div class="class-grid">
      ${classes.map(classCardHtml).join('')}
      <button class="add-class-card" data-action="add-class">
        <span class="plus">＋</span> Nova classe
      </button>
    </div>`;
}

/* ===== Aba 02 — Treinamento ===== */
function datasetAnalysis(modality) {
  const classes = state.project.classes;
  const items = [];
  const isVideo = modality === 'video';
  const noun = isVideo ? 'vídeo' : 'imagem';
  const nounPl = isVideo ? 'vídeos' : 'imagens';
  const minSuggested = isVideo ? 10 : 30;

  if (classes.length < 2) {
    items.push(['warn', '⚠', 'Crie pelo menos 2 classes para poder treinar um modelo.']);
  }

  const counts = classes.map(c => {
    const kc = classKindCounts(c.id);
    return isVideo ? kc.videos : kc.images;
  });

  classes.forEach((c, i) => {
    if (counts[i] === 0) {
      items.push(['warn', '⚠', `A classe "${c.name}" não possui ${nounPl}.`]);
    } else if (counts[i] < minSuggested) {
      items.push(['warn', '⚠', `A classe "${c.name}" possui ${isVideo ? 'poucos' : 'poucas'} ${nounPl} (${counts[i]}). Sugestão: pelo menos ${minSuggested}.`]);
    }
  });

  const nonEmpty = counts.filter(t => t > 0);
  if (nonEmpty.length >= 2 && Math.max(...nonEmpty) >= 3 * Math.min(...nonEmpty)) {
    items.push(['warn', '⚠', 'O dataset está desbalanceado: há grande diferença de exemplos entre classes.']);
  }

  const total = counts.reduce((a, b) => a + b, 0);
  items.push(['info', 'ℹ', `Dataset ${isVideo ? 'temporal' : 'estático'}: ` +
    `${plural(classes.length, 'classe')} e ${plural(total, noun, nounPl)}.` +
    (isVideo ? ' Cada vídeo vira uma sequência de 30 frames com landmarks.' : '')]);

  if (classes.length >= 2 && nonEmpty.length >= 2 &&
      !items.some(([type]) => type === 'warn')) {
    items.push(['ok', '✓', 'Dataset processável. Pronto para o treinamento.']);
  }
  items.push(['info', '💡', 'Ative o LSAE abaixo para ampliar a diversidade ' +
    (isVideo ? 'espacial e temporal' : 'espacial') + ' do treino com variações sintéticas.']);

  return items.map(([type, icon, text]) =>
    `<div class="analysis-item ${type}"><span>${icon}</span><span>${esc(text)}</span></div>`).join('');
}

function confusionHtml(confusion) {
  const max = Math.max(1, ...confusion.matrix.flat());
  return `
    <div class="conf-wrap">
      <table class="conf-table">
        <tr><th></th>${confusion.labels.map(l => `<th>${esc(l)}</th>`).join('')}</tr>
        ${confusion.matrix.map((row, i) => `
          <tr>
            <th>${esc(confusion.labels[i])}</th>
            ${row.map((v, j) => {
              const alpha = v === 0 ? 0 : 0.15 + 0.6 * (v / max);
              const color = i === j ? `rgba(10,163,150,${alpha})` : `rgba(214,69,69,${alpha})`;
              return `<td style="background:${color}">${v}</td>`;
            }).join('')}
          </tr>`).join('')}
      </table>
    </div>`;
}

function experimentHtml(exp, open = false) {
  const m = exp.metrics;
  const modelLabel = `${MODEL_MODALITY[exp.model_type] === 'video' ? '🎥' : '🖼'} ${MODEL_LABELS[exp.model_type]}`;
  const excluded = (exp.classes || []).filter(c => c.excluded);
  const lsaeOn = m.lsae && m.lsae.enabled;
  const lsaeBadge = lsaeOn
    ? `<span class="lsae-badge on">LSAE ${m.lsae.factor}x</span>`
    : '<span class="lsae-badge">LSAE OFF</span>';
  const trainCell = lsaeOn && m.train_size_original
    ? `${m.train_size_original} → ${m.train_size} / ${m.test_size}`
    : `${m.train_size} / ${m.test_size}`;
  return `
    <details class="exp-item" ${open ? 'open' : ''}>
      <summary>
        <span class="exp-id">#${String(exp.id).padStart(3, '0')}</span>
        <span class="exp-model">${modelLabel}</span>
        ${lsaeBadge}
        <span class="exp-date">${formatDate(exp.created_at)}</span>
        <span class="exp-metric">Accuracy <b>${pct(m.accuracy)}</b></span>
        <span class="exp-metric">F1 <b>${pct(m.f1)}</b></span>
      </summary>
      <div class="exp-body">
        <div class="metrics-grid">
          <div class="metric"><span>Accuracy</span><b>${pct(m.accuracy)}</b></div>
          <div class="metric"><span>Precision</span><b>${pct(m.precision)}</b></div>
          <div class="metric"><span>Recall</span><b>${pct(m.recall)}</b></div>
          <div class="metric"><span>F1</span><b>${pct(m.f1)}</b></div>
          <div class="metric"><span>Qualidade dos landmarks</span><b>${pct(m.landmark_quality)}</b></div>
          <div class="metric"><span>Treino${lsaeOn ? ' (orig. → LSAE)' : ''} / Teste</span><b>${trainCell}</b></div>
        </div>
        <h4>Métricas por classe</h4>
        <table class="per-class-table">
          <tr><th>Classe</th><th>Precision</th><th>Recall</th><th>F1</th><th>Exemplos de teste</th></tr>
          ${m.per_class.map(c => `
            <tr><td>${esc(c.name)}</td><td>${pct(c.precision)}</td>
                <td>${pct(c.recall)}</td><td>${pct(c.f1)}</td><td>${c.support}</td></tr>`).join('')}
        </table>
        <h4>Matriz de confusão <span class="hint">(linhas: real · colunas: predição)</span></h4>
        ${confusionHtml(m.confusion)}
        ${excluded.length ? `<p class="note">⚠ Classes excluídas por falta de exemplos válidos:
          ${excluded.map(c => esc(c.name)).join(', ')}</p>` : ''}
        <div class="exp-actions">
          <a class="btn btn-ghost btn-sm" href="${api.exportUrl(exp.id)}">⬇ Exportar modelo</a>
          <span class="hint">Treinado em ${m.train_seconds}s</span>
        </div>
      </div>
    </details>`;
}

function lsaePanelHtml(isVideo) {
  const l = state.lsae;
  const manualDisabled = l.auto ? 'disabled' : '';
  const controls = !l.enabled ? '' : `
    <div class="lsae-controls">
      <label class="lsae-check"><input type="checkbox" data-lsae="auto" ${l.auto ? 'checked' : ''}>
        <span><b>Auto LSAE</b> — o sistema escolhe intensidade e quantidade</span></label>
      <div class="lsae-manual">
        <label class="lsae-field">Intensidade
          <input type="range" data-lsae="intensity" min="10" max="100" step="5"
                 value="${Math.round(l.intensity * 100)}" ${manualDisabled}>
        </label>
        <label class="lsae-field">Quantidade
          <select data-lsae="factor" ${manualDisabled}>
            ${[2, 3, 4, 5].map(f => `<option value="${f}" ${l.factor === f ? 'selected' : ''}>${f}x</option>`).join('')}
          </select>
        </label>
        <label class="lsae-check"><input type="checkbox" data-lsae="spatial" ${l.spatial ? 'checked' : ''} ${manualDisabled}> Spatial (rotação)</label>
        <label class="lsae-check"><input type="checkbox" data-lsae="scale" ${l.scale ? 'checked' : ''} ${manualDisabled}> Scale</label>
        <label class="lsae-check"><input type="checkbox" data-lsae="noise" ${l.noise ? 'checked' : ''} ${manualDisabled}> Noise</label>
        ${isVideo ? `<label class="lsae-check"><input type="checkbox" data-lsae="temporal" ${l.temporal ? 'checked' : ''} ${manualDisabled}> Temporal (ritmo)</label>` : ''}
      </div>
      <p class="hint">O LSAE é aplicado somente ao conjunto de treino, depois do split —
         teste e validação permanecem originais (anti data-leakage).</p>
    </div>`;

  return `
    <div class="lsae-panel ${l.enabled ? 'on' : ''}">
      <div class="lsae-head">
        <label class="lsae-check lsae-title">
          <input type="checkbox" data-lsae="enabled" ${l.enabled ? 'checked' : ''}>
          <span><b>LSAE</b> — Libras Semantic Augmentation Engine</span>
        </label>
        <span class="hint">Gera variações plausíveis dos landmarks
          (rotação, escala, ruído${isVideo ? ', ritmo' : ''}) para ampliar a diversidade do treino.</span>
      </div>
      ${controls}
    </div>`;
}

function viewTraining() {
  const isVideo = state.trainModality === 'video';
  const trainable = state.project.classes.filter(c => {
    const kc = classKindCounts(c.id);
    return (isVideo ? kc.videos : kc.images) > 0;
  }).length >= 2;

  const radios = isVideo
    ? `<label><input type="radio" name="model-type" value="bilstm" checked>
         <span><b>Automático</b> — BiLSTM (recomendado)</span></label>
       <label><input type="radio" name="model-type" value="lstm">
         <span><b>Avançado</b> — LSTM</span></label>`
    : `<label><input type="radio" name="model-type" value="rf" checked>
         <span><b>Automático</b> — Random Forest</span></label>
       <label><input type="radio" name="model-type" value="mlp">
         <span><b>Avançado</b> — MLP (rede neural)</span></label>`;

  const description = isVideo
    ? `Cada vídeo vira uma <b>sequência temporal</b>: frames → landmarks das mãos →
       features normalizadas → rede recorrente (LSTM/BiLSTM). É o modo indicado para
       sinais com movimento.`
    : `Cada imagem vira landmarks das mãos (MediaPipe) → features normalizadas →
       classificador. Indicado para sinais estáticos (configurações de mão).`;

  const history = state.experiments.length
    ? `<h3 class="history-title">Histórico de experimentos</h3>
       ${state.experiments.map((e, i) => experimentHtml(e, i === 0 && state.justTrained)).join('')}`
    : '';

  return `
    <div class="panel">
      <h3>Treinamento</h3>
      <div class="media-tabs">
        <button class="media-tab ${isVideo ? '' : 'active'}"
                data-action="train-modality" data-modality="image">🖼 Imagens — estático</button>
        <button class="media-tab ${isVideo ? 'active' : ''}"
                data-action="train-modality" data-modality="video">🎥 Vídeos — temporal</button>
      </div>
      <p class="note">${description}</p>
      <div class="analysis">${datasetAnalysis(state.trainModality)}</div>
      ${lsaePanelHtml(isVideo)}
      <div class="train-controls">
        <div class="model-choice">${radios}</div>
        <div class="train-cta">
          <button class="btn btn-primary btn-lg" data-action="train"
                  ${trainable && !state.training ? '' : 'disabled'}>
            ⚡ Treinar modelo
          </button>
        </div>
      </div>
      <div id="train-progress" ${state.training ? '' : 'hidden'}>
        <div class="progress-track"><div class="progress-fill" id="train-bar"></div></div>
        <p class="progress-label" id="train-label">Iniciando…</p>
      </div>
    </div>
    ${history}`;
}

/* ===== Polling do treinamento ===== */
async function pollTraining(projectId) {
  clearTimeout(state.pollTimer);
  let status;
  try {
    status = await api.trainStatus(projectId);
  } catch (_) {
    state.pollTimer = setTimeout(() => pollTraining(projectId), 1200);
    return;
  }
  if (!state.project || state.project.id !== projectId) return;

  const bar = document.getElementById('train-bar');
  const label = document.getElementById('train-label');

  if (status.state === 'extracting') {
    if (bar && status.total) {
      bar.style.width = `${Math.round(90 * status.done / status.total)}%`;
      label.textContent = `Extraindo landmarks… ${status.done}/${status.total} exemplos`;
    }
  } else if (status.state === 'training') {
    if (bar) { bar.style.width = '95%'; label.textContent = 'Treinando o modelo…'; }
  } else if (status.state === 'done') {
    state.training = false;
    state.justTrained = true;
    toast('Modelo treinado com sucesso!', 'success');
    state.experiments = await api.listExperiments(projectId);
    state.testExpId = status.experiment_id;
    if (state.tab === 'treino') renderTab();
    state.justTrained = false;
    return;
  } else if (status.state === 'error') {
    state.training = false;
    toast(status.message || 'Falha no treinamento.', 'error');
    if (state.tab === 'treino') renderTab();
    return;
  }
  state.pollTimer = setTimeout(() => pollTraining(projectId), 700);
}

/* ===== Aba 03 — Análise de Experimentos ===== */
function updateComparisonDisplay() {
  const selA = document.querySelector('[data-role="exp-a"]');
  const selB = document.querySelector('[data-role="exp-b"]');
  const cont = document.querySelector('.comparison-container');
  if (!selA || !selB || !cont) return;

  const idA = Number(selA.value), idB = Number(selB.value);
  if (!idA || !idB || idA === idB) {
    cont.innerHTML = '<p class="note">ℹ Selecione 2 experimentos diferentes para comparar.</p>';
    return;
  }

  const expA = state.experiments.find(e => e.id === idA);
  const expB = state.experiments.find(e => e.id === idB);
  if (!expA || !expB) {
    cont.innerHTML = '<p class="note">Experimentos não encontrados.</p>';
    return;
  }

  cont.innerHTML = comparisonTableHtml(expA, expB);
}

function viewAnalysis() {
  if (!state.experiments.length) {
    return `<div class="panel"><h3>Análise</h3>
      <p class="note">⚠ Nenhum experimento disponível. Treine um modelo na aba anterior.</p></div>`;
  }

  const exp1 = state.experiments[0];
  const exp2 = state.experiments[1] || state.experiments[0];

  const html = `<div class="panel">
    <h3>Análise de Experimentos</h3>
    <div class="comparison-controls">
      <label>Experimento A:
        <select data-role="exp-a" onchange="updateComparisonDisplay()">
          ${state.experiments.map(e => `<option value="${e.id}" ${e.id === exp1.id ? 'selected' : ''}>#${String(e.id).padStart(3, '0')} (${MODEL_LABELS[e.model_type]}, acc ${pct(e.metrics.accuracy)})</option>`).join('')}
        </select>
      </label>
      <label>Experimento B:
        <select data-role="exp-b" onchange="updateComparisonDisplay()">
          ${state.experiments.map(e => `<option value="${e.id}" ${e.id === exp2.id ? 'selected' : ''}>#${String(e.id).padStart(3, '0')} (${MODEL_LABELS[e.model_type]}, acc ${pct(e.metrics.accuracy)})</option>`).join('')}
        </select>
      </label>
    </div>
    <div class="comparison-container"></div>
  </div>`;

  setTimeout(updateComparisonDisplay, 10);
  return html;
}

function comparisonTableHtml(expA, expB) {
  const mA = expA.metrics, mB = expB.metrics;
  const delta = (a, b) => {
    const d = b - a;
    if (Math.abs(d) < 0.001) return '<span class="delta-neutral">≈</span>';
    return d > 0 ? `<span class="delta-up">↑${pct(Math.abs(d))}</span>` : `<span class="delta-down">↓${pct(Math.abs(d))}</span>`;
  };

  return `
    <div class="comparison-grid">
      <div class="comparison-exp">
        <h4>#${String(expA.id).padStart(3, '0')}</h4>
        <p class="exp-type">${MODEL_MODALITY[expA.model_type] === 'video' ? '🎥' : '🖼'} ${MODEL_LABELS[expA.model_type]}</p>
        ${expA.metrics.lsae.enabled ? `<p class="lsae-badge on">LSAE ${expA.metrics.lsae.factor}x</p>` : '<p class="lsae-badge">LSAE OFF</p>'}
        <table class="metrics-table">
          <tr><td>Accuracy</td><td><b>${pct(mA.accuracy)}</b></td></tr>
          <tr><td>Precision</td><td><b>${pct(mA.precision)}</b></td></tr>
          <tr><td>Recall</td><td><b>${pct(mA.recall)}</b></td></tr>
          <tr><td>F1</td><td><b>${pct(mA.f1)}</b></td></tr>
          <tr><td>Treino / Teste</td><td><b>${mA.train_size} / ${mA.test_size}</b></td></tr>
          <tr><td>Tempo</td><td><b>${mA.train_seconds}s</b></td></tr>
        </table>
      </div>

      <div class="comparison-delta">
        <h4>Diferenças</h4>
        <table class="delta-table">
          <tr><td>Accuracy</td><td>${delta(mA.accuracy, mB.accuracy)}</td></tr>
          <tr><td>Precision</td><td>${delta(mA.precision, mB.precision)}</td></tr>
          <tr><td>Recall</td><td>${delta(mA.recall, mB.recall)}</td></tr>
          <tr><td>F1</td><td>${delta(mA.f1, mB.f1)}</td></tr>
        </table>
      </div>

      <div class="comparison-exp">
        <h4>#${String(expB.id).padStart(3, '0')}</h4>
        <p class="exp-type">${MODEL_MODALITY[expB.model_type] === 'video' ? '🎥' : '🖼'} ${MODEL_LABELS[expB.model_type]}</p>
        ${expB.metrics.lsae.enabled ? `<p class="lsae-badge on">LSAE ${expB.metrics.lsae.factor}x</p>` : '<p class="lsae-badge">LSAE OFF</p>'}
        <table class="metrics-table">
          <tr><td>Accuracy</td><td><b>${pct(mB.accuracy)}</b></td></tr>
          <tr><td>Precision</td><td><b>${pct(mB.precision)}</b></td></tr>
          <tr><td>Recall</td><td><b>${pct(mB.recall)}</b></td></tr>
          <tr><td>F1</td><td><b>${pct(mB.f1)}</b></td></tr>
          <tr><td>Treino / Teste</td><td><b>${mB.train_size} / ${mB.test_size}</b></td></tr>
          <tr><td>Tempo</td><td><b>${mB.train_seconds}s</b></td></tr>
        </table>
      </div>
    </div>

    <h4 style="margin-top: 2em;">Matrizes de Confusão</h4>
    <div class="comparison-grid">
      <div>
        <h5>#${String(expA.id).padStart(3, '0')}</h5>
        ${confusionHtml(mA.confusion)}
      </div>
      <div>
        <h5>#${String(expB.id).padStart(3, '0')}</h5>
        ${confusionHtml(mB.confusion)}
      </div>
    </div>
  `;
}

/* ===== Aba 04 — Teste ===== */
function currentTestExp() {
  return state.experiments.find(e => e.id === state.testExpId) || state.experiments[0];
}

function expSelectHtml() {
  return `
    <label class="exp-select">Modelo:
      <select data-role="test-exp">
        ${state.experiments.map(e => `
          <option value="${e.id}" ${e.id === state.testExpId ? 'selected' : ''}>
            #${String(e.id).padStart(3, '0')} — ${MODEL_MODALITY[e.model_type] === 'video' ? '🎥' : '🖼'}
            ${MODEL_LABELS[e.model_type]} (accuracy ${pct(e.metrics.accuracy)})
          </option>`).join('')}
      </select>
    </label>`;
}

function testResultHtml() {
  const r = state.testResult;
  if (!r) return '';
  if (r.loading) return '<div class="loading">Processando…</div>';
  if (!r.predictions.length) {
    return `<div class="analysis-item warn"><span>⚠</span><span>${esc(r.message || 'Nenhuma mão detectada.')}</span></div>`;
  }
  const top = r.predictions[0];
  const detail = r.stats
    ? `${r.stats.frames_with_hands}/${r.stats.frames_sampled} frames com mãos · ` +
      (r.stats.duration_s ? `${r.stats.duration_s}s de vídeo · ` : '') +
      `processado em ${r.stats.process_seconds}s`
    : `${plural(r.hands_detected, 'mão detectada', 'mãos detectadas')} na imagem.`;
  return `
    <div class="pred-main">
      <span class="pred-class">${esc(top.class)}</span>
      <span class="pred-prob">${pct(top.prob)}</span>
    </div>
    <div class="prob-list">
      ${r.predictions.map(p => `
        <div class="prob-row">
          <span class="prob-label">${esc(p.class)}</span>
          <div class="prob-track"><div class="prob-fill" style="width:${Math.max(1, p.prob * 100)}%"></div></div>
          <span class="prob-value">${pct(p.prob)}</span>
        </div>`).join('')}
    </div>
    <p class="hint">${detail}</p>`;
}

function viewTest() {
  if (!state.experiments.length) {
    return `
      <div class="panel">
        <h3>Teste</h3>
        <p class="note">Nenhum modelo treinado ainda. Vá para a etapa
           <b>02 — Treinamento</b> e clique em "⚡ Treinar modelo".</p>
      </div>`;
  }
  const exp = currentTestExp();
  const temporal = MODEL_MODALITY[exp.model_type] === 'video';
  const inputButtons = temporal
    ? `<button class="btn btn-ghost" data-action="test-upload">📁 Escolher vídeo</button>
       <button class="btn btn-ghost" data-action="test-cam-open">🎥 Gravar da webcam</button>
       <button class="btn btn-ghost" data-action="test-cam-stream">🎬 Reconhecimento contínuo</button>
       <span class="hint">ou arraste um vídeo aqui</span>`
    : `<button class="btn btn-ghost" data-action="test-upload">📁 Escolher imagem</button>
       <button class="btn btn-ghost" data-action="test-cam-open">📷 Usar webcam</button>
       <button class="btn btn-ghost" data-action="test-cam-stream">🎬 Reconhecimento contínuo</button>
       <span class="hint">ou arraste uma imagem aqui</span>`;
  const camButton = temporal
    ? `<button class="btn btn-primary" data-action="test-cam-record">⏺ Gravar sinal</button>`
    : `<button class="btn btn-primary" data-action="test-cam-shot">Capturar e reconhecer</button>`;

  return `
    <div class="panel">
      <h3>Teste</h3>
      <p class="note">${temporal
        ? 'Envie um vídeo ou grave o sinal pela webcam para reconhecê-lo com o modelo temporal.'
        : 'Envie uma imagem ou use a webcam para reconhecer um sinal com o modelo treinado.'}</p>
      ${expSelectHtml()}
      <div class="test-input test-drop">${inputButtons}</div>
      <div id="test-cam" class="test-cam" hidden>
        <div class="webcam-stage">
          <video autoplay playsinline muted></video>
          <canvas id="recognition-canvas" class="recognition-canvas"></canvas>
          <span class="rec-dot">REC</span>
        </div>
        ${getCameraSelectorHtml()}
        <div class="test-cam-actions">
          ${camButton}
          <button class="btn btn-ghost" data-action="test-cam-close">Fechar câmera</button>
        </div>
      </div>
      <div id="test-result">${testResultHtml()}</div>
    </div>`;
}

function drawPredictionOnCanvas() {
  const canvas = document.getElementById('recognition-canvas');
  const video = canvas?.parentElement?.querySelector('video');
  if (!canvas || !video || !state.testResult) return;

  const ctx = canvas.getContext('2d');
  canvas.width = video.offsetWidth;
  canvas.height = video.offsetHeight;

  // Limpar canvas
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const r = state.testResult;
  if (!r || r.loading) return;

  const top = r.predictions[0];
  if (!top) return;

  // Desenhar landmarks das mãos se disponíveis
  if (r.landmarks && r.landmarks.length > 0) {
    ctx.strokeStyle = '#4f46e5';
    ctx.fillStyle = '#4f46e5';
    ctx.lineWidth = 2;

    // Conectar keypoints (skeleton das mãos)
    const connections = [
      [0, 1], [1, 2], [2, 3], [3, 4],           // Polegar
      [0, 5], [5, 6], [6, 7], [7, 8],           // Indicador
      [0, 9], [9, 10], [10, 11], [11, 12],     // Médio
      [0, 13], [13, 14], [14, 15], [15, 16],   // Anelar
      [0, 17], [17, 18], [18, 19], [19, 20],   // Mínimo
      [5, 9], [9, 13], [13, 17]                 // Conexões entre dedos
    ];

    // Desenhar conexões
    ctx.strokeStyle = 'rgba(79, 70, 229, 0.6)';
    for (const [start, end] of connections) {
      if (r.landmarks[start] && r.landmarks[end]) {
        const p1 = r.landmarks[start];
        const p2 = r.landmarks[end];
        ctx.beginPath();
        ctx.moveTo(p1[0] * canvas.width, p1[1] * canvas.height);
        ctx.lineTo(p2[0] * canvas.width, p2[1] * canvas.height);
        ctx.stroke();
      }
    }

    // Desenhar pontos dos keypoints
    ctx.fillStyle = '#4f46e5';
    for (const point of r.landmarks) {
      const x = point[0] * canvas.width;
      const y = point[1] * canvas.height;
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Desenhar texto com classe e confiança (no topo, sem inversão)
  const text = `${top.class} - ${pct(top.prob)}`;
  ctx.fillStyle = 'white';
  ctx.font = 'bold 24px Arial';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.shadowColor = 'rgba(0, 0, 0, 0.8)';
  ctx.shadowBlur = 10;
  ctx.shadowOffsetX = 2;
  ctx.shadowOffsetY = 2;

  // Posicionar texto no topo sem inversão
  const textY = 20;
  ctx.fillText(text, canvas.width / 2, textY);

  // Remover sombra para próximas operações
  ctx.shadowColor = 'transparent';
}

async function runPrediction(file) {
  if (!state.testExpId) return;
  state.testResult = { loading: true };
  const box = document.getElementById('test-result');
  if (box) box.innerHTML = testResultHtml();
  drawPredictionOnCanvas();
  try {
    state.testResult = await api.predict(state.testExpId, file);
  } catch (err) {
    state.testResult = null;
    toast('Falha no reconhecimento: ' + err.message, 'error');
  }
  const box2 = document.getElementById('test-result');
  if (box2) box2.innerHTML = testResultHtml();
  drawPredictionOnCanvas();
}

async function listAvailableCameras() {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    state.availableCameras = devices.filter(d => d.kind === 'videoinput');
    if (state.availableCameras.length > 0 && !state.selectedCameraId) {
      state.selectedCameraId = state.availableCameras[0].deviceId;
    }
    return state.availableCameras;
  } catch (err) {
    console.error('Erro ao listar câmeras:', err);
    return [];
  }
}

function getCameraSelectorHtml() {
  if (state.availableCameras.length <= 1) return '';
  return `
    <div class="camera-selector">
      <label>Câmera:</label>
      <select data-action="select-camera">
        ${state.availableCameras.map(cam => `
          <option value="${cam.deviceId}" ${cam.deviceId === state.selectedCameraId ? 'selected' : ''}>
            ${cam.label || `Câmera ${state.availableCameras.indexOf(cam) + 1}`}
          </option>
        `).join('')}
      </select>
    </div>`;
}

async function openTestCam() {
  const wrap = document.getElementById('test-cam');
  if (!wrap) return;

  // Atualizar lista de câmeras se ainda não carregou
  if (state.availableCameras.length === 0) {
    await listAvailableCameras();
    // Se houver múltiplas câmeras, re-renderizar para mostrar o seletor
    if (state.availableCameras.length > 1) {
      const newHtml = getCameraSelectorHtml();
      const existingSelector = wrap.querySelector('.camera-selector');
      if (newHtml && !existingSelector) {
        const actionsDiv = wrap.querySelector('.test-cam-actions');
        if (actionsDiv) {
          actionsDiv.insertAdjacentHTML('beforebegin', newHtml);
        }
      }
    }
  }

  try {
    const constraints = {
      video: {
        width: 640,
        height: 480,
        ...(state.selectedCameraId && { deviceId: { exact: state.selectedCameraId } })
      },
      audio: false,
    };
    state.testStream = await navigator.mediaDevices.getUserMedia(constraints);
  } catch (err) {
    toast('Não foi possível acessar a webcam: ' + err.message, 'error');
    return;
  }
  wrap.hidden = false;
  wrap.querySelector('video').srcObject = state.testStream;
}

function shootTestCam() {
  const wrap = document.getElementById('test-cam');
  const video = wrap && wrap.querySelector('video');
  if (!video || !video.videoWidth) return;
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  canvas.toBlob(blob => {
    if (blob) runPrediction(new File([blob], 'webcam_teste.jpg'));
  }, 'image/jpeg', 0.92);
}

async function startContinuousRecognition() {
  const wrap = document.getElementById('test-cam');
  if (!wrap) return;

  // Atualizar lista de câmeras se ainda não carregou
  if (state.availableCameras.length === 0) {
    await listAvailableCameras();
    // Se houver múltiplas câmeras, adicionar o seletor
    if (state.availableCameras.length > 1) {
      const newHtml = getCameraSelectorHtml();
      const existingSelector = wrap.querySelector('.camera-selector');
      if (newHtml && !existingSelector) {
        const actionsDiv = wrap.querySelector('.test-cam-actions');
        if (actionsDiv) {
          actionsDiv.insertAdjacentHTML('beforebegin', newHtml);
        }
      }
    }
  }

  try {
    if (!state.testStream) {
      const constraints = {
        video: {
          width: 640,
          height: 480,
          ...(state.selectedCameraId && { deviceId: { exact: state.selectedCameraId } })
        },
        audio: false,
      };
      state.testStream = await navigator.mediaDevices.getUserMedia(constraints);
    }
  } catch (err) {
    toast('Não foi possível acessar a webcam: ' + err.message, 'error');
    return;
  }

  wrap.hidden = false;
  const video = wrap.querySelector('video');
  if (!video) return;
  video.srcObject = state.testStream;

  // Renderizar UI de streaming
  const actions = wrap.querySelector('.test-cam-actions');
  if (actions) {
    actions.innerHTML = `
      <button class="btn btn-primary" data-action="test-stream-stop">⏹ Parar reconhecimento</button>
      <div id="stream-predictions" class="stream-predictions"></div>`;
  }

  // Iniciar polling de frames
  state.streamInterval = setInterval(async () => {
    if (!state.testStream || video.paused) {
      clearInterval(state.streamInterval);
      return;
    }
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    canvas.toBlob(blob => {
      if (blob && state.testExpId) {
        api.predict(state.testExpId, new File([blob], 'stream_frame.jpg'))
          .then(result => {
            state.testResult = result;
            drawPredictionOnCanvas();
            const pred = document.getElementById('stream-predictions');
            if (pred && result.predictions && result.predictions.length) {
              const top = result.predictions[0];
              pred.innerHTML = `<div class="stream-top"><span>${esc(top.class)}</span> <b>${pct(top.prob)}</b></div>`;
            }
          })
          .catch(() => {});
      }
    }, 'image/jpeg', 0.85);
  }, 1000); // 1 frame por segundo
}

function toggleTestRecording(button) {
  if (state.testRecorder) {          // parar e reconhecer
    state.testRecorder.stop();
    return;
  }
  if (!state.testStream) return;
  const chunks = [];
  const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
    ? 'video/webm;codecs=vp9' : 'video/webm';
  const recorder = new MediaRecorder(state.testStream, { mimeType: mime });
  recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
  recorder.onstop = () => {
    state.testRecorder = null;
    const wrap = document.getElementById('test-cam');
    if (wrap) {
      wrap.querySelector('.rec-dot').style.display = 'none';
      const btn = wrap.querySelector('[data-action="test-cam-record"]');
      if (btn) btn.textContent = '⏺ Gravar sinal';
    }
    const blob = new Blob(chunks, { type: 'video/webm' });
    runPrediction(new File([blob], 'webcam_teste.webm'));
  };
  recorder.start();
  state.testRecorder = recorder;
  const wrap = document.getElementById('test-cam');
  if (wrap) wrap.querySelector('.rec-dot').style.display = 'flex';
  button.textContent = '⏹ Parar e reconhecer';
}

/* ===== Aba 04 — Exportar ===== */
function viewExport() {
  if (!state.experiments.length) {
    return `
      <div class="panel">
        <h3>Exportar</h3>
        <p class="note">Nenhum modelo treinado ainda. Treine um modelo na etapa
           <b>02 — Treinamento</b> para poder exportá-lo.</p>
      </div>`;
  }
  return `
    <div class="panel">
      <h3>Exportar</h3>
      <p class="note">
        O pacote exportado (.zip) contém o modelo (<code>model.joblib</code> para
        Random Forest/MLP, <code>model.keras</code> para LSTM/BiLSTM) e
        <code>metadata.json</code> com classes, configuração de features, normalização
        e métricas — pronto para ser carregado em outra aplicação Python.
      </p>
      <div class="export-list">
        ${state.experiments.map(e => `
          <div class="export-row">
            <span class="exp-id">#${String(e.id).padStart(3, '0')}</span>
            <span class="exp-model">${MODEL_MODALITY[e.model_type] === 'video' ? '🎥' : '🖼'} ${MODEL_LABELS[e.model_type]}</span>
            <span class="exp-date">${formatDate(e.created_at)}</span>
            <span class="exp-metric">Accuracy <b>${pct(e.metrics.accuracy)}</b></span>
            <a class="btn btn-primary btn-sm" href="${api.exportUrl(e.id)}">⬇ Exportar</a>
          </div>`).join('')}
      </div>
      <p class="note">Exportação para TensorFlow.js e ONNX chega junto com os modelos temporais (Fase 3+).</p>
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
      stopTestCam();
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

    } else if (action === 'media-tab') {
      state.mediaTab = target.dataset.kind;
      renderTab();

    } else if (action === 'upload') {
      state.uploadClassId = Number(id);
      $fileInput.accept = state.mediaTab === 'video'
        ? '.mp4,.avi,.mov,.mkv,.webm'
        : '.jpg,.jpeg,.png,.bmp,.webp';
      $fileInput.value = '';
      $fileInput.click();

    } else if (action === 'webcam') {
      Webcam.open(Number(id), name, captured => {
        if (captured > 0) toast(`${captured} captura(s) adicionada(s).`, 'success');
        refreshProject();
      }, state.mediaTab === 'video' ? 'video' : 'photo');

    } else if (action === 'del-example') {
      await api.deleteExample(id);
      refreshProject();

    } else if (action === 'train-modality') {
      state.trainModality = target.dataset.modality;
      renderTab();

    } else if (action === 'train') {
      const modelType = document.querySelector('input[name="model-type"]:checked').value;
      await api.startTrain(state.project.id, modelType, state.lsae);
      state.training = true;
      renderTab();
      pollTraining(state.project.id);

    } else if (action === 'test-upload') {
      const temporal = MODEL_MODALITY[currentTestExp().model_type] === 'video';
      $testFileInput.accept = temporal
        ? '.mp4,.avi,.mov,.mkv,.webm'
        : '.jpg,.jpeg,.png,.bmp,.webp';
      $testFileInput.value = '';
      $testFileInput.click();

    } else if (action === 'test-cam-open') {
      openTestCam();

    } else if (action === 'test-cam-shot') {
      shootTestCam();

    } else if (action === 'test-cam-record') {
      toggleTestRecording(target);

    } else if (action === 'test-cam-close') {
      stopTestCam();
      const wrap = document.getElementById('test-cam');
      if (wrap) wrap.hidden = true;

    } else if (action === 'test-cam-stream') {
      startContinuousRecognition();

    } else if (action === 'test-stream-stop') {
      clearInterval(state.streamInterval);
      stopTestCam();
      const wrap = document.getElementById('test-cam');
      if (wrap) wrap.hidden = true;
      toast('Reconhecimento contínuo encerrado.', 'success');
    }
  } catch (err) {
    toast(err.message, 'error');
  }
});

$app.addEventListener('change', async e => {
  const select = e.target.closest('[data-role="test-exp"]');
  if (select) {
    state.testExpId = Number(select.value);
    state.testResult = null;
    stopTestCam();
    renderTab();  // os controles mudam conforme a modalidade do experimento
    return;
  }
  const lsaeInput = e.target.closest('[data-lsae]');
  if (lsaeInput) {
    const key = lsaeInput.dataset.lsae;
    if (key === 'intensity') state.lsae.intensity = Number(lsaeInput.value) / 100;
    else if (key === 'factor') state.lsae.factor = Number(lsaeInput.value);
    else state.lsae[key] = lsaeInput.checked;
    renderTab();  // atualiza visibilidade/estado dos controles
    return;
  }
  const cameraSelect = e.target.closest('[data-action="select-camera"]');
  if (cameraSelect) {
    state.selectedCameraId = cameraSelect.value;
    // Reiniciar stream com nova câmera se estiver aberto
    if (state.testStream) {
      state.testStream.getTracks().forEach(track => track.stop());
      state.testStream = null;
      await openTestCam();
    }
  }
});

$fileInput.addEventListener('change', async () => {
  const files = [...$fileInput.files];
  if (!files.length || !state.uploadClassId) return;
  await uploadFiles(state.uploadClassId, files);
});

$testFileInput.addEventListener('change', () => {
  const file = $testFileInput.files[0];
  if (file) runPrediction(file);
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

/* ===== Drag & drop (classes e teste) ===== */
$app.addEventListener('dragover', e => {
  const zone = e.target.closest('.class-card, .test-drop');
  if (!zone) return;
  e.preventDefault();
  zone.classList.add('dragover');
});

$app.addEventListener('dragleave', e => {
  const zone = e.target.closest('.class-card, .test-drop');
  if (zone && !zone.contains(e.relatedTarget)) zone.classList.remove('dragover');
});

$app.addEventListener('drop', e => {
  const card = e.target.closest('.class-card');
  const testZone = e.target.closest('.test-drop');
  if (!card && !testZone) return;
  e.preventDefault();
  const files = [...e.dataTransfer.files];
  if (card) {
    card.classList.remove('dragover');
    if (files.length) uploadFiles(Number(card.dataset.classId), files);
  } else {
    testZone.classList.remove('dragover');
    if (files.length) runPrediction(files[0]);
  }
});

/* ===== Início ===== */
route();
