import { useEffect, useRef, useState } from 'react';

export const useCamera = () => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [active, setActive] = useState(false);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' }
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        setActive(true);
      }
    } catch (err) {
      console.error('❌ Erro ao acessar câmera:', err);
    }
  };

  const stopCamera = () => {
    if (videoRef.current?.srcObject) {
      const tracks = (videoRef.current.srcObject as MediaStream).getTracks();
      tracks.forEach((t) => t.stop());
      setActive(false);
    }
  };

  // Captura frame como base64
  const captureFrame = (): string | null => {
    if (!videoRef.current || !canvasRef.current) return null;

    const canvas = canvasRef.current;
    const video = videoRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.drawImage(video, 0, 0);

    // Retorna base64 sem o prefixo "data:image/jpeg;base64,"
    const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
    return dataUrl.split(',')[1];
  };

  useEffect(() => {
    return () => stopCamera();
  }, []);

  return { videoRef, canvasRef, active, startCamera, stopCamera, captureFrame };
};