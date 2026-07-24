"""Serviço de reconhecimento em tempo real usando modelo estático Random Forest."""

import pickle
from pathlib import Path
import numpy as np

# Caminho dos modelos (OCR/modelos está um nível acima de KONECTA_V2)
MODELS_PATH = Path(__file__).parent.parent.parent.parent / "OCR" / "modelos"

# Configurações (iguais ao V1)
TOTAL_FEATURES = 126  # 21 pontos x 2 mãos x 3 coords (x,y,z)

class RecognitionService:
    """Serviço de reconhecimento de gestos Libras usando modelo estático RF."""

    def __init__(self):
        """Inicializa carregando os modelos."""
        self.modelo_estatico = None
        self.encoder_estatico = None
        self.norm_media = None
        self.norm_std = None
        self._load_models()

    def _load_models(self):
        """Carrega o modelo estático Random Forest (que funciona bem)."""
        try:
            # Carregar modelo estático
            modelo_path = MODELS_PATH / "modelo_estatico.pkl"
            encoder_path = MODELS_PATH / "encoder_estatico.pkl"
            norm_path = MODELS_PATH / "variancia_pooled_estatica.pkl"

            if modelo_path.exists():
                with open(modelo_path, "rb") as f:
                    self.modelo_estatico = pickle.load(f)
                print(f"✓ Modelo estático RF carregado: {modelo_path}")
            else:
                print(f"❌ Modelo estático não encontrado: {modelo_path}")
                return

            if encoder_path.exists():
                with open(encoder_path, "rb") as f:
                    self.encoder_estatico = pickle.load(f)
                print(f"✓ Encoder estático carregado: {encoder_path}")
            else:
                print(f"⚠️ Encoder estático não encontrado: {encoder_path}")

            # Carregar normalização
            if norm_path.exists():
                with open(norm_path, "rb") as f:
                    norm_data = pickle.load(f)
                    if isinstance(norm_data, dict):
                        self.norm_media = np.array(norm_data.get("media"), dtype=np.float32)
                        self.norm_std = np.array(norm_data.get("std"), dtype=np.float32)
                    elif isinstance(norm_data, np.ndarray):
                        # Se é um array, usar como média
                        self.norm_media = np.array(norm_data, dtype=np.float32)
                        self.norm_std = np.ones(len(norm_data), dtype=np.float32)
                    print(f"✓ Normalização carregada: {norm_path}")

        except Exception as e:
            print(f"❌ Erro ao carregar modelos: {e}")

    def reconhecer(self, landmarks: list) -> dict:
        """Reconhece um gesto a partir dos landmarks.

        Args:
            landmarks: Lista de frames, cada frame tem 21 pontos x 2 mãos x 3 coords
                      Shape esperado: (30, 42, 3) ou lista com ~1260 valores

        Returns:
            {
                "sinal": str - Nome do sinal reconhecido
                "confianca": float - Probabilidade [0, 1]
            }
        """
        if self.modelo_estatico is None or self.encoder_estatico is None:
            return {
                "sinal": "DESCONHECIDO",
                "confianca": 0.0,
                "erro": "Modelo não carregado",
            }

        try:
            # Converter para array
            landmarks_array = np.array(landmarks, dtype=np.float32)

            # Extrair features (média dos frames para modelo estático)
            features = self._extrair_features(landmarks_array)

            if features is None or len(features) != TOTAL_FEATURES:
                return {
                    "sinal": "DESCONHECIDO",
                    "confianca": 0.0,
                    "erro": f"Features inválidas: esperado {TOTAL_FEATURES}, obteve {len(features) if features is not None else 0}",
                }

            # Normalizar se possível
            if self.norm_media is not None and self.norm_std is not None:
                try:
                    norm_media = np.array(self.norm_media, dtype=np.float32)
                    norm_std = np.array(self.norm_std, dtype=np.float32)
                    features = (features - norm_media) / (norm_std + 1e-8)
                except Exception as e:
                    print(f"⚠️ Erro ao normalizar: {e}")

            # Fazer predição
            x = features.reshape(1, -1)
            predicao = self.modelo_estatico.predict(x)
            probabilidades = self.modelo_estatico.predict_proba(x)

            if len(predicao) > 0:
                sinal = predicao[0]
                confianca = float(np.max(probabilidades[0]))

                return {
                    "sinal": str(sinal),
                    "confianca": confianca,
                }

            return {
                "sinal": "DESCONHECIDO",
                "confianca": 0.0,
            }

        except Exception as e:
            print(f"❌ Erro ao reconhecer: {e}")
            return {
                "sinal": "DESCONHECIDO",
                "confianca": 0.0,
                "erro": str(e),
            }

    def _extrair_features(self, landmarks: np.ndarray) -> np.ndarray | None:
        """Extrai features dos landmarks (média dos frames).

        Tira a média de todos os frames para usar como features estáticas.
        Isso é similar ao que V1 faz para o modelo estático.
        """
        try:
            if landmarks.size == 0:
                return np.zeros(TOTAL_FEATURES, dtype=np.float32)

            # Se é um array 3D (frames, pontos, coords), flatten e tira média
            if landmarks.ndim == 3:
                # Shape: (frames, 21, 3) ou (frames, 42, 3)
                landmarks = landmarks.reshape(landmarks.shape[0], -1)  # (frames, features)
                features = np.mean(landmarks, axis=0)  # Média entre frames
            else:
                # Se já é 1D ou 2D, apenas usar como está
                features = landmarks.flatten()

            # Garantir que temos exatamente 126 features
            if len(features) < TOTAL_FEATURES:
                # Pad com zeros
                features = np.pad(features, (0, TOTAL_FEATURES - len(features)))
            elif len(features) > TOTAL_FEATURES:
                # Truncar
                features = features[:TOTAL_FEATURES]

            return features.astype(np.float32)

        except Exception as e:
            print(f"❌ Erro ao extrair features: {e}")
            return None


# Instância global do serviço
service = RecognitionService()
