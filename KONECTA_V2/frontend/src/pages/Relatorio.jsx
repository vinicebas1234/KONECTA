import { useEffect, useState } from 'react'
import { marked } from 'marked'
import { Card, Vazio } from '../components/ui.jsx'
import { obterRelatorio } from '../api.js'

export default function Relatorio({ analise }) {
  const [html, setHtml] = useState(null)
  const [erro, setErro] = useState(null)

  useEffect(() => {
    if (!analise) return
    obterRelatorio()
      .then((md) => setHtml(marked.parse(md)))
      .catch((e) => setErro(e.message))
  }, [analise])

  if (!analise) return <Vazio>Execute uma análise para gerar o relatório.</Vazio>
  if (erro) return <Vazio>{erro}</Vazio>
  if (!html) return <Vazio>Gerando relatório…</Vazio>

  return (
    <Card className="max-w-3xl">
      {/* Conteudo gerado pelo proprio backend (ReportGenerator) — fonte confiavel */}
      <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />
    </Card>
  )
}
