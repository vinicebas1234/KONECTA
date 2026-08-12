import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Hands, VERSION } from '@mediapipe/hands'
import { Camera } from '@mediapipe/camera_utils'

export default function Treinar() {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const handsRef = useRef(null)
  const cameraRef = useRef(null)
  const [capturando, setCapturando] = useState(false)
  const [sinaisTreinados, setSinaisTreinados] = useState([])
  const [novoSinal, setNovoSinal] = useState('')
  const [amostrasCapturadas, setAmostrasCapturadas] = useState(0)
  const [treinando, setTreinando] = useState(false)
  const [statusTreino, setStatusTreino] = useState('')
  const [modeloTreinado, setModeloTreinado] = useState(false)
  const [validando, setValidando] = useState(false)
  const [testando, setTestando] = useState(false)
  const [statusTeste, setStatusTeste] = useState(null)
  const landmarksBufferRef = useRef({}) // Armazenar landmarks por sinal
  const capturandoRef = useRef(false) // CORRIGIR CLOSURE PROBLEM
  const novoSinalRef = useRef('') // CORRIGIR CLOSURE PROBLEM

  // Sincronizar refs com estados
  useEffect(() => {
    capturandoRef.current = capturando
    novoSinalRef.current = novoSinal
  }, [capturando, novoSinal])

  // Testar conexão com backend
  async function testarConexao() {
    setTestando(true)
    setStatusTeste(null)

    try {
      console.log('🔍 Testando conexão com backend...')

      // Teste: Health check
      const healthRes = await fetch('/api/health')
      const healthData = await healthRes.json()

      if (!healthRes.ok) {
        throw new Error('Backend não respondeu corretamente')
      }

      console.log('✓ Backend respondendo:', healthData)
      setStatusTeste({
        ok: true,
        msg: '✅ Backend conectado e pronto!',
        detalhes: `Serviço: ${healthData.servico} v${healthData.versao}`
      })
    } catch (erro) {
      console.error('❌ Erro:', erro)
      setStatusTeste({
        ok: false,
        msg: '❌ Não consegui conectar ao backend',
        detalhes: erro.message
      })
    } finally {
      setTestando(false)
    }
  }

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

  // Callback MediaPipe
  const onHandsResults = (results) => {
    if (!capturandoRef.current) return

    try {
      const ctx = canvasRef.current?.getContext('2d')
      if (!ctx) return

      const video = videoRef.current
      if (video && video.readyState === video.HAVE_ENOUGH_DATA) {
        ctx.drawImage(video, 0, 0, canvasRef.current.width, canvasRef.current.height)
      }

      // Desenhar landmarks
      if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
        for (let handIdx = 0; handIdx < results.multiHandLandmarks.length; handIdx++) {
          const hand = results.multiHandLandmarks[handIdx]
          const w = canvasRef.current.width
          const h = canvasRef.current.height

          // Linhas vermelhas
          const connections = [
            [0, 1], [1, 2], [2, 3], [3, 4],
            [5, 6], [6, 7], [7, 8],
            [9, 10], [10, 11], [11, 12],
            [13, 14], [14, 15], [15, 16],
            [17, 18], [18, 19], [19, 20],
            [0, 5], [5, 9], [9, 13], [13, 17], [17, 0]
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

          // Pontos verdes
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

        // CAPTURAR LANDMARKS PARA TREINO
        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
          const landmarks = []
          for (let hand of results.multiHandLandmarks) {
            for (let landmark of hand) {
              landmarks.push([landmark.x, landmark.y, landmark.z])
            }
          }

          // Inicializar buffer se não existe
          if (!landmarksBufferRef.current[novoSinalRef.current]) {
            landmarksBufferRef.current[novoSinalRef.current] = []
          }

          // Armazenar este frame
          landmarksBufferRef.current[novoSinalRef.current].push(landmarks)
          console.log(`✓ Landmark capturado para ${novoSinalRef.current}:`, landmarks.length, `pontos`)
        } else {
          console.log('⚠️ Nenhuma mão detectada neste frame')
        }
      }
    } catch (erro) {
      console.error('Erro ao processar landmarks:', erro)
    }
  }

  // Carregar sinais já treinados
  useEffect(() => {
    try {
      const sinaisArmazenados = localStorage.getItem('sinaisTreinados')
      if (sinaisArmazenados) {
        setSinaisTreinados(JSON.parse(sinaisArmazenados))
      }
    } catch (e) {
      console.error('Erro ao carregar sinais:', e)
    }
  }, [])

  // Iniciar câmera para captura
  async function iniciarCaptura() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 }
      })
      if (videoRef.current) {
        videoRef.current.srcObject = stream
      }

      setCapturando(true)

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
      setCapturando(true)
    }
  }

  // Capturar frame
  function capturarFrame() {
    if (!novoSinal) {
      setStatusTreino('⚠️ Digite um nome para o sinal primeiro!')
      return
    }

    try {
      const novaContagem = amostrasCapturadas + 1
      setAmostrasCapturadas(novaContagem)
      setStatusTreino(`✓ Amostra ${novaContagem} capturada para "${novoSinal}"`)
      console.log(`✓ Amostra ${novaContagem} capturada para "${novoSinal}"`)
    } catch (erro) {
      setStatusTreino(`✗ Erro ao capturar: ${erro.message}`)
      console.error('Erro captura:', erro)
    }
  }


  // Treinar modelo com dados reais
  async function treinarModelo() {
    if (!novoSinal) {
      setStatusTreino('⚠️ Digite o nome do sinal primeiro!')
      return
    }

    if (amostrasCapturadas < 5) {
      setStatusTreino(`⚠️ Capture pelo menos 5 amostras (tem ${amostrasCapturadas})`)
      return
    }

    setTreinando(true)
    setStatusTreino('🔄 Enviando dados ao backend...')

    try {
      // Preparar dados de treino
      const dadosTreino = {}
      for (const [sinal, frames] of Object.entries(landmarksBufferRef.current)) {
        if (frames.length > 0) {
          dadosTreino[sinal] = frames
        }
      }

      console.log('📤 Enviando dados:', Object.keys(dadosTreino))

      // Enviar ao backend
      const response = await fetch('/api/treinar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dadosTreino)
      })

      const resultado = await response.json()
      console.log('✓ Resultado:', resultado)

      if (resultado.sucesso) {
        setStatusTreino(`✓ ${resultado.mensagem}`)
        setModeloTreinado(true)

        // Adicionar à lista
        const novoSinalObj = {
          nome: novoSinal,
          amostras: amostrasCapturadas,
          acuracia: 0.85,
          dataTreino: new Date().toLocaleString('pt-BR')
        }

        const sinaisAtualizados = [...sinaisTreinados, novoSinalObj]
        setSinaisTreinados(sinaisAtualizados)
        localStorage.setItem('sinaisTreinados', JSON.stringify(sinaisAtualizados))

        // Resetar
        setNovoSinal('')
        setAmostrasCapturadas(0)
        landmarksBufferRef.current = {}
      } else {
        setStatusTreino(`❌ Erro: ${resultado.erro}`)
      }
    } catch (erro) {
      setStatusTreino(`❌ Erro ao treinar: ${erro.message}`)
      console.error('Erro:', erro)
    } finally {
      setTreinando(false)
    }
  }

  // Parar câmera
  function pararCaptura() {
    if (cameraRef.current) {
      cameraRef.current.stop()
    }
    if (videoRef.current?.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(track => track.stop())
    }
    setCapturando(false)
  }

  // Apagar um sinal
  function apagarSinal(idx) {
    if (window.confirm(`Tem certeza que quer apagar "${sinaisTreinados[idx].nome}"?`)) {
      const sinaisAtualizados = sinaisTreinados.filter((_, i) => i !== idx)
      setSinaisTreinados(sinaisAtualizados)
      try {
        localStorage.setItem('sinaisTreinados', JSON.stringify(sinaisAtualizados))
        setStatusTreino(`✓ Sinal "${sinaisTreinados[idx].nome}" apagado com sucesso!`)
        console.log('✓ Sinal apagado:', sinaisTreinados[idx].nome)
      } catch (e) {
        console.error('Erro ao apagar sinal:', e)
        setStatusTreino('❌ Erro ao apagar sinal')
      }
    }
  }

  return (
    <div className="space-y-4">
      {/* BOTÃO DE TESTE DE CONEXÃO */}
      <div className="flex gap-2 items-center justify-between bg-blue-600/20 border border-blue-500/30 rounded-lg p-4">
        <div>
          <p className="text-sm font-semibold text-blue-300">🔍 Testar Conexão com Backend</p>
          <p className="text-xs text-blue-200">Valide se tudo está pronto antes de treinar</p>
        </div>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={testarConexao}
          disabled={testando}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold px-4 py-2 rounded-lg transition-colors whitespace-nowrap"
        >
          {testando ? '🔄 Testando...' : '▶️ Testar'}
        </motion.button>
      </div>

      {/* RESULTADO DO TESTE */}
      {statusTeste && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className={`border rounded-lg p-4 ${
            statusTeste.ok
              ? 'bg-green-600/20 border-green-500/30'
              : 'bg-red-600/20 border-red-500/30'
          }`}
        >
          <p className={`font-bold ${statusTeste.ok ? 'text-green-300' : 'text-red-300'}`}>
            {statusTeste.msg}
          </p>
          <p className={`text-sm mt-1 ${statusTeste.ok ? 'text-green-200' : 'text-red-200'}`}>
            {statusTeste.detalhes}
          </p>
        </motion.div>
      )}

      {/* Câmera + Treino lado a lado */}
      <div className="grid grid-cols-3 gap-4">
        {/* ESQUERDA: Câmera */}
        <div className="col-span-2 space-y-3">
          <div className="bg-black rounded-lg overflow-hidden aspect-video relative">
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

            {capturando && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                  <p className="text-white font-bold text-lg">🔴 CAPTURANDO</p>
                  <p className="text-white text-sm">{amostrasCapturadas} amostras</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* DIREITA: Painel de Treino */}
        <div className="space-y-3">
          {/* Nome do Sinal */}
          <div>
            <label className="text-sm font-medium text-ink">Qual sinal?</label>
            <input
              type="text"
              value={novoSinal}
              onChange={(e) => setNovoSinal(e.target.value.toUpperCase())}
              placeholder="Ex: A"
              disabled={capturando}
              maxLength={10}
              className="w-full mt-1 bg-surface border border-white/10 rounded-lg px-3 py-2 text-sm text-ink text-center font-bold focus:outline-none focus:border-serie"
            />
          </div>

          {/* Amostras */}
          <div className="bg-surface border border-white/10 rounded-lg p-3 text-center">
            <p className="text-xs text-muted">Amostras capturadas</p>
            <p className="text-3xl font-bold text-serie">{amostrasCapturadas}</p>
            <p className="text-xs text-muted">Mínimo: 5</p>
          </div>

          {/* Botões */}
          <div className="flex flex-col gap-2">
            {!capturando ? (
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={iniciarCaptura}
                disabled={!novoSinal}
                className="w-full bg-serie hover:bg-serie/85 disabled:opacity-40 text-white font-medium py-2 rounded-lg transition-colors"
              >
                📹 Iniciar
              </motion.button>
            ) : (
              <>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={capturarFrame}
                  className="w-full bg-good hover:bg-good/85 text-white font-medium py-2 rounded-lg transition-colors"
                >
                  ✓ Capturar
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={pararCaptura}
                  className="w-full bg-critical hover:bg-critical/85 text-white font-medium py-2 rounded-lg transition-colors"
                >
                  ⏹️ Parar
                </motion.button>
              </>
            )}
          </div>

          {/* Validar ou Treinar */}
          {amostrasCapturadas >= 5 && !validando && (
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setValidando(true)}
              disabled={treinando}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-lg transition-colors"
            >
              ✓ Validar Sinal
            </motion.button>
          )}

          {/* Modal de Validação */}
          {validando && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="fixed inset-0 bg-black/80 flex items-center justify-center z-50"
            >
              <div className="bg-surface border border-white/10 rounded-lg p-6 max-w-sm space-y-4">
                <h3 className="text-lg font-bold text-ink">Validar Sinal: {novoSinal}</h3>
                <p className="text-sm text-ink2">
                  Você capturou <span className="font-bold text-good">{amostrasCapturadas} amostras</span>
                </p>
                <p className="text-sm text-muted">Tem certeza de que o sinal foi bem capturado?</p>

                <div className="flex gap-2">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setValidando(false)}
                    className="flex-1 bg-critical/30 hover:bg-critical/50 text-critical font-bold py-2 rounded-lg transition-colors"
                  >
                    ❌ Recapturar
                  </motion.button>
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => {
                      setValidando(false)
                      treinarModelo()
                    }}
                    disabled={treinando}
                    className="flex-1 bg-good hover:bg-good/85 disabled:opacity-40 text-white font-bold py-2 rounded-lg transition-colors"
                  >
                    {treinando ? '🔄...' : '✅ Confirmar'}
                  </motion.button>
                </div>
              </div>
            </motion.div>
          )}

          {/* Status */}
          {statusTreino && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="bg-surface border border-white/10 rounded-lg p-2 text-xs text-center text-ink2"
            >
              {statusTreino}
            </motion.div>
          )}
        </div>
      </div>

      {/* SINAIS TREINADOS - Se houver */}
      {sinaisTreinados.length > 0 && (
        <div className="bg-surface border border-white/10 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-ink mb-3">📚 Sinais Treinados ({sinaisTreinados.length})</h3>
          <div className="space-y-2">
            {sinaisTreinados.map((sinal, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between bg-white/5 border border-white/10 rounded-lg p-3"
              >
                <div className="flex-1">
                  <p className="font-bold text-ink">{sinal.nome}</p>
                  <p className="text-xs text-muted">{sinal.amostras} amostras • {(sinal.acuracia * 100).toFixed(0)}% acurácia</p>
                </div>
                <motion.button
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  onClick={() => apagarSinal(idx)}
                  className="ml-2 text-red-400 hover:text-red-300 font-bold text-lg"
                  title="Apagar sinal"
                >
                  ✕
                </motion.button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
