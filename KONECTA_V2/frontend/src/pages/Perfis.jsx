import { useState } from 'react'
import { Card, SectionTitle, Vazio, fmt } from '../components/ui.jsx'

function Tabela({ colunas, linhas }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-muted uppercase tracking-wide border-b border-line">
            {colunas.map((c) => (
              <th key={c} className="py-2 pr-4 font-medium">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {linhas.map((linha, i) => (
            <tr key={i}>
              {linha.map((celula, j) => (
                <td key={j} className={`py-2 pr-4 ${j === 0 ? 'text-ink' : 'text-ink2 tabular-nums'}`}>
                  {celula}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Perfis({ analise }) {
  const [aba, setAba] = useState('sinalizantes')
  if (!analise) return <Vazio>Execute uma análise para construir os perfis.</Vazio>

  const sinais = [...analise.perfis_sinais]
    .sort((a, b) => (b.variabilidade ?? -1) - (a.variabilidade ?? -1))
    .slice(0, 50)

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        {[
          ['sinalizantes', 'Sinalizantes'],
          ['sinais', 'Sinais'],
        ].map(([id, rotulo]) => (
          <button
            key={id}
            onClick={() => setAba(id)}
            className={`text-sm px-4 py-1.5 rounded-full border transition-colors ${
              aba === id
                ? 'bg-serie/15 border-serie/50 text-ink'
                : 'border-white/10 text-muted hover:text-ink2'
            }`}
          >
            {rotulo}
          </button>
        ))}
      </div>

      {aba === 'sinalizantes' ? (
        <Card>
          <SectionTitle sub="perfil biomecânico aprendido a partir das execuções">
            Perfis dos sinalizantes
          </SectionTitle>
          <Tabela
            colunas={['Sinalizante', 'Amostras', 'Velocidade', 'Amplitude', 'Estabilidade', 'Landmarks perdidos', 'Dominância']}
            linhas={analise.perfis_sinalizantes.map((p) => [
              p.sinalizante,
              p.n_amostras,
              fmt.num(p.velocidade_media),
              fmt.num(p.amplitude_media),
              fmt.num(p.estabilidade),
              fmt.pct(p.taxa_landmarks_perdidos),
              p.dominancia,
            ])}
          />
        </Card>
      ) : (
        <Card>
          <SectionTitle sub={`ordenados por variabilidade (mais difíceis primeiro) — top 50 de ${analise.perfis_sinais.length}`}>
            Perfis dos sinais
          </SectionTitle>
          <Tabela
            colunas={['Sinal', 'Amostras', 'Sinalizantes', 'Velocidade', 'Amplitude', 'Complexidade', 'Variabilidade']}
            linhas={sinais.map((p) => [
              p.sinal,
              p.n_amostras,
              p.n_sinalizantes,
              fmt.num(p.velocidade_media),
              fmt.num(p.amplitude_media),
              fmt.num(p.complexidade, 3),
              fmt.num(p.variabilidade, 3),
            ])}
          />
        </Card>
      )}
    </div>
  )
}
