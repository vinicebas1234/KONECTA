"""Serviço de reconhecimento em tempo real usando Random Forest."""

import pickle
from pathlib import Path
import numpy as np
from sklearn.preprocessing import StandardScaler

# Caminho dos modelos
MODELS_PATH = Path(__file__).parent.parent.parent / "OCR" / "modelos"

class RecognitionService:
    """Serviço de reconhecimento de gestos Libras."""

    def __init__(self):
        """Inicializa o serviço carregando os modelos."""
        self.modelo_dinamico = None
        self.encoder_dinamico = None
        self.modelo_estatico = None
        self.encoder_estatico = None
        self._load_models()

    def _load_models(self):
        """Carrega os modelos Random Forest."""
        try:
            # Carregar modelo dinâmico
            modelo_path = MODELS_PATH / "modelo_dinamico_rf.pkl"
            encoder_path = MODELS_PATH / "encoder_dinamico_rf.pkl"

            if modelo_path.exists():
                with open(modelo_path, "rb") as f:
                    self.modelo_dinamico = pickle.load(f)
                print(f"✓ Modelo dinâmico carregado: {modelo_path}")
            else:
                print(f"⚠️ Modelo dinâmico não encontrado: {modelo_path}")

            if encoder_path.exists():
                with open(encoder_path, "rb") as f:
                    self.encoder_dinamico = pickle.load(f)
                print(f"✓ Encoder dinâmico carregado: {encoder_path}")
            else:
                print(f"⚠️ Encoder dinâmico não encontrado: {encoder_path}")

            # Carregar modelo estático como fallback
            modelo_est_path = MODELS_PATH / "modelo_estatico.pkl"
            encoder_est_path = MODELS_PATH / "encoder_estatico.pkl"

            if modelo_est_path.exists():
                with open(modelo_est_path, "rb") as f:
                    self.modelo_estatico = pickle.load(f)
                print(f"✓ Modelo estático carregado: {modelo_est_path}")

            if encoder_est_path.exists():
                with open(encoder_est_path, "rb") as f:
                    self.encoder_estatico = pickle.load(f)
                print(f"✓ Encoder estático carregado: {encoder_est_path}")

        except Exception as e:
            print(f"❌ Erro ao carregar modelos: {e}")

    def reconhecer(self, landmarks: list) -> dict:
        """Reconhece um gesto a partir dos landmarks.

        Args:
            landmarks: Lista de frames, cada frame tem 21 pontos x 2 mãos x 3 coords
                      Shape esperado: (30, 42, 3) ou similar

        Returns:
            {
                "sinal": str - Nome do sinal reconhecido
                "confianca": float - Probabilidade [0, 1]
                "modelo": str - Qual modelo foi usado
            }
        """
        if not self.modelo_dinamico:
            return {
                "sinal": "DESCONHECIDO",
                "confianca": 0.0,
                "modelo": "nenhum",
                "erro": "Modelos não carregados",
            }

        try:
            # Converter landmarks para array numpy
            landmarks_array = np.array(landmarks, dtype=np.float32)

            # Extrair features (placeholder - em produção usaria os verdadeiros features)
            # Por enquanto, vamos apenas normalizar os landmarks
            features = self._extrair_features(landmarks_array)

            if features is None:
                return {
                    "sinal": "DESCONHECIDO",
                    "confianca": 0.0,
                    "modelo": "dinamico",
                    "erro": "Falha ao extrair features",
                }

            # Normalizar com o encoder
            if self.encoder_dinamico:
                try:
                    features_normalized = self.encoder_dinamico.transform(
                        features.reshape(1, -1)
                    )
                except Exception:
                    features_normalized = features.reshape(1, -1)
            else:
                features_normalized = features.reshape(1, -1)

            # Fazer predição
            predicoes = self.modelo_dinamico.predict(features_normalized)
            probabilidades = self.modelo_dinamico.predict_proba(features_normalized)

            if len(predicoes) > 0:
                sinal = predicoes[0]
                # Pegar a confiança máxima
                confianca = float(np.max(probabilidades[0]))

                return {
                    "sinal": str(sinal),
                    "confianca": confianca,
                    "modelo": "dinamico",
                }

            return {
                "sinal": "DESCONHECIDO",
                "confianca": 0.0,
                "modelo": "dinamico",
            }

        except Exception as e:
            return {
                "sinal": "DESCONHECIDO",
                "confianca": 0.0,
                "modelo": "dinamico",
                "erro": str(e),
            }

    def _extrair_features(self, landmarks: np.ndarray) -> np.ndarray | None:
        """Extrai features dos landmarks.

        Placeholder: em produção usaria os verdadeiros cálculos de features
        (velocidade, amplitude, etc.) como definidos no projeto.
        """
        try:
            # Flatten dos landmarks
            if landmarks.ndim == 3:
                # (30, 21, 3) ou (frames, pontos, coords)
                features = landmarks.flatten()
            else:
                features = landmarks

            return features
        except Exception as e:
            print(f"❌ Erro ao extrair features: {e}")
            return None


# Instância global do serviço
service = RecognitionService()
