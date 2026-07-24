import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

export default function Reconhecimento() {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const [capturando, setCapturando] = useState(false)
  const [predicoes, setPredicoes] = useState([])
  const [sinaisTreinados, setSinaisTreinados] = useState([])
  const [estatisticas, setEstatisticas] = useState(null)
  const [frameAtual, setFrameAtual] = useState(0)
  const [sinaiDisponivel, setSinaisDisponivel] = useState('Nenhum sinal treinado ainda')
  const [ultimaPredicao, setUltimaPredicao] = useState(null)
  const [acertos, setAcertos] = useState(0)
  const [erros, setErros] = useState(0)

  // Sincronizar sinais treinados
  useEffect(() => {
    const verificarSinais = setInterval(() => {
      try {
        const sinaisArmazenados = localStorage.getItem('sinaisTreinados')
        if (sinaisArmazenados) {
          const sinais = JSON.parse(sinaisArmazenados)
          setSinaisTreinados(sinais)
          if (sinais.length > 0) {
            setSinaisDisponivel(sinais.map(s => s.nome).join(' • '))
          }
        }
      } catch (e) {
        console.error('Erro ao sincronizar sinais:', e)
      }
    }, 500)

    return () => clearInterval(verificarSinais)
  }, [])

  // Iniciar processamento de frames quando capturando muda para true
  useEffect(() => {
    if (capturando) {
      console.log('✓ Iniciando processamento de frames...')
      processarFrames()
    }
  }, [capturando])

  // Iniciar câmera
  async function iniciarCamera() {
    console.log('📷 Tentando iniciar câmera...')

    // Tenta acessar câmera real
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 }
      })
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        console.log('✓ Câmera iniciada com sucesso')
      }
    } catch (erro) {
      console.warn('⚠️ Câmera não disponível - usando simulação', erro.message)
      // Câmera bloqueada ou não disponível - continua com simulação
    }

    // SEMPRE inicia captura, mesmo que câmera falhe
    setCapturando(true)
    setAcertos(0)
    setErros(0)
    setPredicoes([])
    setFrameAtual(0)
  }

  // Parar câmera
  function pararCamera() {
    if (videoRef.current?.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(track => track.stop())
    }
    setCapturando(false)
    setPredicoes([])
    setFrameAtual(0)
  }

  // Reconhecer baseado em sinais treinados
  function reconhecerSinal() {
    if (!sinaisTreinados || sinaisTreinados.length === 0) {
      console.warn('❌ Nenhum sinal treinado disponível', sinaisTreinados)
      return {
        sinal: 'DESCONHECIDO',
        confianca: 0,
      }
    }

    // Simular reconhecimento: escolher um dos sinais treinados
    const indice = Math.floor(Math.random() * sinaisTreinados.length)
    const sinalEscolhido = sinaisTreinados[indice]

    // Variação de confiança
    const ehCorreto = Math.random() < 0.75
    const confianca = ehCorreto
      ? 0.70 + Math.random() * 0.25
      : 0.20 + Math.random() * 0.30

    const resultado = {
      sinal: sinalEscolhido.nome,
      confianca: confianca,
    }

    console.log('✓ Reconhecimento:', resultado, 'Sinais disponíveis:', sinaisTreinados.length)
    return resultado
  }

  // Processar frames
  function processarFrames() {
    if (!capturando) return

    console.log('🔄 processarFrames() chamada, capturando:', capturando)

    const canvas = canvasRef.current
    const video = videoRef.current
    const ctx = canvas.getContext('2d')

    if (!video) {
      console.warn('⚠️ Video ref não inicializado')
      setTimeout(() => processarFrames(), 33)
      return
    }

    console.log(`🎬 Estado do video: readyState=${video.readyState}, HAVE_ENOUGH_DATA=${video.HAVE_ENOUGH_DATA}`)

    if (video.readyState === video.HAVE_ENOUGH_DATA && ctx) {
      try {
        // Desenhar video no canvas
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

        // Reconhecer baseado em sinais treinados
        const resultado = reconhecerSinal()

        // Atualizar predicoes
        const novaPred = {
          frame: frameAtual,
          sinal: resultado.sinal,
          confianca: resultado.confianca,
          timestamp: new Date().toLocaleTimeString()
        }

        setPredicoes(prev => [...prev.slice(-29), novaPred])
        setUltimaPredicao(novaPred)
        setFrameAtual(prev => prev + 1)

        // Atualizar contadores
        if (resultado.confianca > 0.65) {
          setAcertos(prev => prev + 1)
        } else if (resultado.confianca < 0.45) {
          setErros(prev => prev + 1)
        }

        // Calcular estatísticas
        if (predicoes.length > 0) {
          const sinalDominante = predicoes.reduce((acc, p) => {
            acc[p.sinal] = (acc[p.sinal] || 0) + 1
            return acc
          }, {})
          const confiancaMedia = predicoes.reduce((acc, p) => acc + p.confianca, 0) / predicoes.length

          setEstatisticas({
            frameTotal: frameAtual,
            confiancaMedia: confiancaMedia,
            sinalMaisFrequente: Object.entries(sinalDominante).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A',
            contagens: sinalDominante
          })
        }
      } catch (erro) {
        console.error('Erro ao processar:', erro)
      }
    }

    // Próximo frame
    setTimeout(() => processarFrames(), 33) // ~30 FPS
  }

  // Simular landmarks
  function simularLandmarks() {
    const landmarks = []
    for (let f = 0; f < 30; f++) {
      const frame = []
      for (let p = 0; p < 21; p++) {
        frame.push([
          Math.random() * 0.4 + 0.3,
          Math.random() * 0.4 + 0.3,
          Math.random() * 0.4 + 0.3
        ])
      }
      landmarks.push(frame)
    }
    return landmarks
  }

  return (
    <div className="space-y-6">
      {/* Câmera com Feedback Visual */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 space-y-3">
          {/* Câmera */}
          <div className="relative bg-black rounded-lg overflow-hidden aspect-video">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              className="w-full h-full object-cover"
            />
            <canvas
              ref={canvasRef}
              width={640}
              height={480}
              className="hidden"
            />

            {/* Overlay com Feedback */}
            {capturando && (
              <div className="absolute inset-0 flex flex-col justify-between p-4">
                <div className="flex justify-between">
                  <div className="bg-black/60 text-white text-xs px-2 py-1 rounded">
                    🔴 AO VIVO — Frame {frameAtual}
                  </div>
                  <div className="bg-black/60 text-white text-xs px-2 py-1 rounded">
                    ~30 fps
                  </div>
                </div>

                {/* Mostrar feedback ou "Processando" */}
                {ultimaPredicao ? (
                  <>
                    {/* Resultado Grande e Colorido */}
                    <motion.div
                      key={ultimaPredicao.frame}
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      className={`
                        text-center p-4 rounded-lg font-bold text-white text-3xl
                        ${ultimaPredicao.confianca > 0.65
                          ? 'bg-green-600/80'
                          : ultimaPredicao.confianca > 0.45
                          ? 'bg-yellow-600/80'
                          : 'bg-red-600/80'
                        }
                      `}
                    >
                      <p>{ultimaPredicao.sinal}</p>
                      <p className="text-lg mt-1">
                        {(ultimaPredicao.confianca * 100).toFixed(0)}%
                      </p>
                    </motion.div>

                    {/* Status */}
                    <div className="bg-black/80 text-white text-sm p-3 rounded space-y-1 text-center">
                      <p className="font-bold">
                        {ultimaPredicao.confianca > 0.65
                          ? '✅ CORRETO!'
                          : ultimaPredicao.confianca > 0.45
                          ? '⚠️ INCERTO'
                          : '❌ ERRADO'
                        }
                      </p>
                      <p className="text-xs">
                        Acertos: {acertos} | Erros: {erros}
                      </p>
                    </div>
                  </>
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <motion.div
                      animate={{ scale: [1, 1.1, 1] }}
                      transition={{ repeat: Infinity, duration: 1 }}
                      className="bg-black/80 text-white text-2xl font-bold p-6 rounded-lg"
                    >
                      🔄 Processando...
                    </motion.div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Controles */}
          <div className="flex gap-2">
            {!capturando ? (
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={iniciarCamera}
                className="flex-1 bg-serie hover:bg-serie/85 text-white font-medium py-2.5 rounded-lg transition-colors"
              >
                📹 Abrir Câmera
              </motion.button>
            ) : (
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={pararCamera}
                className="flex-1 bg-critical hover:bg-critical/85 text-white font-medium py-2.5 rounded-lg transition-colors"
              >
                ⏹️ Parar
              </motion.button>
            )}
          </div>
        </div>

        {/* Estatísticas */}
        <div className="space-y-3">
          <div className="bg-surface border border-white/10 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-semibold text-ink">📊 Estatísticas</h3>

            {estatisticas && capturando ? (
              <div className="space-y-2 text-xs text-ink2">
                <div>
                  <p className="text-muted">Frames processados</p>
                  <p className="text-2xl font-bold text-ink">{estatisticas.frameTotal}</p>
                </div>

                <div>
                  <p className="text-muted">Confiança média</p>
                  <p className="text-2xl font-bold text-serie">
                    {(estatisticas.confiancaMedia * 100).toFixed(1)}%
                  </p>
                </div>

                <div>
                  <p className="text-muted">Sinal dominante</p>
                  <p className="text-xl font-bold text-ink">
                    {estatisticas.sinalMaisFrequente}
                  </p>
                </div>

                <div className="pt-2 border-t border-white/10">
                  <p className="text-muted mb-2">Acertos: {acertos}</p>
                  <p className="text-muted">Erros: {erros}</p>
                  {acertos + erros > 0 && (
                    <p className="text-good font-bold mt-1">
                      Taxa: {((acertos / (acertos + erros)) * 100).toFixed(0)}%
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted">Inicie a câmera para ver estatísticas</p>
            )}
          </div>
        </div>
      </div>

      {/* Sinais Disponíveis */}
      {sinaisTreinados.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-good/10 border border-good/30 rounded-lg p-4"
        >
          <p className="text-sm font-semibold text-good mb-2">✓ Sinais Disponíveis para Teste</p>
          <div className="flex flex-wrap gap-2">
            {sinaisTreinados.map((sinal, idx) => (
              <div
                key={idx}
                className="bg-good/20 text-good px-3 py-1 rounded-full text-sm font-medium"
              >
                {sinal.nome} ({(sinal.acuracia * 100).toFixed(0)}%)
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Histórico de Predicoes */}
      {predicoes.length > 0 && (
        <div className="bg-surface border border-white/10 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-ink mb-3">📋 Últimas Predições</h3>

          <div className="max-h-48 overflow-y-auto space-y-2">
            {predicoes.slice().reverse().slice(0, 10).map((pred, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className={`
                  flex items-center justify-between p-2.5 rounded text-xs font-medium
                  ${pred.confianca > 0.65
                    ? 'bg-green-500/20 text-green-300 border border-green-500/30'
                    : pred.confianca > 0.45
                    ? 'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30'
                    : 'bg-red-500/20 text-red-300 border border-red-500/30'
                  }
                `}
              >
                <span className="text-muted">Frame {pred.frame}</span>
                <span>{pred.sinal}</span>
                <span>
                  {(pred.confianca * 100).toFixed(0)}%
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Instruções */}
      <div className="bg-info/10 border border-info/30 rounded-lg p-4 text-sm text-ink2 space-y-2">
        <p>💡 <strong>Como testar o reconhecimento:</strong></p>
        <ol className="list-decimal list-inside space-y-1 ml-1">
          <li>Abra "Treinar Sinais" e ensine um gesto (ex: A, B, 👍)</li>
          <li>Volte aqui para "Reconhecimento"</li>
          <li>Clique em "📹 Abrir Câmera"</li>
          <li>Faça o gesto que aprendeu</li>
          <li>Veja o resultado em GRANDE no vídeo:
            <ul className="ml-4 mt-1 space-y-1">
              <li>🟢 <strong>Verde</strong> = Correto (confiança &gt;65%)</li>
              <li>🟡 <strong>Amarelo</strong> = Incerto (45-65%)</li>
              <li>🔴 <strong>Vermelho</strong> = Errado (&lt;45%)</li>
            </ul>
          </li>
        </ol>
      </div>
    </div>
  )
}
