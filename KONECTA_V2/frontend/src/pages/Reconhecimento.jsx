import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

export default function Reconhecimento() {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const [capturando, setCapturando] = useState(false)
  const [predicoes, setPredicoes] = useState([])
  const [sinais, setSinais] = useState([])
  const [estatisticas, setEstatisticas] = useState(null)
  const [frameAtual, setFrameAtual] = useState(0)

  // Iniciar câmera
  async function iniciarCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 }
      })
      if (videoRef.current) {
        videoRef.current.srcObject = stream
      }
      setCapturando(true)
      processarFrames()
    } catch (erro) {
      alert('Erro ao acessar câmera: ' + erro.message)
    }
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

  // Processar frames
  async function processarFrames() {
    if (!capturando) return

    const canvas = canvasRef.current
    const video = videoRef.current
    const ctx = canvas.getContext('2d')

    if (video.readyState === video.HAVE_ENOUGH_DATA) {
      // Desenhar video no canvas
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

      // Simular extração de landmarks (no futuro: chamar MediaPipe)
      const landmarks = simularLandmarks()

      // Chamar API para reconhecer
      try {
        const response = await fetch('http://localhost:8000/api/models/reconhecer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            landmarks: landmarks,
            modo: 'frame_unico'
          })
        })

        if (response.ok) {
          const resultado = await response.json()

          // Atualizar predicoes
          setPredicoes(prev => [...prev.slice(-29), {
            frame: frameAtual,
            sinal: resultado.sinal,
            confianca: resultado.confianca,
            timestamp: new Date().toLocaleTimeString()
          }])

          setFrameAtual(prev => prev + 1)

          // Estatisticas
          const ultimasPred = predicoes.slice(-30)
          if (ultimasPred.length > 0) {
            const sinalDominante = ultimasPred.reduce((acc, p) => {
              acc[p.sinal] = (acc[p.sinal] || 0) + 1
              return acc
            }, {})
            const confiancaMedia = ultimasPred.reduce((acc, p) => acc + p.confianca, 0) / ultimasPred.length

            setEstatisticas({
              frameTotal: frameAtual,
              confiancaMedia: confiancaMedia,
              sinalMaisFrequente: Object.entries(sinalDominante).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A',
              contagens: sinalDominante
            })
          }
        }
      } catch (erro) {
        console.error('Erro ao reconhecer:', erro)
      }
    }

    // Próximo frame
    setTimeout(() => processarFrames(), 33) // ~30 FPS
  }

  // Simular extração de landmarks (placeholder)
  function simularLandmarks() {
    // Gerar landmarks aleatórios (30 frames x 21 pontos x 3 coords)
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
      {/* Câmera */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 space-y-3">
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

            {/* Overlay com informações */}
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

                {predicoes.length > 0 && (
                  <div className="bg-black/80 text-white text-sm p-3 rounded space-y-1">
                    <p className="font-bold">
                      {predicoes[predicoes.length - 1].sinal}
                    </p>
                    <p className="text-xs">
                      Confiança: {(predicoes[predicoes.length - 1].confianca * 100).toFixed(0)}%
                    </p>
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

            {estatisticas ? (
              <div className="space-y-2 text-xs text-ink2">
                <div>
                  <p className="text-muted">Frames processados</p>
                  <p className="text-lg font-bold text-ink">{estatisticas.frameTotal}</p>
                </div>

                <div>
                  <p className="text-muted">Confiança média</p>
                  <p className="text-lg font-bold text-serie">
                    {(estatisticas.confiancaMedia * 100).toFixed(1)}%
                  </p>
                </div>

                <div>
                  <p className="text-muted">Sinal dominante</p>
                  <p className="text-lg font-bold text-ink">
                    {estatisticas.sinalMaisFrequente}
                  </p>
                </div>

                {Object.entries(estatisticas.contagens).length > 0 && (
                  <div className="pt-2 border-t border-white/10">
                    <p className="text-muted mb-2">Contagem</p>
                    {Object.entries(estatisticas.contagens).map(([sinal, count]) => (
                      <div key={sinal} className="flex justify-between text-xs">
                        <span>{sinal}</span>
                        <span className="font-bold">{count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-muted">Inicie a câmera para ver estatísticas</p>
            )}
          </div>
        </div>
      </div>

      {/* Histórico de Predicoes */}
      {predicoes.length > 0 && (
        <div className="bg-surface border border-white/10 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-ink mb-3">📋 Últimas Predições</h3>

          <div className="max-h-48 overflow-y-auto space-y-2">
            {predicoes.slice().reverse().slice(0, 15).map((pred, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex items-center justify-between bg-white/5 p-2.5 rounded text-xs"
              >
                <span className="text-muted">Frame {pred.frame}</span>
                <span className={`font-bold ${
                  pred.confianca > 0.7 ? 'text-good' : pred.confianca > 0.5 ? 'text-warning' : 'text-critical'
                }`}>
                  {pred.sinal}
                </span>
                <span className="text-muted">
                  {(pred.confianca * 100).toFixed(0)}%
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Info */}
      <div className="bg-info/10 border border-info/30 rounded-lg p-4 text-sm text-ink2 space-y-2">
        <p>💡 <strong>Como usar:</strong></p>
        <ol className="list-decimal list-inside space-y-1 ml-1">
          <li>Clique em "📹 Abrir Câmera"</li>
          <li>Posicione sua mão dentro do quadro</li>
          <li>Faça o gesto do sinal (CASA, MESA, PORTA)</li>
          <li>Veja o reconhecimento em tempo real</li>
        </ol>
        <p className="pt-2 border-t border-info/30">
          ⚠️ <strong>Nota:</strong> O reconhecimento usa dados aleatórios simulados.
          Para testes reais, integre com MediaPipe no backend.
        </p>
      </div>
    </div>
  )
}
