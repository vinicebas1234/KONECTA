import { useEffect, useRef } from 'react';
import { useCamera } from '../hooks/useCamera';
import { HandGestureResult } from '../types/libras';

interface Props {
  onGestureDetected: (result: HandGestureResult) => void;
  sendFrame: (frame: string) => void;
  active: boolean;
}

export const CameraFeed = ({ onGestureDetected, sendFrame, active }: Props) => {
  const { videoRef, canvasRef, startCamera, stopCamera, captureFrame } = useCamera();
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (active) {
      startCamera();
      // Envia frames a cada 200ms (5 FPS — suficiente para reconhecimento)
      intervalRef.current = setInterval(() => {
        const frame = captureFrame();
        if (frame) {
          sendFrame(frame);
        }
      }, 200);
    } else {
      stopCamera();
      if (intervalRef.current) clearInterval(intervalRef.current);
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [active]);

  return (
    <div style={{ position: 'relative' }}>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        style={{
          width: '320px', height: '240px',
          borderRadius: '12px', border: '2px solid #4A90D9',
          transform: 'scaleX(-1)' // Espelha a câmera
        }}
      />
      {/* Canvas oculto para captura */}
      <canvas ref={canvasRef} style={{ display: 'none' }} />
    </div>
  );
};