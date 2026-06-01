import { TranslatedToken } from '../types/libras';

interface Props {
  tokens: TranslatedToken[];
}

export const SignDisplay = ({ tokens }: Props) => {
  if (tokens.length === 0) return null;

  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', gap: '12px',
      padding: '10px', justifyContent: 'center'
    }}>
      {tokens.map((token, idx) => (
        <div key={idx} style={{
          border: token.type === 'word' ? '2px solid #27AE60' : '2px solid #F39C12',
          borderRadius: '10px', padding: '8px',
          backgroundColor: token.type === 'word' ? '#E8F8F0' : '#FEF9E7',
          textAlign: 'center', minWidth: '60px'
        }}>
          <span style={{
            fontSize: '0.6rem', fontWeight: 'bold',
            color: token.type === 'word' ? '#27AE60' : '#F39C12'
          }}>
            {token.type === 'word' ? '🤟 Sinal' : '🔤 Soletrado'}
          </span>
          <p style={{ fontWeight: 'bold', fontSize: '0.8rem', margin: '2px 0' }}>
            {token.original}
          </p>
          <div style={{ display: 'flex', gap: '2px', justifyContent: 'center', flexWrap: 'wrap' }}>
            {token.signs.map((sign: any, sIdx: number) => (
              <div key={sIdx}>
                <img
                  src={`http://localhost:8000${sign.image_url}`}
                  alt={sign.letter || sign.word}
                  style={{
                    width: token.type === 'word' ? '80px' : '40px',
                    height: token.type === 'word' ? '80px' : '40px',
                    objectFit: 'contain'
                  }}
                />
                {sign.letter && (
                  <p style={{ fontSize: '0.7rem', margin: 0 }}>{sign.letter}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};