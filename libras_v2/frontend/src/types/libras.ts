export interface LibrasSign {
  id: string;
  letter: string;
  hint: string;
  image_url: string;
}

export interface LibrasWord {
  id: string;
  word: string;
  category: string;
  hint: string;
  image_url: string;
  video_url?: string;
}

export type TokenType = 'word' | 'fingerspell';

export interface TranslatedToken {
  original: string;
  type: TokenType;
  signs: (LibrasSign | LibrasWord)[];
}

export interface TranslationResponse {
  original_text: string;
  tokens: TranslatedToken[];
}

export interface HandGestureResult {
  detected: boolean;
  letter: string | null;
  confidence: number;
}

// WebSocket
export type WSMessageType =
  | 'translate_text'
  | 'camera_frame'
  | 'translation_result'
  | 'gesture_result'
  | 'error';

export interface WSMessage {
  type: WSMessageType;
  data: any;
}