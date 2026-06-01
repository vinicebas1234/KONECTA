import { useEffect, useRef, useState, useCallback } from 'react';
import { WSMessage } from '../types/libras';

const WS_URL = 'ws://localhost:8000/ws';

export const useWebSocket = () => {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log('🔌 WebSocket conectado');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      const message: WSMessage = JSON.parse(event.data);
      setLastMessage(message);
    };

    ws.onclose = () => {
      console.log('🔌 WebSocket desconectado');
      setConnected(false);
      // Reconnect automático após 3 segundos
      setTimeout(() => {
        wsRef.current = new WebSocket(WS_URL);
      }, 3000);
    };

    ws.onerror = (err) => {
      console.error('❌ WebSocket erro:', err);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, []);

  const sendMessage = useCallback((type: string, data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, data }));
    }
  }, []);

  return { connected, lastMessage, sendMessage };
};