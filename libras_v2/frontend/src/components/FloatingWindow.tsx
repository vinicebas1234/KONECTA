import { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { SignDisplay } from './SignDisplay';
import { CameraFeed } from './CameraFeed';
import { TranslatedToken, HandGestureResult } from '../types/libras';

export const FloatingWindow = () => {
  // Estado
  const [tokens, setTokens] = useState<TranslatedToken[]>([]);
  const [recognizedText, setRecognizedText] = useState('');
  const [letterBuffer, setLetterBuffer] = useState<string[]>([]);
  const [cameraActive, setCameraActive] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [position, setPosition] = useState({ x: window.innerWidth - 420, y: 20 });
  const [dragging, setDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  // WebSocket
  const { connected, lastMessage, sendMessage } = useWebSocket();

  // ===== Recebe mensagens do backend =====
  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === 'translation_result') {
      setTokens(lastMessage.data.tokens);
    }

    if (lastMessage.type === 'gesture_result') {
      const result: HandGestureResult = lastMessage.data;
      if (result.detected && result.letter && result.confidence > 0.6) {
        setLetterBuffer((prev) => {
          const updated = [...prev, result.letter!];
          // Mantém buffer das últimas 20 letras
          return updated.slice(-20);
        });
        setRecognizedText((prev) => prev + result.letter);
      }
    }
  }, [lastMessage]);

  // ===== Recebe texto da transcrição (do seu sistema já pronto) =====
  // Esta função será chamada pelo seu sistema de speech-to-text
  const onTranscribedText = useCallback((text: string) => {
    sendMessage('translate_text', { text });
  }, [sendMessage]);

  // Expõe a função globalmente para integração com seu speech-to-text
  useEffect(() => {
    (window as any).onTranscribedText = onTranscribedText;
    return () => { delete (window as any).onTranscribedText; };
  }, [onTranscribedText]);

  // ===== Envia frame da câmera =====
  const handleSendFrame = useCallback((frame: string) => {
    sendMessage('camera_frame', { frame });
  }, [sendMessage]);

  // ===== Drag & Drop da janela =====
  const handleMouseDown = (e: React.MouseEvent) => {
    setDragging(true);
    setDragOffset({ x: e.clientX - position.x, y: e.clientY - position.y });
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (dragging) {
        setPosition({ x: e.clientX - dragOffset.x, y: e.clientY - dragOffset.y });
      }
    };
    const handleMouseUp = () => setDragging(false);

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragging, dragOffset]);

  // ===== UI =====
  return (
    <div style={{
      position: 'fixed',
      top: position.y, left: position.x,
      width: minimized ? '200px' : '400px',
      backgroundColor: 'rgba(30, 30, 30, 0.95)',
      borderRadius: '16px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      color: '#fff',
      zIndex: 99999,
      overflow: 'hidden',
      fontFamily: 'Arial, sans-serif',
      transition: 'width 0.3s ease',
    }}>
      {/* ===== Barra de título (draggable) ===== */}
      <div
        onMouseDown={handleMouseDown}
        style={{
          padding: '10px 16px',
          backgroundColor: '#4A90D9',
          cursor: 'grab',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          userSelect: 'none',
        }}
      >
        <span style={{ fontWeight: 'bold' }}>
          🤟 Libras {connected ? '🟢' : '🔴'}
        </span>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setMinimized(!minimized)}
            style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontSize: '1.2rem' }}
          >
            {minimized ? '🔽' : '🔼'}
          </button>
        </div>
      </div>

      {/* ===== Conteúdo (quando expandido) ===== */}
      {!minimized && (
        <div style={{ padding: '12px' }}>

          {/* --- Input manual (para testes) --- */}
          <div style={{ marginBottom: '10px' }}>
            <input
              type="text"
              placeholder="Digite ou aguarde transcrição..."
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  onTranscribedText((e.target as HTMLInputElement).value);
                  (e.target as HTMLInputElement).value = '';
                }
              }}
              style={{
                width: '100%', padding: '8px', borderRadius: '8px',
                border: '1px solid #555', backgroundColor: '#2a2a2a',
                color: '#fff', fontSize: '0.9rem', boxSizing: 'border-box',
              }}
            />
          </div>

          {/* --- Sinais traduzidos --- */}
          <div style={{
            backgroundColor: '#1a1a1a', borderRadius: '8px',
            padding: '8px', marginBottom: '10px',
            maxHeight: '200px', overflowY: 'auto'
          }}>
            <p style={{ fontSize: '0.7rem', color: '#888', margin: '0 0 4px' }}>
              🔤 Tradução em Libras:
            </p>
            {tokens.length > 0 ? (
              <SignDisplay tokens={tokens} />
            ) : (
              <p style={{ color: '#555', fontSize: '0.8rem', textAlign: 'center' }}>
                Aguardando texto...
              </p>
            )}
          </div>

          {/* --- Câmera + Reconhecimento --- */}
          <div style={{
            backgroundColor: '#1a1a1a', borderRadius: '8px',
            padding: '8px'
          }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              alignItems: 'center', marginBottom: '8px'
            }}>
              <p style={{ fontSize: '0.7rem', color: '#888', margin: 0 }}>
                📷 Reconhecimento de gestos:
              </p>
              <button
                onClick={() => setCameraActive(!cameraActive)}
                style={{
                  padding: '4px 12px', borderRadius: '6px',
                  border: 'none', cursor: 'pointer', fontSize: '0.75rem',
                  backgroundColor: cameraActive ? '#E74C3C' : '#27AE60',
                  color: '#fff'
                }}
              >
                {cameraActive ? '⏹ Parar' : '▶️ Iniciar'}
              </button>
            </div>

            {cameraActive && (
              <CameraFeed
                active={cameraActive}
                sendFrame={handleSendFrame}
                onGestureDetected={() => {}}
              />
            )}

            {/* Texto reconhecido pela câmera */}
            {letterBuffer.length > 0 && (
              <div style={{
                marginTop: '8px', padding: '8px',
                backgroundColor: '#2a2a2a', borderRadius: '6px'
              }}>
                <p style={{ fontSize: '0.7rem', color: '#888', margin: '0 0 4px' }}>
                  Texto reconhecido:
                </p>
                <p style={{
                  fontSize: '1.1rem', fontWeight: 'bold',
                  color: '#F39C12', margin: 0, letterSpacing: '2px'
                }}>
                  {letterBuffer.join('')}
                </p>
                <button
                  onClick={() => { setLetterBuffer([]); setRecognizedText(''); }}
                  style={{
                    marginTop: '4px', padding: '2px 8px',
                    fontSize: '0.7rem', borderRadius: '4px',
                    border: 'none', backgroundColor: '#555',
                    color: '#fff', cursor: 'pointer'
                  }}
                >
                  🗑️ Limpar
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};