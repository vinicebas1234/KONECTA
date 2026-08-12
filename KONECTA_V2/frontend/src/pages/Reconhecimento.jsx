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
  const capturandoRef = useRef(false)

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

  // Sincronizar capturandoRef com estado
  useEffect(() => {
    capturandoRef.current = capturando
  }, [capturando])

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

  // Desenhar landmarks no canvas
  const desenharLandmarks = (landmarkData) => {
    const ctx = canvasRef.current?.getContext('2d')
    if (!ctx) return

    const w = canvasRef.current.width
    const h = canvasRef.current.height

    // Limpar canvas (fundo transparente - mantém o vídeo visível)
    ctx.clearRect(0, 0, w, h)

    // Se landmarkData é um objeto com multiHandLandmarks (MediaPipe)
    if (landmarkData && landmarkData.multiHandLandmarks && landmarkData.multiHandLandmarks.length > 0) {
      for (let handIdx = 0; handIdx < landmarkData.multiHandLandmarks.length; handIdx++) {
        const hand = landmarkData.multiHandLandmarks[handIdx]
        desenharMao(ctx, hand, w, h)
      }
    }
    // Se é um array de objetos { x, y, z } (modo teste)
    else if (Array.isArray(landmarkData) && landmarkData.length > 0 && landmarkData[0]?.x !== undefined) {
      // Dividir array de 42 pontos em duas mãos (21 cada)
      const mao1 = landmarkData.slice(0, 21)
      const mao2 = landmarkData.slice(21, 42)

      if (mao1.some(p => p.x !== 0 || p.y !== 0)) {
        desenharMao(ctx, mao1, w, h)
      }
      if (mao2.some(p => p.x !== 0 || p.y !== 0)) {
        desenharMao(ctx, mao2, w, h)
      }
    }
  }

  const desenharMao = (ctx, hand, w, h) => {
    const connections = [
      [0, 1], [1, 2], [2, 3], [3, 4],           // Polegar
      [5, 6], [6, 7], [7, 8],                   // Índice
      [9, 10], [10, 11], [11, 12],              // Meio
      [13, 14], [14, 15], [15, 16],             // Anelar
      [17, 18], [18, 19], [19, 20],             // Mínimo
      [0, 5], [5, 9], [9, 13], [13, 17], [17, 0] // Palma
    ]

    // Desenhar conexões (skeleton)
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

    // Desenhar pontos
    for (let i = 0; i < hand.length; i++) {
      const point = hand[i]
      const x = point.x * w
      const y = point.y * h

      ctx.fillStyle = '#00FF00'
      ctx.beginPath()
      ctx.arc(x, y, 6, 0, 2 * Math.PI)
      ctx.fill()

      ctx.strokeStyle = '#FFFFFF'
      ctx.lineWidth = 1.5
      ctx.stroke()
    }
  }

  // Callback quando MediaPipe detecta landmarks
  const onHandsResults = (results) => {
    if (!capturandoRef.current) return

    try {
      // Desenhar landmarks no canvas
      desenharLandmarks(results)

      // Extrair landmarks das mãos
      let landmarks = []

      if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
        console.log(`✓ Detectadas ${results.multiHandLandmarks.length} mão(s)`)

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
        landmarks = Array(42).fill(null).map(() => [0, 0, 0])
      }

      // Adicionar ao buffer
      landmarksBufferRef.current.push(landmarks)

      // Quando tiver 30 frames, fazer predição
      if (landmarksBufferRef.current.length >= 30) {
        console.log('📊 30 frames coletados, enviando para API...')
        fazerPredicao(landmarksBufferRef.current.slice(0, 30))
        landmarksBufferRef.current = []
      }

      setFrameAtual(prev => prev + 1)
    } catch (erro) {
      console.error('Erro ao processar landmarks:', erro)
    }
  }

  // Fazer predição via API
  const fazerPredicao = async (landmarks) => {
    try {
      const response = await fetch('/api/reconhecer', {
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

      // Filtrar apenas sinais treinados (A, B, C, D) com confiança mínima 30%
      const sinaisValidos = ['A', 'B', 'C', 'D']
      const sinalValido = sinaisValidos.includes(resultado.sinal)
      const confiancaMinima = 0.30

      if (sinalValido && resultado.confianca >= confiancaMinima && resultado.sinal !== 'DESCONHECIDO') {
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
        const landmarkObjects = []

        // Primeira mão (pontos 0-20)
        for (let i = 0; i < 21; i++) {
          // Simular posição realista de mão (0.2 a 0.8)
          const baseX = 0.4 + Math.sin(i / 21 * Math.PI) * 0.2
          const baseY = 0.5 + Math.cos(i / 21 * Math.PI) * 0.2
          const noise = () => (Math.random() - 0.5) * 0.1

          const x = baseX + noise()
          const y = baseY + noise()
          const z = 0.5 + noise()

          landmark.push(x)
          landmark.push(y)
          landmark.push(z)
          landmarkObjects.push({ x, y, z })
        }

        // Segunda mão (pontos 21-41) - posição diferente
        for (let i = 0; i < 21; i++) {
          const baseX = 0.6 + Math.sin(i / 21 * Math.PI) * 0.2
          const baseY = 0.5 + Math.cos(i / 21 * Math.PI) * 0.2
          const noise = () => (Math.random() - 0.5) * 0.1

          const x = baseX + noise()
          const y = baseY + noise()
          const z = 0.5 + noise()

          landmark.push(x)
          landmark.push(y)
          landmark.push(z)
          landmarkObjects.push({ x, y, z })
        }

        // Desenhar landmarks no canvas (modo teste)
        desenharLandmarks(landmarkObjects)

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
    <div className="space-y-4">
      {/* Câmera + Stats lado a lado */}
      <div className="grid grid-cols-3 gap-4">
        {/* ESQUERDA: Câmera e Resultado */}
        <div className="col-span-2">
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
              className="absolute inset-0 w-full h-full z-10"
            />

            {capturando && (
              <div className="absolute inset-0 flex flex-col justify-between p-6">
                {/* Frame counter no topo */}
                <div className="text-white text-sm font-bold bg-black/70 px-3 py-1 rounded w-fit">
                  Frame: {frameAtual}
                </div>

                {/* Resultado no centro */}
                {ultimaPredicao ? (
                  <motion.div
                    key={ultimaPredicao.frame}
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className={`
                      text-center p-6 rounded-lg font-bold text-white
                      ${ultimaPredicao.confianca > 0.65
                        ? 'bg-green-600/90'
                        : ultimaPredicao.confianca > 0.45
                        ? 'bg-yellow-600/90'
                        : 'bg-red-600/90'
                      }
                    `}
                  >
                    <p className="text-5xl mb-2">{ultimaPredicao.sinal}</p>
                    <p className="text-2xl">{(ultimaPredicao.confianca * 100).toFixed(0)}%</p>
                    <p className="text-sm mt-2">
                      {ultimaPredicao.confianca > 0.65
                        ? '✅ CORRETO'
                        : ultimaPredicao.confianca > 0.45
                        ? '⚠️ INCERTO'
                        : '❌ ERRADO'}
                    </p>
                  </motion.div>
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <motion.div
                      animate={{ scale: [1, 1.1, 1] }}
                      transition={{ repeat: Infinity, duration: 1 }}
                      className="bg-black/80 text-white text-lg font-bold px-6 py-4 rounded-lg text-center"
                    >
                      🔄 Aguardando...<br /><span className="text-sm">Faça um gesto</span>
                    </motion.div>
                  </div>
                )}

                {/* Placar embaixo */}
                <div className="text-white text-sm font-bold bg-black/70 px-3 py-2 rounded text-center">
                  ✅ {acertos} | ❌ {erros}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* DIREITA: Controles e Stats */}
        <div className="space-y-3">
          {/* Câmera selection */}
          {dispositivos.length > 0 && !capturando && (
            <div>
              <label className="text-xs font-semibold text-ink2">Câmera</label>
              <select
                value={cameraEscolhida || ''}
                onChange={(e) => setCameraEscolhida(e.target.value)}
                className="w-full mt-1 px-2 py-1 rounded-lg bg-surface border border-white/20 text-ink text-xs"
              >
                {dispositivos.map((device) => (
                  <option key={device.deviceId} value={device.deviceId}>
                    {device.label || `Câmera ${dispositivos.indexOf(device) + 1}`}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Botão principal */}
          {!capturando ? (
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={iniciarCamera}
              className="w-full bg-serie hover:bg-serie/85 text-white font-bold py-3 rounded-lg transition-colors"
            >
              📹 Abrir Câmera
            </motion.button>
          ) : (
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={pararCamera}
              className="w-full bg-critical hover:bg-critical/85 text-white font-bold py-3 rounded-lg transition-colors"
            >
              ⏹️ Parar
            </motion.button>
          )}

          {/* Stats */}
          {capturando && estatisticas && (
            <div className="bg-surface border border-white/10 rounded-lg p-3 space-y-2 text-xs">
              <div className="text-center">
                <p className="text-muted">Confiança Média</p>
                <p className="text-2xl font-bold text-serie">
                  {(estatisticas.confiancaMedia * 100).toFixed(0)}%
                </p>
              </div>
            </div>
          )}

          {/* Sinais disponíveis */}
          {sinaisTreinados.length > 0 && (
            <div className="bg-good/10 border border-good/30 rounded-lg p-3">
              <p className="text-xs font-semibold text-good mb-2">Sinais Treináveis:</p>
              <div className="flex flex-wrap gap-1">
                {sinaisTreinados.map((sinal, idx) => (
                  <div
                    key={idx}
                    className="bg-good/30 text-good px-2 py-1 rounded text-xs font-medium"
                  >
                    {sinal.nome}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
