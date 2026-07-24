from pathlib import Path
import re
import shutil

arquivo = Path("libras_recognizer.py")

if not arquivo.exists():
    raise FileNotFoundError("Arquivo libras_recognizer.py não encontrado na pasta atual.")

backup = Path("libras_recognizer_backup.py")
shutil.copy2(arquivo, backup)

texto = arquivo.read_text(encoding="utf-8")

# Corrige entidades HTML, caso tenham sido copiadas assim
texto = texto.replace("&lt;", "<")
texto = texto.replace("&gt;", ">")
texto = texto.replace("&amp;", "&")

# Adiciona import necessário do MediaPipe
import_antigo = """from mediapipe.tasks import python
from mediapipe.tasks.python import vision"""

import_novo = """from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2"""

if import_antigo in texto and "from mediapipe.framework.formats import landmark_pb2" not in texto:
    texto = texto.replace(import_antigo, import_novo)

# Corrige instalação automática do TensorFlow para não quebrar NumPy/ml-dtypes
padrao_cmd_tf = r'cmd = \[sys\.executable, "-m", "pip", "install", "tensorflow", "--upgrade"\]'

cmd_tf_novo = '''cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "tensorflow==2.16.1",
        "numpy==1.26.4",
        "ml-dtypes==0.3.2",
        "--no-cache-dir"
    ]'''

texto = re.sub(padrao_cmd_tf, cmd_tf_novo, texto)

# Nova classe DetectorMaos corrigida
nova_classe_detector = r'''class DetectorMaos:
    """Detector de mãos e extrator de features (landmarks normalizados)."""

    def __init__(self, model_path=None, debug=False, log_fn=None):
        self.debug = bool(debug)
        self.log_fn = log_fn
        self.model_path = str(model_path or HAND_LANDMARKER_FILE)

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Modelo não encontrado: {self.model_path}. "
                f"Faça download para {DIR_MODELOS}"
            )

        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=MP_MAX_HANDS,
            min_hand_detection_confidence=MP_DET_CONF,
            min_tracking_confidence=MP_TRK_CONF,
        )

        self.detector = vision.HandLandmarker.create_from_options(options)

        # Correção: drawing_utils e drawing_styles pertencem ao mp.solutions,
        # não ao mediapipe.tasks.python.vision.
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_style = mp.solutions.drawing_styles
        self.mp_connections = mp.solutions.hands.HAND_CONNECTIONS

    def _debug(self, msg):
        if self.debug:
            _safe_log(self.log_fn, f"[DEBUG Detector] {msg}")

    def processar(self, frame_bgr):
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        return self.detector.detect(mp_image)

    def desenhar(self, frame_bgr, result):
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        annotated = frame_rgb.copy()

        if result.hand_landmarks:
            for hand_landmarks in result.hand_landmarks:
                landmark_list = landmark_pb2.NormalizedLandmarkList()

                for lm in hand_landmarks:
                    landmark = landmark_list.landmark.add()
                    landmark.x = lm.x
                    landmark.y = lm.y
                    landmark.z = lm.z

                self.mp_draw.draw_landmarks(
                    annotated,
                    landmark_list,
                    self.mp_connections,
                    self.mp_style.get_default_hand_landmarks_style(),
                    self.mp_style.get_default_hand_connections_style(),
                )

        return cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)

    @staticmethod
    def _normalizar_mao(pts):
        """Normalização robusta: centraliza no pulso e escala pela distância da palma."""
        pts = pts.astype(np.float32).copy()
        center = pts[0].copy()
        pts -= center

        ref = np.linalg.norm(pts[9] - pts[0])
        if ref < 1e-6:
            ref = np.max(np.abs(pts))
        if ref < 1e-6:
            ref = 1.0

        pts /= float(ref)
        pts = np.clip(pts, -3.0, 3.0)

        return pts

    def extrair_features(self, result):
        """Retorna vetor 126 (2 mãos). Se não houver mão: zeros."""
        feats = np.zeros(TOTAL_FEATURES, dtype=np.float32)

        if not result.hand_landmarks:
            return feats

        for idx, hand in enumerate(result.hand_landmarks):
            if idx >= MP_MAX_HANDS:
                break

            pts = np.array([[lm.x, lm.y, lm.z] for lm in hand], dtype=np.float32)
            pts = self._normalizar_mao(pts)

            start = idx * FEATURES_PER_HAND
            end = start + FEATURES_PER_HAND
            feats[start:end] = pts.flatten()

        return feats

    def liberar(self):
        try:
            self.detector.close()
        except Exception:
            pass
'''

# Substitui a classe DetectorMaos inteira
padrao_classe_detector = r'class DetectorMaos:.*?(?=\n# ══════════════════════════════════════════════════════════════════════════════\n# GERENCIADOR DE DADOS)'
texto = re.sub(padrao_classe_detector, nova_classe_detector + "\n", texto, flags=re.DOTALL)

# Corrige _carregar_estatico para não quebrar caso existam modelos .pkl antigos
nova_carregar_estatico = r'''def _carregar_estatico(self):
        m = DIR_MODELOS / "modelo_estatico.pkl"
        e = DIR_MODELOS / "encoder_estatico.pkl"

        if m.exists() and e.exists():
            try:
                with open(m, "rb") as f:
                    self.modelo_estatico = pickle.load(f)

                with open(e, "rb") as f:
                    self.encoder_estatico = pickle.load(f)

            except Exception as exc:
                print(f"Erro ao carregar modelo estático antigo: {exc}")
                print("O modelo estático será ignorado. Treine novamente pela interface.")

                self.modelo_estatico = None
                self.encoder_estatico = None'''

padrao_carregar_estatico = r'def _carregar_estatico\(self\):\n        m = DIR_MODELOS / "modelo_estatico\.pkl"\n        e = DIR_MODELOS / "encoder_estatico\.pkl"\n        if m\.exists\(\) and e\.exists\(\):\n            with open\(m, "rb"\) as f:\n                self\.modelo_estatico = pickle\.load\(f\)\n            with open\(e, "rb"\) as f:\n                self\.encoder_estatico = pickle\.load\(f\)'

texto = re.sub(padrao_carregar_estatico, nova_carregar_estatico, texto)

arquivo.write_text(texto, encoding="utf-8")

print("Correções aplicadas com sucesso.")
print(f"Backup criado em: {backup}")
print("Agora execute: python libras_recognizer.py")
