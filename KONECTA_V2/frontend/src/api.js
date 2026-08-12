// Cliente da API do KONECTA V2 (REST via proxy do Vite + WebSocket).

export async function obterAnalise() {
  const r = await fetch('/api/analise')
  if (r.status === 404) return null
  if (!r.ok) throw new Error(`Erro ${r.status} ao buscar análise`)
  return r.json()
}

export async function obterFontes() {
  const r = await fetch('/api/fontes')
  if (!r.ok) throw new Error('Backend indisponível')
  const { fontes } = await r.json()
  return fontes
}

export async function obterRelatorio() {
  const r = await fetch('/api/analise/relatorio')
  if (!r.ok) throw new Error('Nenhuma análise disponível')
  return r.text()
}

export async function interpretarComIA(tipo = 'dataset') {
  const r = await fetch(`/api/analise/interpretar?tipo=${tipo}`, { method: 'POST' })
  if (!r.ok) {
    const erro = await r.json()
    throw new Error(erro.detail || 'Erro na interpretação com IA')
  }
  return r.json()
}

// === Capture Engine / Pipeline (Etapas 4-6) ===
// Importante: a captura por webcam roda no HOST do backend (cv2.VideoCapture),
// não na câmera do navegador — pensado para uso local/desktop.

async function post(caminho, params = {}) {
  const qs = new URLSearchParams(params).toString()
  const r = await fetch(`${caminho}${qs ? `?${qs}` : ''}`, { method: 'POST' })
  if (!r.ok) {
    const erro = await r.json().catch(() => ({}))
    throw new Error(erro.detail || `Erro ${r.status} em ${caminho}`)
  }
  return r.json()
}

export function iniciarSessaoCaptura(idSessao, sinal, sinalizante) {
  return post('/api/captura/sessao', { id_sessao: idSessao, sinal, sinalizante })
}

export function capturarWebcam(idSessao, duracaoSegundos = 5.0) {
  return post(`/api/captura/sessao/${idSessao}/webcam`, { duracao_segundos: duracaoSegundos })
}

export function validarCaptura(idSessao) {
  return post(`/api/captura/sessao/${idSessao}/validar`)
}

export function processarPipeline(idSessao, sinal, sinalizante) {
  return post('/api/pipeline/processar', { id_sessao: idSessao, sinal, sinalizante })
}

export async function obterTrajetoria(idSessao) {
  const r = await fetch(`/api/pipeline/sessao/${idSessao}/trajetoria`)
  if (!r.ok) {
    const erro = await r.json().catch(() => ({}))
    throw new Error(erro.detail || 'Análise de trajetória não encontrada')
  }
  return r.json()
}

// Dispara a análise via WebSocket e devolve o socket (permite cancelar).
export function executarAnalise(fonte, { onProgresso, onConcluido, onErro }) {
  const protocolo = location.protocol === 'https:' ? 'wss' : 'ws'
  // Usa o mesmo host da página (respeita o proxy do Vite em dev e funciona
  // em qualquer deploy, em vez de depender de localhost:8000 fixo).
  const ws = new WebSocket(`${protocolo}://${location.host}/ws/analise`)
  ws.onopen = () => ws.send(JSON.stringify({ fonte }))
  ws.onmessage = (evento) => {
    const msg = JSON.parse(evento.data)
    if (msg.tipo === 'progresso') onProgresso(msg.mensagem)
    else if (msg.tipo === 'concluido') onConcluido(msg.analise)
    else if (msg.tipo === 'erro') onErro(msg.mensagem)
  }
  ws.onerror = () => onErro('Falha na conexão com o backend')
  return ws
}
