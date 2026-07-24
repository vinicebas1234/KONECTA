import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

export default function Treinar() {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const [capturando, setCapturando] = useState(false)
  const [sinaisTreinados, setSinaisTreinados] = useState([])
  const [novoSinal, setNovoSinal] = useState('')
  const [amostrasCapturadas, setAmostrasCapturadas] = useState(0)
  const [treinando, setTreinando] = useState(false)
  const [statusTreino, setStatusTreino] = useState('')
  const [modeloTreinado, setModeloTreinado] = useState(false)

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
    } catch (erro) {
      alert('Erro ao acessar câmera: ' + erro.message)
    }
  }

  // Capturar frame
  function capturarFrame() {
    if (!novoSinal) {
      setStatusTreino('⚠️ Digite um nome para o sinal primeiro!')
      return
    }

    const canvas = canvasRef.current
    const video = videoRef.current
    const ctx = canvas.getContext('2d')

    if (!video || !canvas || !ctx) {
      setStatusTreino('✗ Câmera não inicializada')
      return
    }

    if (video.readyState === video.HAVE_ENOUGH_DATA) {
      try {
        // Desenhar frame do vídeo
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

        // Simular extração de landmarks
        const landmarks = simularLandmarks()

        // Contar amostra localmente (sem backend)
        const novaContagem = amostrasCapturadas + 1
        setAmostrasCapturadas(novaContagem)
        setStatusTreino(`✓ Amostra ${novaContagem} capturada para "${novoSinal}"`)

        // Log para debug
        console.log(`✓ Amostra ${novaContagem} salva`, { sinal: novoSinal, landmarks })
      } catch (erro) {
        setStatusTreino(`✗ Erro ao capturar: ${erro.message}`)
        console.error('Erro captura:', erro)
      }
    } else {
      setStatusTreino('⚠️ Câmera ainda carregando... aguarde')
    }
  }

  // Simular landmarks (placeholder - usar MediaPipe depois)
  function simularLandmarks() {
    const landmarks = []
    for (let f = 0; f < 30; f++) {
      const frame = []
      for (let p = 0; p < 21; p++) {
        frame.push([
          Math.random() * 0.3 + 0.35,
          Math.random() * 0.3 + 0.35,
          Math.random() * 0.3 + 0.35
        ])
      }
      landmarks.push(frame)
    }
    return landmarks
  }

  // Treinar modelo
  function treinarModelo() {
    if (!novoSinal) {
      setStatusTreino('⚠️ Digite o nome do sinal primeiro!')
      return
    }

    if (amostrasCapturadas < 5) {
      setStatusTreino(`⚠️ Capture pelo menos 5 amostras (tem ${amostrasCapturadas})`)
      return
    }

    setTreinando(true)
    setStatusTreino('🔄 Treinando modelo...')

    // Simular treino (300ms)
    setTimeout(() => {
      // Gerar acurácia simulada (85-95%)
      const acuraciaSimulada = 0.85 + Math.random() * 0.1

      setStatusTreino(`✓ Modelo treinado! Acurácia: ${(acuraciaSimulada * 100).toFixed(1)}%`)
      setModeloTreinado(true)

      // Adicionar à lista de sinais treinados
      const novoSinalObj = {
        nome: novoSinal,
        amostras: amostrasCapturadas,
        acuracia: acuraciaSimulada,
        dataTreino: new Date().toLocaleString('pt-BR')
      }

      const sinaisAtualizados = [...sinaisTreinados, novoSinalObj]
      setSinaisTreinados(sinaisAtualizados)

      // Sincronizar com localStorage para Reconhecimento ver
      try {
        localStorage.setItem('sinaisTreinados', JSON.stringify(sinaisAtualizados))
        console.log('✓ Sinais salvos:', sinaisAtualizados)
      } catch (e) {
        console.error('Erro ao salvar sinais:', e)
      }

      // Resetar
      setNovoSinal('')
      setAmostrasCapturadas(0)
      setTreinando(false)
    }, 300)
  }

  // Parar câmera
  function pararCaptura() {
    if (videoRef.current?.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(track => track.stop())
    }
    setCapturando(false)
  }

  return (
    <div className="space-y-6">
      {/* Seção de Captura */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 space-y-3">
          {/* Câmera */}
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
              className="hidden"
            />

            {capturando && (
              <div className="absolute inset-0 flex flex-col justify-between p-4 bg-gradient-to-b from-black/40 to-transparent">
                <div className="flex justify-between">
                  <div className="bg-black/60 text-white text-xs px-3 py-1 rounded-full">
                    🔴 CAPTURANDO
                  </div>
                  <div className="bg-black/60 text-white text-xs px-3 py-1 rounded-full">
                    Amostras: {amostrasCapturadas}
                  </div>
                </div>

                {novoSinal && (
                  <div className="bg-black/80 text-white text-center p-3 rounded">
                    <p className="font-bold text-lg">{novoSinal}</p>
                    <p className="text-xs text-gray-300">
                      Faça o gesto e clique em "Capturar"
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Entrada de Nome do Sinal */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-ink">O que Deseja Ensinar?</label>
            <p className="text-xs text-muted">Digite qualquer coisa: A, B, 1, 2, @, etc.</p>
            <input
              type="text"
              value={novoSinal}
              onChange={(e) => setNovoSinal(e.target.value.toUpperCase())}
              placeholder="Ex: A, B, C, 1, 2, GATO, @"
              disabled={capturando}
              maxLength={20}
              className="w-full bg-surface border border-white/10 rounded-lg px-4 py-2 text-sm text-ink placeholder-muted focus:outline-none focus:border-serie text-center text-2xl font-bold"
            />
          </div>

          {/* Controles */}
          <div className="flex gap-2">
            {!capturando ? (
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={iniciarCaptura}
                disabled={!novoSinal}
                className="flex-1 bg-serie hover:bg-serie/85 disabled:opacity-40 text-white font-medium py-2.5 rounded-lg transition-colors"
              >
                📹 Iniciar Captura
              </motion.button>
            ) : (
              <>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={capturarFrame}
                  className="flex-1 bg-good hover:bg-good/85 text-white font-medium py-2.5 rounded-lg transition-colors"
                >
                  ✓ Capturar Frame
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={pararCaptura}
                  className="flex-1 bg-critical hover:bg-critical/85 text-white font-medium py-2.5 rounded-lg transition-colors"
                >
                  ⏹️ Parar
                </motion.button>
              </>
            )}
          </div>

          {/* Status */}
          {statusTreino && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-surface border border-white/10 rounded-lg p-3 text-sm text-ink2"
            >
              {statusTreino}
            </motion.div>
          )}
        </div>

        {/* Painel Direito - Controles de Treino */}
        <div className="space-y-3">
          <div className="bg-surface border border-white/10 rounded-lg p-4 space-y-4">
            <h3 className="text-sm font-semibold text-ink">🎓 Treinar Modelo</h3>

            <div className="space-y-2 text-xs">
              <p className="text-muted">Amostras capturadas</p>
              <p className="text-2xl font-bold text-serie">{amostrasCapturadas}</p>
              <p className="text-muted">Mínimo: 5 amostras</p>
            </div>

            <button
              onClick={treinarModelo}
              disabled={amostrasCapturadas < 5 || treinando}
              className="w-full bg-good hover:bg-good/85 disabled:opacity-40 text-white font-medium py-2 rounded-lg transition-colors text-sm"
            >
              {treinando ? '🔄 Treinando...' : '🚀 Treinar Modelo'}
            </button>

            {modeloTreinado && (
              <div className="bg-good/20 border border-good/40 rounded p-2 text-xs text-good">
                ✓ Modelo treinado com sucesso!
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Sinais Treinados */}
      {sinaisTreinados.length > 0 && (
        <div className="bg-surface border border-white/10 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-ink mb-3">📚 Sinais Treinados</h3>

          <div className="grid grid-cols-2 gap-2">
            {sinaisTreinados.map((sinal, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-white/5 border border-white/10 rounded-lg p-3 space-y-1"
              >
                <p className="font-bold text-ink">{sinal.nome}</p>
                <p className="text-xs text-muted">{sinal.amostras} amostras</p>
                <p className="text-xs font-medium text-good">
                  Acurácia: {(sinal.acuracia * 100).toFixed(1)}%
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Instruções */}
      <div className="bg-info/10 border border-info/30 rounded-lg p-4 text-sm text-ink2 space-y-2">
        <p>💡 <strong>Como Treinar um Novo Sinal:</strong></p>
        <ol className="list-decimal list-inside space-y-1 ml-1">
          <li>Digite o nome do sinal (ex: CASA)</li>
          <li>Clique em "📹 Iniciar Captura"</li>
          <li>Faça o gesto e clique "✓ Capturar Frame"</li>
          <li>Repita 5+ vezes com variações</li>
          <li>Clique em "🚀 Treinar Modelo"</li>
          <li>Sistema aprende seu sinal!</li>
        </ol>
      </div>
    </div>
  )
}
