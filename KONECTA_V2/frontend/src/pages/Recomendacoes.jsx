import { Card, Vazio, BadgePrioridade } from '../components/ui.jsx'

export default function Recomendacoes({ analise }) {
  if (!analise) return <Vazio>Execute uma análise para gerar recomendações de coleta.</Vazio>

  if (analise.recomendacoes.length === 0) {
    return <Vazio>Nenhuma recomendação — o dataset atende a todos os critérios configurados.</Vazio>
  }

  return (
    <div className="space-y-4 max-w-3xl">
      {analise.recomendacoes.map((rec, i) => (
        <Card key={i}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-ink">{rec.titulo}</h3>
              <p className="text-sm text-ink2 mt-1">{rec.motivo}</p>
              {rec.sinais.length > 0 && (
                <p className="text-xs text-muted mt-2">
                  {rec.sinais.slice(0, 12).join(', ')}
                  {rec.sinais.length > 12 && ` … (+${rec.sinais.length - 12})`}
                </p>
              )}
            </div>
            <BadgePrioridade prioridade={rec.prioridade} />
          </div>
        </Card>
      ))}
    </div>
  )
}
