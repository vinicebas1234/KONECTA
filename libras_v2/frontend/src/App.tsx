import { FloatingWindow } from './components/FloatingWindow';

function App() {
  return (
    <div>
      {/* Sua aplicação de chamada de vídeo aqui */}
      <div style={{
        height: '100vh', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        backgroundColor: '#1a1a2e', color: '#fff',
        fontFamily: 'Arial, sans-serif'
      }}>
        <h1>🎥 Sua chamada de vídeo aqui</h1>
      </div>

      {/* Janela flutuante (always on top) */}
      <FloatingWindow />
    </div>
  );
}

export default App;