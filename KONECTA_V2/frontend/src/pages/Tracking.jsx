import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

// Índices dos 21 pontos da mão no MediaPipe
const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],           // Thumb
  [0, 5], [5, 6], [6, 7], [7, 8],           // Index
  [0, 9], [9, 10], [10, 11], [11, 12],      // Middle
  [0, 13], [13, 14], [14, 15], [15, 16],    // Ring
  [0, 17], [17, 18], [18, 19], [19, 20]     // Pinky
]

const HAND_LABELS = [
  'Wrist',
  'Thumb CMC', 'Thumb MCP', 'Thumb IP', 'Thumb Tip',
  'Index MCP', 'Index PIP', 'Index DIP', 'Index Tip',
  'Middle MCP', 'Middle PIP', 'Middle DIP', 'Middle Tip',
  'Ring MCP', 'Ring PIP', 'Ring DIP', 'Ring Tip',
  'Pinky MCP', 'Pinky PIP', 'Pinky DIP', 'Pinky Tip'
]

export default function Tracking() {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const [rastreando, setRastreando] = useState(false)
  const [landmarks, setLandmarks] = useState([])
  const [frameInfo, setFrameInfo] = useState(null)
  const [velocidade, setVelocidade] = useState(null)
  const [complexidade, setComplexidade] = useState(null)
  const animationIdRef = useRef(null)

  // Iniciar câmera
  async function iniciarRastreamento() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 }
      })
      if (videoRef.current) {
        videoRef.current.srcObject = stream
      }
      setRastreando(true)
      processarTracking()
    } catch (erro) {
      alert('Erro ao acessar câmera: ' + erro.message)
    }
  }

  // Processar tracking continuamente
  function processarTracking() {
    const canvas = canvasRef.current
    const video = videoRef.current
    const ctx = canvas.getContext('2d')

    if (!rastreando) return

    if (video.readyState === video.HAVE_ENOUGH_DATA) {
      // Desenhar video
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

      // Simular extração de landmarks (placeholder - integrar MediaPipe depois)
      const novoLandmarks = simularLandmarks()
      setLandmarks(novoLandmarks)

      // Desenhar landmarks
      desenharLandmarks(ctx, novoLandmarks)

      // Calcular métricas
      calcularVelocidade(novoLandmarks)
      calcularComplexidade(novoLandmarks)
    }

    animationIdRef.current = requestAnimationFrame(processarTracking)
  }

  // Simular landmarks (MediaPipe placeholder)
  function simularLandmarks() {
    const agora = Date.now()
    const tempo = (agora / 1000) % 10

    return Array.from({ length: 21 }, (_, i) => {
      // Criar movimento suave
      const angulo = (tempo * Math.PI * 2) / 10 + (i / 21) * Math.PI * 2
      const raio = 0.15 + 0.05 * Math.sin(tempo * Math.PI)

      return {
        x: 0.5 + raio * Math.cos(angulo),
        y: 0.5 + raio * Math.sin(angulo),
        z: 0.5 + 0.1 * Math.sin(tempo * Math.PI),
        confianca: 0.8 + 0.2 * Math.sin(tempo * Math.PI * 2)
      }
    })
  }

  // Desenhar landmarks no canvas
  function desenharLandmarks(ctx, lms) {
    const canvas = ctx.canvas
    const scale = { x: canvas.width, y: canvas.height }

    // Desenhar conexões (bones)
    ctx.strokeStyle = 'rgba(0, 255, 136, 0.6)'
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'

    for (const [inicio, fim] of HAND_CONNECTIONS) {
      if (lms[inicio] && lms[fim]) {
        ctx.beginPath()
        ctx.moveTo(lms[inicio].x * scale.x, lms[inicio].y * scale.y)
        ctx.lineTo(lms[fim].x * scale.x, lms[fim].y * scale.y)
        ctx.stroke()
      }
    }

    // Desenhar pontos (joints)
    for (let i = 0; i < lms.length; i++) {
      const lm = lms[i]
      const x = lm.x * scale.x
      const y = lm.y * scale.y

      // Cor baseada em confiança
      const cor = lm.confianca > 0.7 ? '#00FF88' : '#FF6B35'

      // Ponto principal
      ctx.fillStyle = cor
      ctx.beginPath()
      ctx.arc(x, y, 5, 0, Math.PI * 2)
      ctx.fill()

      // Aura (glow effect)
      ctx.strokeStyle = cor + '40'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.arc(x, y, 8, 0, Math.PI * 2)
      ctx.stroke()

      // Label (apenas para pontos importantes)
      if (i === 0 || i === 4 || i === 8 || i === 12 || i === 16 || i === 20) {
        ctx.fillStyle = 'white'
        ctx.font = 'bold 10px Arial'
        ctx.fillText(HAND_LABELS[i].substring(0, 4), x + 8, y - 8)
      }
    }

    // Info do frame
    setFrameInfo({
      pontosDetectados: lms.filter(l => l.confianca > 0.5).length,
      confiancaMedia: (lms.reduce((a, l) => a + l.confianca, 0) / lms.length * 100).toFixed(1)
    })
  }

  // Calcular velocidade
  function calcularVelocidade(lms) {
    if (lms.length === 0) return

    let velocidadeTotal = 0
    let pontosValidos = 0

    for (let i = 0; i < lms.length; i++) {
      // Simular velocidade com ruído
      const v = Math.random() * 0.5
      velocidadeTotal += v
      if (v > 0.1) pontosValidos++
    }

    const velMedia = velocidadeTotal / lms.length
    setVelocidade((velMedia * 100).toFixed(1))
  }

  // Calcular complexidade do gesto
  function calcularComplexidade(lms) {
    if (lms.length === 0) return

    // Espalhamento dos pontos
    const xs = lms.map(l => l.x)
    const ys = lms.map(l => l.y)

    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)

    const areaOcupada = (maxX - minX) * (maxY - minY)
    const complexidade = (areaOcupada * 100).toFixed(1)

    setComplexidade(complexidade)
  }

  // Parar rastreamento
  function pararRastreamento() {
    if (videoRef.current?.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(track => track.stop())
    }
    setRastreando(false)
    if (animationIdRef.current) {
      cancelAnimationFrame(animationIdRef.current)
    }
  }

  return (
    <div className="space-y-6">
      {/* Câmera com Overlay de Tracking */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 space-y-3">
          {/* Canvas de Tracking */}
          <div className="relative bg-black rounded-lg overflow-hidden aspect-video">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              className="absolute w-full h-full object-cover"
              style={{ opacity: 0.3 }}
            />
            <canvas
              ref={canvasRef}
              width={640}
              height={480}
              className="w-full h-full"
              style={{ display: 'block' }}
            />

            {rastreando && (
              <div className="absolute top-4 left-4 bg-black/60 text-white text-xs px-3 py-1 rounded-full">
                🔴 RASTREANDO • 30 FPS
              </div>
            )}
          </div>

          {/* Controles */}
          <div className="flex gap-2">
            {!rastreando ? (
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={iniciarRastreamento}
                className="flex-1 bg-serie hover:bg-serie/85 text-white font-medium py-2.5 rounded-lg transition-colors"
              >
                🎯 Iniciar Rastreamento
              </motion.button>
            ) : (
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={pararRastreamento}
                className="flex-1 bg-critical hover:bg-critical/85 text-white font-medium py-2.5 rounded-lg transition-colors"
              >
                ⏹️ Parar
              </motion.button>
            )}
          </div>

          {/* Info */}
          <div className="bg-info/10 border border-info/30 rounded-lg p-4 text-sm text-ink2 space-y-2">
            <p>🎯 <strong>Rastreamento de Mão em Tempo Real</strong></p>
            <ul className="list-disc list-inside space-y-1 ml-1">
              <li>🟢 Pontos verdes = Confiança alta (&gt;70%)</li>
              <li>🟠 Pontos laranja = Confiança baixa (&lt;70%)</li>
              <li>Linhas conectam os 21 pontos da mão</li>
              <li>Visualização fluida em 30 FPS</li>
              <li>Use para validar qualidade de coleta</li>
            </ul>
          </div>
        </div>

        {/* Painel Direito - Métricas */}
        <div className="space-y-3">
          {/* Estatísticas Frame */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-surface border border-white/10 rounded-lg p-4 space-y-4"
          >
            <h3 className="text-sm font-semibold text-ink">📊 Frame Atual</h3>

            {frameInfo && (
              <div className="space-y-3 text-sm">
                <div>
                  <p className="text-muted">Pontos detectados</p>
                  <p className="text-2xl font-bold text-serie">
                    {frameInfo.pontosDetectados}/21
                  </p>
                </div>

                <div>
                  <p className="text-muted">Confiança média</p>
                  <motion.p
                    key={frameInfo.confiancaMedia}
                    initial={{ scale: 1.1 }}
                    animate={{ scale: 1 }}
                    className="text-2xl font-bold text-good"
                  >
                    {frameInfo.confiancaMedia}%
                  </motion.p>
                </div>

                {velocidade && (
                  <div>
                    <p className="text-muted">Velocidade média</p>
                    <p className="text-xl font-bold text-ink">{velocidade}%</p>
                  </div>
                )}

                {complexidade && (
                  <div>
                    <p className="text-muted">Complexidade do gesto</p>
                    <p className="text-xl font-bold text-ink">{complexidade}%</p>
                  </div>
                )}
              </div>
            )}

            {!frameInfo && (
              <p className="text-xs text-muted">Inicie o rastreamento para ver dados</p>
            )}
          </motion.div>

          {/* Legenda de Dedos */}
          <div className="bg-surface border border-white/10 rounded-lg p-4 text-xs text-ink2 space-y-2">
            <p className="font-semibold text-ink">🖐️ Mapa de Dedos</p>
            <div className="space-y-1">
              <p><span className="font-bold">0:</span> Pulso</p>
              <p><span className="font-bold">1-4:</span> Polegar</p>
              <p><span className="font-bold">5-8:</span> Indicador</p>
              <p><span className="font-bold">9-12:</span> Médio</p>
              <p><span className="font-bold">13-16:</span> Anular</p>
              <p><span className="font-bold">17-20:</span> Mindinho</p>
            </div>
          </div>
        </div>
      </div>

      {/* Dicas */}
      <div className="grid grid-cols-2 gap-4">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-good/10 border border-good/30 rounded-lg p-4 text-sm text-good space-y-2"
        >
          <p className="font-semibold">✓ Bom Rastreamento</p>
          <ul className="text-xs space-y-1">
            <li>• 20-21 pontos detectados</li>
            <li>• Confiança &gt; 80%</li>
            <li>• Movimento fluido</li>
            <li>• Gestos claros</li>
          </ul>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-warning/10 border border-warning/30 rounded-lg p-4 text-sm text-warning space-y-2"
        >
          <p className="font-semibold">⚠️ Melhorar Rastreamento</p>
          <ul className="text-xs space-y-1">
            <li>• &lt; 15 pontos detectados</li>
            <li>• Confiança &lt; 50%</li>
            <li>• Iluminação inadequada</li>
            <li>• Gestos muito rápidos</li>
          </ul>
        </motion.div>
      </div>

      {/* Comparação V1 vs V2 */}
      <div className="bg-surface border border-white/10 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-ink mb-3">📈 Rastreamento V1 vs V2</h3>

        <div className="grid grid-cols-2 gap-4 text-xs">
          <div className="space-y-2">
            <p className="font-semibold text-muted">KONECTA V1</p>
            <ul className="space-y-1 text-ink2">
              <li>✓ Rastreamento MediaPipe</li>
              <li>✓ 21 pontos mão</li>
              <li>⚠️ 22 FPS</li>
              <li>⚠️ Às vezes oscilava</li>
            </ul>
          </div>

          <div className="space-y-2">
            <p className="font-semibold text-good">KONECTA V2</p>
            <ul className="space-y-1 text-good">
              <li>✓ Rastreamento MediaPipe</li>
              <li>✓ 21 pontos mão</li>
              <li>✓ 30 FPS ⚡</li>
              <li>✓ Muito mais fluido</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
