import { motion } from 'framer-motion'

export function Card({ children, className = '' }) {
  return (
    <div className={`bg-surface border border-white/10 rounded-xl p-5 ${className}`}>
      {children}
    </div>
  )
}

export function SectionTitle({ children, sub }) {
  return (
    <div className="mb-4">
      <h2 className="text-base font-semibold text-ink">{children}</h2>
      {sub && <p className="text-xs text-muted mt-0.5">{sub}</p>}
    </div>
  )
}

export function StatTile({ label, value, sub }) {
  return (
    <Card>
      <p className="text-xs text-muted uppercase tracking-wide">{label}</p>
      <p className="text-3xl font-semibold text-ink mt-1">{value}</p>
      {sub && <p className="text-xs text-ink2 mt-1">{sub}</p>}
    </Card>
  )
}

const CORES_PRIORIDADE = {
  alta: 'text-critical border-critical/40',
  media: 'text-warning border-warning/40',
  baixa: 'text-muted border-white/15',
}

export function BadgePrioridade({ prioridade }) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide border rounded-full px-2 py-0.5 ${CORES_PRIORIDADE[prioridade] ?? CORES_PRIORIDADE.baixa}`}
    >
      {prioridade === 'alta' ? '▲' : prioridade === 'media' ? '●' : '▽'} {prioridade}
    </span>
  )
}

// Barras horizontais de série única (magnitude): um único matiz,
// extremidades arredondadas, rótulo de valor em tinta de texto.
export function BarrasHorizontais({ dados, maxItens = 15, formato = (v) => v }) {
  const itens = dados.slice(0, maxItens)
  const maximo = Math.max(...itens.map(([, v]) => v), 1)
  return (
    <div className="space-y-2">
      {itens.map(([nome, valor], i) => (
        <div key={nome} className="grid grid-cols-[minmax(0,160px)_1fr_auto] items-center gap-3">
          <span className="text-xs text-ink2 truncate" title={nome}>{nome}</span>
          <div className="h-4 relative">
            <motion.div
              className="absolute inset-y-0 left-0 bg-serie rounded-r-[4px]"
              initial={{ width: 0 }}
              animate={{ width: `${(valor / maximo) * 100}%` }}
              transition={{ duration: 0.4, delay: i * 0.02 }}
            />
          </div>
          <span className="text-xs text-ink2 tabular-nums">{formato(valor)}</span>
        </div>
      ))}
    </div>
  )
}

export function Vazio({ children }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <p className="text-ink2 max-w-md">{children}</p>
    </div>
  )
}

export const fmt = {
  num: (v, casas = 2) => (v == null ? 'n/d' : Number(v).toFixed(casas)),
  pct: (v) => (v == null ? 'n/d' : `${(v * 100).toFixed(1)}%`),
}
