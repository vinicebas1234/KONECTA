import { useState } from 'react'
import { motion } from 'framer-motion'
import { Card, SectionTitle, StatTile, BarrasHorizontais, Vazio, fmt } from '../components/ui.jsx'
import { interpretarComIA } from '../api.js'

export default function Dashboard({ analise }) {
  const [interpretando, setInterpretando] = useState(false)
  const [interpretacao, setInterpretacao] = useState(null)
  const [erroInterpretacao, setErroInterpretacao] = useState(null)

  async function pedir_interpretacao(tipo) {
    setInterpretando(true)
    setErroInterpretacao(null)
    try {
      const { resultado } = await interpretarComIA(tipo)
      setInterpretacao({ tipo, resultado })
    } catch (e) {
      setErroInterpretacao(e.message)
    } finally {
      setInterpretando(false)
    }
  }

  if (!analise) {
    return (
      <Vazio>
        Nenhuma análise carregada. Escolha uma fonte de dados no topo e clique em
        <span className="text-ink font-medium"> Analisar dataset</span> para o Knowledge
        Engine processar as amostras.
      </Vazio>
    )
  }

  const e = analise.estatisticas
  const porSinal = Object.entries(e.amostras_por_sinal).sort((a, b) => b[1] - a[1])
  const porSinalizante = Object.entries(e.amostras_por_sinalizante).sort((a, b) => b[1] - a[1])

  return (
    <>
    {interpretacao && (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
        onClick={() => setInterpretacao(null)}
      >
        <motion.div
          initial={{ scale: 0.95 }}
          animate={{ scale: 1 }}
          className="bg-surface border border-white/10 rounded-xl w-[720px] max-w-[90vw] max-h-[80vh] overflow-y-auto p-6"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-ink">
              Interpretação do AI Research Assistant
            </h3>
            <button
              onClick={() => setInterpretacao(null)}
              className="text-muted hover:text-ink2 text-lg"
            >
              ✕
            </button>
          </div>
          <div className="text-sm text-ink2 whitespace-pre-wrap leading-relaxed">
            {interpretacao.resultado}
          </div>
        </motion.div>
      </motion.div>
    )}
    <div className="space-y-6">
      {erroInterpretacao && (
        <div className="border border-critical/40 bg-critical/10 text-sm text-ink rounded-lg px-4 py-2">
          Erro ao interpretar: {erroInterpretacao}
        </div>
      )}
      {interpretando && (
        <div className="border border-serie/40 bg-serie/10 text-sm text-ink rounded-lg px-4 py-2">
          Claude está analisando o dataset…
        </div>
      )}
      <div className="flex gap-2">
        <button
          onClick={() => pedir_interpretacao('dataset')}
          disabled={interpretando}
          className="text-sm bg-serie/15 hover:bg-serie/25 disabled:opacity-40 text-ink border border-serie/50 px-4 py-2 rounded-lg transition-colors"
        >
          Interpretar com IA
        </button>
        <button
          onClick={() => pedir_interpretacao('coletas')}
          disabled={interpretando}
          className="text-sm bg-serie/15 hover:bg-serie/25 disabled:opacity-40 text-ink border border-serie/50 px-4 py-2 rounded-lg transition-colors"
        >
          Priorizar coletas
        </button>
        <button
          onClick={() => pedir_interpretacao('treinamento')}
          disabled={interpretando}
          className="text-sm bg-serie/15 hover:bg-serie/25 disabled:opacity-40 text-ink border border-serie/50 px-4 py-2 rounded-lg transition-colors"
        >
          Próximos passos
        </button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatTile label="Amostras" value={e.n_amostras} />
        <StatTile label="Sinais" value={e.n_sinais} />
        <StatTile label="Sinalizantes" value={e.n_sinalizantes} />
        <StatTile
          label="Balanceamento"
          value={fmt.num(e.balanceamento)}
          sub="entropia normalizada (1.00 = perfeito)"
        />
        <StatTile
          label="Reprovadas"
          value={analise.qualidade.reprovadas}
          sub={`de ${analise.qualidade.avaliadas} avaliadas`}
        />
        <StatTile
          label="Landmarks perdidos"
          value={fmt.pct(e.taxa_landmarks_perdidos)}
          sub="média do dataset"
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <Card>
          <SectionTitle sub={`${porSinal.length} sinais no total — exibindo os 15 com mais amostras`}>
            Amostras por sinal
          </SectionTitle>
          <BarrasHorizontais dados={porSinal} />
        </Card>

        <div className="space-y-6">
          <Card>
            <SectionTitle>Amostras por sinalizante</SectionTitle>
            <BarrasHorizontais dados={porSinalizante} maxItens={8} />
          </Card>

          <Card>
            <SectionTitle sub="pares com maior similaridade — risco de confusão no reconhecimento">
              Sinais semelhantes
            </SectionTitle>
            {analise.relacoes.length === 0 ? (
              <p className="text-sm text-muted">Nenhum par acima do limiar de similaridade.</p>
            ) : (
              <ul className="space-y-2">
                {analise.relacoes.slice(0, 8).map((r) => (
                  <li key={`${r.sinal_a}-${r.sinal_b}`} className="flex items-center justify-between text-sm">
                    <span className="text-ink2 truncate">
                      {r.sinal_a} <span className="text-muted">×</span> {r.sinal_b}
                    </span>
                    <span className="text-ink tabular-nums ml-3">{fmt.num(r.similaridade)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
    </>
  )
}
