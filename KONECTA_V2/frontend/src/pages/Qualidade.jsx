import { Card, SectionTitle, StatTile, Vazio, BadgePrioridade } from '../components/ui.jsx'

export default function Qualidade({ analise }) {
  if (!analise) return <Vazio>Execute uma análise para avaliar a qualidade das amostras.</Vazio>

  const q = analise.qualidade
  const aprovadas = q.avaliadas - q.reprovadas

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 max-w-2xl">
        <StatTile label="Avaliadas" value={q.avaliadas} />
        <StatTile label="Aprovadas" value={aprovadas} />
        <StatTile label="Reprovadas" value={q.reprovadas} />
      </div>

      <Card>
        <SectionTitle sub="somente amostras aprovadas devem entrar no dataset principal">
          Amostras reprovadas
        </SectionTitle>
        {q.detalhes_reprovadas.length === 0 ? (
          <p className="text-sm text-good">✓ Nenhuma amostra reprovada pelos limiares atuais.</p>
        ) : (
          <ul className="divide-y divide-line">
            {q.detalhes_reprovadas.map((item) => (
              <li key={item.amostra_id} className="py-3">
                <p className="text-sm text-ink font-medium">{item.amostra_id}</p>
                <ul className="mt-1.5 space-y-1">
                  {item.problemas.map((p, i) => (
                    <li key={i} className="flex items-center gap-2 text-xs text-ink2">
                      <BadgePrioridade prioridade={p.severidade} />
                      <span>{p.descricao}</span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
