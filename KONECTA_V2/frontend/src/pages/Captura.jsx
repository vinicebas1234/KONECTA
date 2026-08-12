import { useState } from 'react'
import { Card, SectionTitle, StatTile, Vazio, fmt } from '../components/ui.jsx'
import {
  capturarWebcam,
  iniciarSessaoCaptura,
  obterTrajetoria,
  processarPipeline,
  validarCaptura,
} from '../api.js'

const ETAPAS = {
  ocioso: 'ocioso',
  capturando: 'capturando',
  validando: 'validando',
  processando: 'processando',
  concluido: 'concluido',
}

export default function Captura() {
  const [sinal, setSinal] = useState('')
  const [sinalizante, setSinalizante] = useState('')
  const [duracao, setDuracao] = useState(5)

  const [etapa, setEtapa] = useState(ETAPAS.ocioso)
  const [erro, setErro] = useState(null)
  const [log, setLog] = useState([])

  const [sessaoAtual, setSessaoAtual] = useState(null)
  const [validacao, setValidacao] = useState(null)
  const [pipeline, setPipeline] = useState(null)
  const [trajetoria, setTrajetoria] = useState(null)
  const [historico, setHistorico] = useState([])

  const emAndamento = etapa === ETAPAS.capturando || etapa === ETAPAS.validando || etapa === ETAPAS.processando

  function registrar(mensagem) {
    setLog((l) => [...l, mensagem])
  }

  async function iniciarCaptura() {
    if (!sinal.trim() || !sinalizante.trim()) {
      setErro('Informe o sinal e o sinalizante antes de capturar.')
      return
    }

    const idSessao = `${sinal.trim().toUpperCase()}_${Date.now()}`
    setErro(null)
    setLog([])
    setValidacao(null)
    setPipeline(null)
    setTrajetoria(null)
    setSessaoAtual(null)
    setEtapa(ETAPAS.capturando)

    try {
      registrar(`Criando sessão "${idSessao}"…`)
      await iniciarSessaoCaptura(idSessao, sinal.trim(), sinalizante.trim())

      registrar(`Capturando ${duracao}s da webcam do host do backend…`)
      const sessao = await capturarWebcam(idSessao, Number(duracao))
      setSessaoAtual(sessao)
      registrar(`✓ ${sessao.n_frames} frames capturados (fps real: ${sessao.fps_realizado?.toFixed(1)})`)

      setEtapa(ETAPAS.validando)
      registrar('Validando qualidade da captura…')
      const val = await validarCaptura(idSessao)
      setValidacao(val)
      registrar(val.valida ? '✓ Captura válida' : '⚠ Captura com problemas de qualidade')

      setEtapa(ETAPAS.processando)
      registrar('Rodando pipeline completo (landmarks → tracking → amostra)…')
      const pipe = await processarPipeline(idSessao, sinal.trim(), sinalizante.trim())
      setPipeline(pipe)
      registrar('✓ Pipeline concluído')

      const traj = await obterTrajetoria(idSessao).catch(() => null)
      setTrajetoria(traj)

      setHistorico((h) => [{ idSessao, sinal: sinal.trim(), sinalizante: sinalizante.trim(), pipe }, ...h].slice(0, 10))
      setEtapa(ETAPAS.concluido)
    } catch (e) {
      setErro(e.message)
      registrar(`✗ Erro: ${e.message}`)
      setEtapa(ETAPAS.ocioso)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <SectionTitle sub="Captura roda na webcam da máquina onde o backend está rodando (cv2.VideoCapture), não na câmera do navegador — pensado para uso local do pesquisador.">
          Nova sessão de captura
        </SectionTitle>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label className="text-xs text-muted block mb-1">Sinal</label>
            <input
              value={sinal}
              onChange={(e) => setSinal(e.target.value)}
              disabled={emAndamento}
              placeholder="ex: CASA"
              className="w-full bg-bg border border-white/10 rounded-lg text-sm px-3 py-1.5 text-ink2 disabled:opacity-50"
            />
          </div>
          <div>
            <label className="text-xs text-muted block mb-1">Sinalizante</label>
            <input
              value={sinalizante}
              onChange={(e) => setSinalizante(e.target.value)}
              disabled={emAndamento}
              placeholder="ex: Articulador01"
              className="w-full bg-bg border border-white/10 rounded-lg text-sm px-3 py-1.5 text-ink2 disabled:opacity-50"
            />
          </div>
          <div>
            <label className="text-xs text-muted block mb-1">Duração (s)</label>
            <input
              type="number"
              min={1}
              max={30}
              value={duracao}
              onChange={(e) => setDuracao(e.target.value)}
              disabled={emAndamento}
              className="w-full bg-bg border border-white/10 rounded-lg text-sm px-3 py-1.5 text-ink2 disabled:opacity-50"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={iniciarCaptura}
              disabled={emAndamento}
              className="w-full bg-serie hover:bg-serie/85 disabled:opacity-40 text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors"
            >
              {emAndamento ? 'Processando…' : 'Iniciar captura'}
            </button>
          </div>
        </div>

        {erro && (
          <div className="mt-4 border border-critical/40 bg-critical/10 text-sm text-ink rounded-lg px-4 py-2">
            {erro}
          </div>
        )}

        {log.length > 0 && (
          <div className="mt-4 space-y-1">
            {log.map((m, i) => (
              <p key={i} className="text-xs text-ink2 flex gap-2">
                <span className={i === log.length - 1 && emAndamento ? 'text-serie' : 'text-good'}>
                  {i === log.length - 1 && emAndamento ? '›' : '✓'}
                </span>
                {m}
              </p>
            ))}
          </div>
        )}
      </Card>

      {!sessaoAtual && !emAndamento && (
        <Vazio>
          Preencha sinal e sinalizante e clique em <span className="text-ink font-medium">Iniciar captura</span>{' '}
          para rodar o Capture → Tracking → Knowledge Engine de ponta a ponta sobre uma amostra real.
        </Vazio>
      )}

      {sessaoAtual && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatTile label="Frames capturados" value={sessaoAtual.n_frames} />
          <StatTile label="FPS realizado" value={fmt.num(sessaoAtual.fps_realizado, 1)} />
          <StatTile label="Duração" value={`${fmt.num(sessaoAtual.duracao_segundos, 1)}s`} />
          <StatTile label="Iluminação média" value={fmt.pct(sessaoAtual.qualidade_media_luz)} />
        </div>
      )}

      {validacao && (
        <Card>
          <SectionTitle>Validação de qualidade</SectionTitle>
          <p className="text-sm text-ink2">
            {validacao.valida ? '✓ Válida' : '⚠ Reprovada'} — pontuação {fmt.num(validacao.pontuacao)}
          </p>
          {validacao.problemas?.length > 0 && (
            <ul className="mt-2 space-y-1 text-sm text-critical">
              {validacao.problemas.map((p, i) => <li key={i}>• {p}</li>)}
            </ul>
          )}
          {validacao.avisos?.length > 0 && (
            <ul className="mt-2 space-y-1 text-sm text-warning">
              {validacao.avisos.map((a, i) => <li key={i}>• {a}</li>)}
            </ul>
          )}
        </Card>
      )}

      {pipeline && (
        <Card>
          <SectionTitle sub={`Amostra ${pipeline.id}`}>Resultado do pipeline</SectionTitle>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatTile label="Dominância" value={pipeline.trajetoria?.dominancia ?? 'n/d'} />
            <StatTile label="Local principal" value={pipeline.trajetoria?.local_principal ?? 'n/d'} />
            <StatTile label="Complexidade" value={fmt.num(pipeline.trajetoria?.complexidade)} />
            <StatTile label="Velocidade média" value={fmt.num(pipeline.trajetoria?.velocidade_media)} />
          </div>
        </Card>
      )}

      {trajetoria && (
        <Card>
          <SectionTitle>Trajetória detalhada por mão</SectionTitle>
          <div className="grid md:grid-cols-2 gap-4">
            {Object.entries(trajetoria.maos ?? {}).map(([lado, mao]) => (
              <div key={lado} className="text-sm text-ink2 space-y-1">
                <p className="font-medium text-ink capitalize">{lado}</p>
                <p>Ativa em {mao.ativa_em_frames} frames</p>
                <p>Velocidade média: {fmt.num(mao.velocidade_media)}</p>
                <p>Amplitude total: {fmt.num(mao.amplitude_total)}</p>
                <p>Estabilidade: {fmt.num(mao.estabilidade)}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {historico.length > 0 && (
        <Card>
          <SectionTitle>Sessões capturadas nesta visita</SectionTitle>
          <ul className="space-y-1 text-sm text-ink2">
            {historico.map((h) => (
              <li key={h.idSessao} className="flex items-center justify-between">
                <span>{h.sinal} · {h.sinalizante}</span>
                <span className="text-muted text-xs">{h.pipe?.n_frames} frames</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
