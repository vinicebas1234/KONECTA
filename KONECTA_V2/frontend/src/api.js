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

// Dispara a análise via WebSocket e devolve o socket (permite cancelar).
export function executarAnalise(fonte, { onProgresso, onConcluido, onErro }) {
  const protocolo = location.protocol === 'https:' ? 'wss' : 'ws'
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
