"""Serviço de treino dinâmico para criar novos modelos com dados do usuário."""

import pickle
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

# CORREÇÃO: Usar KONECTA_V2/modelos, não OCR/modelos (V1)
MODELS_PATH = Path(__file__).parent.parent.parent / "modelos"
TOTAL_FEATURES = 126

class TrainingService:
    """Treina novo modelo Random Forest com dados capturados pelo usuário."""

    @staticmethod
    def treinar_modelo(dados_treinamento: dict) -> dict:
        """
        Treina modelo com dados: {'A': [frames], 'B': [frames], ...}
        Cada frame é uma lista de 126 features.
        """
        try:
            X = []
            y = []

            # Preparar dados
            for sinal, frames_list in dados_treinamento.items():
                for frame in frames_list:
                    features = np.array(frame, dtype=np.float32)
                    if len(features) == TOTAL_FEATURES:
                        X.append(features)
                        y.append(sinal)

            if len(X) < 10:
                return {"sucesso": False, "erro": "Dados insuficientes para treino"}

            X = np.array(X)
            y = np.array(y)

            # Treinar modelo
            modelo = RandomForestClassifier(n_estimators=100, max_depth=15, random_state=42)
            modelo.fit(X, y)

            # Criar encoder
            encoder = LabelEncoder()
            encoder.fit(y)

            # Calcular normalização
            norm_media = np.mean(X, axis=0)
            norm_std = np.std(X, axis=0)

            # Salvar modelos
            with open(MODELS_PATH / "modelo_treinado_usuario.pkl", "wb") as f:
                pickle.dump(modelo, f)
            with open(MODELS_PATH / "encoder_treinado_usuario.pkl", "wb") as f:
                pickle.dump(encoder, f)
            with open(MODELS_PATH / "normalizacao_usuario.pkl", "wb") as f:
                pickle.dump({"media": norm_media, "std": norm_std}, f)

            return {
                "sucesso": True,
                "mensagem": f"Modelo treinado com {len(X)} amostras",
                "sinais": len(np.unique(y)),
                "amostras_por_sinal": {s: sum(1 for x in y if x == s) for s in np.unique(y)}
            }

        except Exception as e:
            return {"sucesso": False, "erro": str(e)}

    @staticmethod
    def carregar_modelo_usuario():
        """Carrega o modelo treinado pelo usuário se existir."""
        modelo_path = MODELS_PATH / "modelo_treinado_usuario.pkl"
        if modelo_path.exists():
            with open(modelo_path, "rb") as f:
                return pickle.load(f), True
        return None, False
