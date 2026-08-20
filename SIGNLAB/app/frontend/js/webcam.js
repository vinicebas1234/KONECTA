/* Captura de exemplos pela webcam: foto (clique ou rajada) e vídeo. */
const Webcam = (() => {
  let stream = null;
  let recorder = null;
  let chunks = [];
  let burstTimer = null;
  let classId = null;
  let mode = 'photo';
  let captured = 0;
  let onCloseCb = null;
  let overlay = null;
  // Camera escolhida na gravacao. Sem isto o navegador usa sempre a padrao,
  // que costuma ser a do notebook mesmo com uma externa melhor plugada.
  let cameraId = null;

  function el(id) { return overlay.querySelector(id); }

  async function open(cid, className, onClose, initialMode = 'photo') {
    classId = cid;
    onCloseCb = onClose;
    mode = 'photo';
    captured = 0;

    overlay = document.createElement('div');
    overlay.className = 'overlay';
    overlay.innerHTML = `
      <div class="modal webcam-modal">
        <h3>Webcam — ${className}</h3>
        <div class="webcam-camera-pick">
          <label>Câmera:</label>
          <select data-cameras></select>
        </div>
        <div class="webcam-stage">
          <video autoplay playsinline muted></video>
          <span class="rec-dot">REC</span>
        </div>
        <div class="webcam-controls">
          <div class="mode-toggle">
            <button data-mode="photo" class="active">📷 Foto</button>
            <button data-mode="video">🎥 Vídeo</button>
          </div>
          <span class="webcam-count">0 capturas nesta sessão</span>
          <div style="display:flex;gap:8px">
            <button class="btn btn-primary" data-act="capture">Capturar</button>
            <button class="btn btn-ghost" data-act="close">Concluir</button>
          </div>
        </div>
        <p class="webcam-hint" data-hint>
          Clique para capturar uma foto — segure o botão para capturar em rajada.
        </p>
      </div>`;
    document.getElementById('modal-root').appendChild(overlay);

    overlay.addEventListener('click', onClick);
    const capBtn = el('[data-act="capture"]');
    capBtn.addEventListener('pointerdown', onHoldStart);
    capBtn.addEventListener('pointerup', onHoldEnd);
    capBtn.addEventListener('pointerleave', onHoldEnd);

    if (initialMode !== 'photo') setMode(initialMode);

    try {
      await iniciarCamera();
      await listarCameras();
    } catch (err) {
      toast('Não foi possível acessar a webcam: ' + err.message, 'error');
      close();
    }
  }

  /* Abre (ou reabre) o stream na camera escolhida. */
  async function iniciarCamera() {
    if (stream) stream.getTracks().forEach(t => t.stop());
    const video = { width: 640, height: 480 };
    if (cameraId) video.deviceId = { exact: cameraId };
    stream = await navigator.mediaDevices.getUserMedia({ video, audio: false });
    el('video').srcObject = stream;
    // o deviceId real so' aparece depois que o stream abre
    if (!cameraId) {
      const trilha = stream.getVideoTracks()[0];
      cameraId = trilha && trilha.getSettings ? trilha.getSettings().deviceId : null;
    }
  }

  /* Preenche o seletor. Os rotulos so' vem depois de permissao concedida,
     por isso listamos DEPOIS de abrir o stream. */
  async function listarCameras() {
    const seletor = el('[data-cameras]');
    if (!seletor) return;
    const dispositivos = await navigator.mediaDevices.enumerateDevices();
    const cameras = dispositivos.filter(d => d.kind === 'videoinput');
    if (cameras.length < 2) {
      seletor.closest('.webcam-camera-pick').style.display = 'none';
      return;
    }
    seletor.innerHTML = cameras.map((c, i) =>
      `<option value="${c.deviceId}"${c.deviceId === cameraId ? ' selected' : ''}>` +
      `${c.label || 'Câmera ' + (i + 1)}</option>`).join('');
    seletor.addEventListener('change', async () => {
      if (recorder) toggleRecord();   // nao troca no meio de uma gravacao
      cameraId = seletor.value;
      try {
        await iniciarCamera();
      } catch (err) {
        toast('Não foi possível abrir esta câmera: ' + err.message, 'error');
      }
    });
  }

  function onClick(e) {
    const modeBtn = e.target.closest('[data-mode]');
    if (modeBtn) return setMode(modeBtn.dataset.mode);
    const act = e.target.closest('[data-act]');
    if (!act) return;
    if (act.dataset.act === 'close') return close();
    if (act.dataset.act === 'capture' && mode === 'video') toggleRecord();
  }

  function setMode(m) {
    if (recorder) toggleRecord();
    mode = m;
    overlay.querySelectorAll('[data-mode]').forEach(b =>
      b.classList.toggle('active', b.dataset.mode === m));
    el('[data-act="capture"]').textContent = m === 'photo' ? 'Capturar' : 'Gravar';
    el('[data-hint]').textContent = m === 'photo'
      ? 'Clique para capturar uma foto — segure o botão para capturar em rajada.'
      : 'Clique em Gravar para iniciar e clique novamente para encerrar o vídeo.';
  }

  /* --- foto --- */
  function onHoldStart() {
    if (mode !== 'photo') return;
    capturePhoto();
    burstTimer = setTimeout(function tick() {
      capturePhoto();
      burstTimer = setTimeout(tick, 200);
    }, 450);
  }

  function onHoldEnd() {
    clearTimeout(burstTimer);
    burstTimer = null;
  }

  function capturePhoto() {
    const video = el('video');
    if (!video.videoWidth) return;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    canvas.toBlob(blob => {
      if (blob) upload(blob, `captura_${Date.now()}.jpg`);
    }, 'image/jpeg', 0.92);
  }

  /* --- vídeo --- */
  function toggleRecord() {
    if (recorder) {
      recorder.stop();
      return;
    }
    chunks = [];
    const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
      ? 'video/webm;codecs=vp9' : 'video/webm';
    recorder = new MediaRecorder(stream, { mimeType: mime });
    recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: 'video/webm' });
      upload(blob, `captura_${Date.now()}.webm`);
      recorder = null;
      el('.rec-dot').style.display = 'none';
      el('[data-act="capture"]').textContent = 'Gravar';
    };
    recorder.start();
    el('.rec-dot').style.display = 'flex';
    el('[data-act="capture"]').textContent = 'Parar';
  }

  /* --- envio --- */
  async function upload(blob, filename) {
    try {
      await api.uploadExamples(classId, [new File([blob], filename)], 'webcam');
      captured++;
      el('.webcam-count').textContent =
        `${captured} captura${captured === 1 ? '' : 's'} nesta sessão`;
    } catch (err) {
      toast('Falha ao salvar captura: ' + err.message, 'error');
    }
  }

  function close() {
    if (recorder) { try { recorder.stop(); } catch (_) {} recorder = null; }
    onHoldEnd();
    if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    overlay.remove();
    overlay = null;
    if (onCloseCb) onCloseCb(captured);
  }

  return { open };
})();
