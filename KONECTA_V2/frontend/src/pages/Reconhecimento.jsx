import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Hands, VERSION } from '@mediapipe/hands'
import { Camera } from '@mediapipe/camera_utils'

export default function Reconhecimento() {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const handsRef = useRef(null)
  const cameraRef = useRef(null)

  const [capturando, setCapturando] = useState(false)
  const [predicoes, setPredicoes] = useState([])
  const [sinaisTreinados, setSinaisTreinados] = useState([])
  const [estatisticas, setEstatisticas] = useState(null)
  const [frameAtual, setFrameAtual] = useState(0)
  const [sinaiDisponivel, setSinaisDisponivel] = useState('Nenhum sinal treinado ainda')
  const [ultimaPredicao, setUltimaPredicao] = useState(null)
  const [acertos, setAcertos] = useState(0)
  const [erros, setErros] = useState(0)
  const [dispositivos, setDispositivos] = useState([])
  const [cameraEscolhida, setCameraEscolhida] = useState(null)

  // Buffer de landmarks para fazer predição (30 frames)
  const landmarksBufferRef = useRef([])

  // Listar dispositivos de câmera disponíveis
  useEffect(() => {
    const listarDispositivos = async () => {
      try {
        const devices = await navigator.mediaDevices.enumerateDevices()
        const cameras = devices.filter(device => device.kind === 'videoinput')
        setDispositivos(cameras)
        console.log(`📹 ${cameras.length} câmera(s) encontrada(s):`, cameras)
        if (cameras.length > 0) {
          setCameraEscolhida(cameras[0].deviceId)
        }
      } catch (erro) {
        console.error('❌ Erro ao listar câmeras:', erro)
      }
    }

    listarDispositivos()
  }, [])

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

  // Inicializar MediaPipe Hands
  useEffect(() => {
    const setupHands = async () => {
      try {
        const hands = new Hands({
          locateFile: (file) => {
            return `https://cdn.jsdelivr.net/npm/@mediapipe/hands@${VERSION}/${file}`
          },
        })

        hands.setOptions({
          maxNumHands: 2,
          modelComplexity: 1,
          minDetectionConfidence: 0.5,
          minTrackingConfidence: 0.5,
        })

        // Callback quando MediaPipe detecta landmarks
        hands.onResults(onHandsResults)

        handsRef.current = hands
        console.log('✓ MediaPipe Hands inicializado')
      } catch (erro) {
        console.error('❌ Erro ao inicializar MediaPipe:', erro)
      }
    }

    setupHands()

    return () => {
      if (handsRef.current) {
        handsRef.current.close()
      }
    }
  }, [])

  // Callback quando MediaPipe detecta landmarks
  const onHandsResults = (results) => {
    if (!capturando) return

    try {
      const ctx = canvasRef.current?.getContext('2d')
      if (!ctx) return

      // Desenhar vídeo no canvas
      const video = videoRef.current
      if (video && video.readyState === video.HAVE_ENOUGH_DATA) {
        ctx.drawImage(video, 0, 0, canvasRef.current.width, canvasRef.current.height)
      }

      // Extrair landmarks das mãos
      let landmarks = []

      if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
        console.log(`✓ Detectadas ${results.multiHandLandmarks.length} mão(s)`)

        // Desenhar landmarks
        for (let handIdx = 0; handIdx < results.multiHandLandmarks.length; handIdx++) {
          const hand = results.multiHandLandmarks[handIdx]
          const w = canvasRef.current.width
          const h = canvasRef.current.height

          // Desenhar conexões (skeleton) PRIMEIRO para aparecer atrás
          const connections = [
            [0, 1], [1, 2], [2, 3], [3, 4],           // Polegar
            [5, 6], [6, 7], [7, 8],                   // Índice
            [9, 10], [10, 11], [11, 12],              // Meio
            [13, 14], [14, 15], [15, 16],             // Anelar
            [17, 18], [18, 19], [19, 20],             // Mínimo
            [0, 5], [5, 9], [9, 13], [13, 17], [17, 0] // Palma
          ]

          ctx.strokeStyle = '#FF0000'
          ctx.lineWidth = 3
          for (let [start, end] of connections) {
            const p1 = hand[start]
            const p2 = hand[end]
            if (p1 && p2) {
              ctx.beginPath()
              ctx.moveTo(p1.x * w, p1.y * h)
              ctx.lineTo(p2.x * w, p2.y * h)
              ctx.stroke()
            }
          }

          // Desenhar pontos DEPOIS para aparecer na frente
          for (let i = 0; i < hand.length; i++) {
            const point = hand[i]
            const x = point.x * w
            const y = point.y * h

            // Desenhar círculo verde
            ctx.fillStyle = '#00FF00'
            ctx.beginPath()
            ctx.arc(x, y, 6, 0, 2 * Math.PI)
            ctx.fill()

            // Borda branca
            ctx.strokeStyle = '#FFFFFF'
            ctx.lineWidth = 1.5
            ctx.stroke()
          }
        }

        // Pegar landmarks de ambas as mãos (se houver)
        for (let hand of results.multiHandLandmarks) {
          for (let landmark of hand) {
            landmarks.push([landmark.x, landmark.y, landmark.z])
          }
        }
      } else {
        console.log('⚠️ Nenhuma mão detectada neste frame')
      }

      // Se não detectou mão, usar zeros
      if (landmarks.length === 0) {
        landmarks = Array(42).fill([0, 0, 0]) // 21 pontos x 2 mãos x 3 coords
      }

      // Adicionar ao buffer
      landmarksBufferRef.current.push(landmarks)

      // Quando tiver 30 frames, fazer predição
      if (landmarksBufferRef.current.length >= 30) {
        console.log('📊 30 frames coletados, enviando para API...')
        fazerPredicao(landmarksBufferRef.current.slice(0, 30))
        landmarksBufferRef.current = [] // Limpar buffer
      }

      setFrameAtual(prev => prev + 1)
    } catch (erro) {
      console.error('Erro ao processar landmarks:', erro)
    }
  }

  // Fazer predição via API
  const fazerPredicao = async (landmarks) => {
    try {
      const response = await fetch('http://localhost:8000/api/reconhecer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(landmarks),
      })

      if (!response.ok) {
        throw new Error(`Erro na API: ${response.status}`)
      }

      const resultado = await response.json()
      console.log('✓ Reconhecimento:', resultado)

      if (resultado.sinal && resultado.sinal !== 'DESCONHECIDO') {
        const novaPred = {
          frame: frameAtual,
          sinal: resultado.sinal,
          confianca: resultado.confianca || 0.5,
          timestamp: new Date().toLocaleTimeString(),
        }

        setPredicoes(prev => [...prev.slice(-29), novaPred])
        setUltimaPredicao(novaPred)

        // Atualizar contadores
        if (novaPred.confianca > 0.65) {
          setAcertos(prev => prev + 1)
        } else if (novaPred.confianca < 0.45) {
          setErros(prev => prev + 1)
        }

        // Calcular estatísticas
        setEstatisticas({
          frameTotal: frameAtual,
          confiancaMedia: (predicoes.reduce((acc, p) => acc + p.confianca, 0) + novaPred.confianca) / (predicoes.length + 1),
          sinalMaisFrequente: novaPred.sinal,
          contagens: { [novaPred.sinal]: predicoes.filter(p => p.sinal === novaPred.sinal).length + 1 },
        })
      }
    } catch (erro) {
      console.error('❌ Erro ao reconhecer:', erro)
      setUltimaPredicao({
        frame: frameAtual,
        sinal: 'ERRO',
        confianca: 0,
        timestamp: new Date().toLocaleTimeString(),
      })
    }
  }

  // Iniciar câmera
  async function iniciarCamera() {
    console.log(`📷 Iniciando câmera (${cameraEscolhida}) com MediaPipe...`)

    try {
      const videoConstraints = {
        width: 640,
        height: 480,
      }

      if (cameraEscolhida) {
        videoConstraints.deviceId = { exact: cameraEscolhida }
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: videoConstraints,
      })

      if (videoRef.current) {
        videoRef.current.srcObject = stream
      }

      setCapturando(true)
      setAcertos(0)
      setErros(0)
      setPredicoes([])
      setFrameAtual(0)
      landmarksBufferRef.current = []

      // Iniciar camera com MediaPipe
      if (handsRef.current && videoRef.current) {
        cameraRef.current = new Camera(videoRef.current, {
          onFrame: async () => {
            await handsRef.current.send({ image: videoRef.current })
          },
          width: 640,
          height: 480,
        })
        cameraRef.current.start()
        console.log('✓ Camera iniciada com MediaPipe')
      }
    } catch (erro) {
      console.warn('⚠️ Câmera não disponível:', erro.message)
      console.log('📊 Iniciando modo TESTE com dados simulados...')

      setCapturando(true)
      setAcertos(0)
      setErros(0)
      setPredicoes([])
      setFrameAtual(0)
      landmarksBufferRef.current = []

      // Modo teste: simular detecção de mão
      let simulatedHandIndex = 0
      const simulateFrames = () => {
        // Gerar landmarks realistas simulando uma mão (21 pontos x 2 mãos)
        const landmark = []

        // Primeira mão (pontos 0-20)
        for (let i = 0; i < 21; i++) {
          // Simular posição realista de mão (0.2 a 0.8)
          const baseX = 0.4 + Math.sin(i / 21 * Math.PI) * 0.2
          const baseY = 0.5 + Math.cos(i / 21 * Math.PI) * 0.2
          const noise = () => (Math.random() - 0.5) * 0.1

          landmark.push(baseX + noise()) // x
          landmark.push(baseY + noise()) // y
          landmark.push(0.5 + noise())    // z
        }

        // Segunda mão (pontos 21-41) - posição diferente
        for (let i = 0; i < 21; i++) {
          const baseX = 0.6 + Math.sin(i / 21 * Math.PI) * 0.2
          const baseY = 0.5 + Math.cos(i / 21 * Math.PI) * 0.2
          const noise = () => (Math.random() - 0.5) * 0.1

          landmark.push(baseX + noise()) // x
          landmark.push(baseY + noise()) // y
          landmark.push(0.5 + noise())    // z
        }

        landmarksBufferRef.current.push(landmark)
        setFrameAtual(prev => prev + 1)

        if (landmarksBufferRef.current.length >= 30) {
          console.log('📊 30 frames simulados com padrão realista, enviando para API...')
          fazerPredicao(landmarksBufferRef.current.slice(0, 30))
          landmarksBufferRef.current = []
        }
      }

      // Simular frames a cada 50ms (20 FPS)
      const intervalId = setInterval(simulateFrames, 50)
      cameraRef.current = { stop: () => clearInterval(intervalId) }
      console.log('✓ Modo TESTE iniciado (dados simulados)')
    }
  }

  // Parar câmera
  function pararCamera() {
    if (cameraRef.current) {
      cameraRef.current.stop()
    }
    if (videoRef.current?.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(track => track.stop())
    }
    setCapturando(false)
    setPredicoes([])
    setFrameAtual(0)
    landmarksBufferRef.current = []
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
              className="absolute inset-0 w-full h-full"
            />

            {/* Overlay com Feedback */}
            {capturando && (
              <div className="absolute inset-0 flex flex-col justify-between p-4">
                <div className="flex justify-between">
                  <div className="bg-black/60 text-white text-xs px-2 py-1 rounded">
                    🔴 AO VIVO — Frame {frameAtual}
                  </div>
                  <div className="bg-black/60 text-white text-xs px-2 py-1 rounded">
                    MediaPipe
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
                          : '❌ ERRADO'}
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
                      🔄 Aguardando landmarks...
                    </motion.div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Seleção de Câmera */}
          {dispositivos.length > 0 && !capturando && (
            <div className="space-y-2">
              <label className="text-xs font-semibold text-ink2">📹 Câmera</label>
              <select
                value={cameraEscolhida || ''}
                onChange={(e) => setCameraEscolhida(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-surface border border-white/20 text-ink text-sm"
              >
                {dispositivos.map((device) => (
                  <option key={device.deviceId} value={device.deviceId}>
                    {device.label || `Câmera ${dispositivos.indexOf(device) + 1}`}
                  </option>
                ))}
              </select>
            </div>
          )}

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
                  <p className="text-muted">Sinal atual</p>
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
          <li>Faça o gesto que aprendeu (30 frames = ~1-2 segundos)</li>
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
