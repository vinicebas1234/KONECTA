import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { executarAnalise, obterAnalise, obterFontes } from './api.js'
import Dashboard from './pages/Dashboard.jsx'
import Reconhecimento from './pages/Reconhecimento.jsx'
import Tracking from './pages/Tracking.jsx'
import Treinar from './pages/Treinar.jsx'
import Qualidade from './pages/Qualidade.jsx'
import Perfis from './pages/Perfis.jsx'
import Recomendacoes from './pages/Recomendacoes.jsx'
import Relatorio from './pages/Relatorio.jsx'

const PAGINAS = [
  { id: 'dashboard', rotulo: 'Dashboard', Componente: Dashboard },
  { id: 'reconhecimento', rotulo: 'Reconhecimento', Componente: Reconhecimento },
  { id: 'tracking', rotulo: 'Tracking', Componente: Tracking },
  { id: 'treinar', rotulo: 'Treinar Sinais', Componente: Treinar },
  { id: 'qualidade', rotulo: 'Qualidade', Componente: Qualidade },
  { id: 'perfis', rotulo: 'Perfis', Componente: Perfis },
  { id: 'recomendacoes', rotulo: 'Recomendações', Componente: Recomendacoes },
  { id: 'relatorio', rotulo: 'Relatório', Componente: Relatorio },
]

const ROTULOS_FONTE = {
  v1_dinamicos: 'Dataset V1 — dinâmicos',
  v1_estaticos: 'Dataset V1 — estáticos',
  sintetico: 'Sintético (demonstração)',
}

export default function App() {
  const [pagina, setPagina] = useState('dashboard')
  const [analise, setAnalise] = useState(null)
  const [fontes, setFontes] = useState({})
  const [fonte, setFonte] = useState('sintetico')
  const [carregando, setCarregando] = useState(false)
  const [progresso, setProgresso] = useState([])
  const [erro, setErro] = useState(null)
  const [backendOk, setBackendOk] = useState(null)
  const fimProgressoRef = useRef(null)

  useEffect(() => {
    obterFontes()
      .then((f) => {
        setFontes(f)
        setBackendOk(true)
        if (f.v1_dinamicos) setFonte('v1_dinamicos')
      })
      .catch(() => setBackendOk(false))
    obterAnalise().then((a) => a && setAnalise(a)).catch(() => {})
  }, [])

  useEffect(() => {
    fimProgressoRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [progresso])

  function analisar() {
    setCarregando(true)
    setProgresso([])
    setErro(null)
    executarAnalise(fonte, {
      onProgresso: (m) => setProgresso((p) => [...p, m]),
      onConcluido: (a) => {
        setAnalise(a)
        setCarregando(false)
      },
      onErro: (m) => {
        setErro(m)
        setCarregando(false)
      },
    })
  }

  const { Componente } = PAGINAS.find((p) => p.id === pagina)

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 border-r border-line flex flex-col">
        <div className="px-5 py-5 border-b border-line">
          <h1 className="text-lg font-bold tracking-tight">
            KONECTA <span className="text-serie">V2</span>
          </h1>
          <p className="text-[11px] text-muted mt-0.5">Plataforma de pesquisa em Libras</p>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {PAGINAS.map((p) => (
            <button
              key={p.id}
              onClick={() => setPagina(p.id)}
              className={`w-full text-left text-sm px-3 py-2 rounded-lg transition-colors ${
                pagina === p.id
                  ? 'bg-serie/15 text-ink'
                  : 'text-ink2 hover:bg-white/5'
              }`}
            >
              {p.rotulo}
            </button>
          ))}
        </nav>
        <div className="p-4 border-t border-line text-[11px] text-muted">
          {backendOk === null && 'Conectando ao backend…'}
          {backendOk === true && (
            <span className="text-ink2">● <span className="text-good">API conectada</span> — Knowledge Engine</span>
          )}
          {backendOk === false && (
            <span className="text-critical">✕ Backend indisponível (porta 8000)</span>
          )}
        </div>
      </aside>

      {/* Conteudo */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center justify-between gap-4 px-6 py-4 border-b border-line">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-ink">
              {PAGINAS.find((p) => p.id === pagina).rotulo}
            </h2>
            {analise && (
              <p className="text-[11px] text-muted truncate">
                Fonte: {ROTULOS_FONTE[analise.fonte] ?? analise.fonte} · analisado em{' '}
                {new Date(analise.gerada_em).toLocaleString('pt-BR')}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <select
              value={fonte}
              onChange={(e) => setFonte(e.target.value)}
              disabled={carregando}
              className="bg-surface border border-white/10 rounded-lg text-sm px-3 py-1.5 text-ink2"
            >
              {Object.entries(fontes)
                .filter(([, disponivel]) => disponivel)
                .map(([id]) => (
                  <option key={id} value={id}>{ROTULOS_FONTE[id] ?? id}</option>
                ))}
            </select>
            <button
              onClick={analisar}
              disabled={carregando || backendOk !== true}
              className="bg-serie hover:bg-serie/85 disabled:opacity-40 text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors"
            >
              {carregando ? 'Analisando…' : 'Analisar dataset'}
            </button>
          </div>
        </header>

        {erro && (
          <div className="mx-6 mt-4 border border-critical/40 bg-critical/10 text-sm text-ink rounded-lg px-4 py-2">
            Erro na análise: {erro}
          </div>
        )}

        <main className="flex-1 overflow-y-auto p-6">
          {/* key={pagina} remonta e anima a entrada a cada troca de pagina;
              sem AnimatePresence (exit preso com StrictMode, ver acima). */}
          <motion.div
            key={pagina}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15 }}
          >
            <Componente analise={analise} />
          </motion.div>
        </main>
      </div>

      {/* Painel de progresso do Knowledge Engine (WebSocket).
          Renderizacao condicional pura (sem AnimatePresence): o exit do
          overlay pode ficar preso no DOM com StrictMode e, invisivel,
          bloquearia os cliques da pagina inteira. */}
      {carregando && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          >
            <motion.div
              initial={{ scale: 0.96 }}
              animate={{ scale: 1 }}
              className="bg-surface border border-white/10 rounded-xl w-[480px] max-w-[90vw] p-6"
            >
              <h3 className="text-sm font-semibold text-ink">Knowledge Engine em execução</h3>
              <p className="text-xs text-muted mt-0.5">{ROTULOS_FONTE[fonte] ?? fonte}</p>
              <div className="mt-4 max-h-56 overflow-y-auto space-y-1.5 pr-1">
                {progresso.map((m, i) => (
                  <p key={i} className="text-xs text-ink2 flex gap-2">
                    <span className={i === progresso.length - 1 ? 'text-serie' : 'text-good'}>
                      {i === progresso.length - 1 ? '›' : '✓'}
                    </span>
                    {m}
                  </p>
                ))}
                <div ref={fimProgressoRef} />
              </div>
            </motion.div>
          </motion.div>
      )}
    </div>
  )
}
