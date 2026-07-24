#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera libras_recognizer_corrigido_v2.py a partir do libras_recognizer.py."""
from pathlib import Path
import re
import shutil
import py_compile

ARQUIVO_ORIGINAL = Path("libras_recognizer.py")
ARQUIVO_NOVO = Path("libras_recognizer_corrigido_v2.py")
BACKUP = Path("libras_recognizer_backup_antes_corrigir_v2.py")

NOVA_CLASSE_DETECTOR = 'class DetectorMaos:\n    """Detector de mãos e extrator de features (landmarks normalizados)."""\n\n    def __init__(self, model_path=None, debug=False, log_fn=None):\n        self.debug = bool(debug)\n        self.log_fn = log_fn\n        self.model_path = str(model_path or HAND_LANDMARKER_FILE)\n\n        if not os.path.exists(self.model_path):\n            raise FileNotFoundError(\n                f"Modelo não encontrado: {self.model_path}. "\n                f"Faça download para {DIR_MODELOS}"\n            )\n\n        base_options = python.BaseOptions(model_asset_path=self.model_path)\n        options = vision.HandLandmarkerOptions(\n            base_options=base_options,\n            num_hands=MP_MAX_HANDS,\n            min_hand_detection_confidence=MP_DET_CONF,\n            min_tracking_confidence=MP_TRK_CONF,\n        )\n        self.detector = vision.HandLandmarker.create_from_options(options)\n        self.mp_draw = mp.solutions.drawing_utils\n        self.mp_style = mp.solutions.drawing_styles\n        self.mp_connections = mp.solutions.hands.HAND_CONNECTIONS\n\n    def _debug(self, msg):\n        if self.debug:\n            _safe_log(self.log_fn, f"[DEBUG Detector] {msg}")\n\n    def processar(self, frame_bgr):\n        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)\n        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)\n        return self.detector.detect(mp_image)\n\n    def desenhar(self, frame_bgr, result):\n        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)\n        annotated = frame_rgb.copy()\n        if result.hand_landmarks:\n            for hand_landmarks in result.hand_landmarks:\n                landmark_list = landmark_pb2.NormalizedLandmarkList()\n                for lm in hand_landmarks:\n                    landmark = landmark_list.landmark.add()\n                    landmark.x = lm.x\n                    landmark.y = lm.y\n                    landmark.z = lm.z\n                self.mp_draw.draw_landmarks(\n                    annotated,\n                    landmark_list,\n                    self.mp_connections,\n                    self.mp_style.get_default_hand_landmarks_style(),\n                    self.mp_style.get_default_hand_connections_style(),\n                )\n        return cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)\n\n    @staticmethod\n    def _normalizar_mao(pts):\n        pts = pts.astype(np.float32).copy()\n        center = pts[0].copy()\n        pts -= center\n        ref = np.linalg.norm(pts[9] - pts[0])\n        if ref < 1e-6:\n            ref = np.max(np.abs(pts))\n        if ref < 1e-6:\n            ref = 1.0\n        pts /= float(ref)\n        pts = np.clip(pts, -3.0, 3.0)\n        return pts\n\n    def extrair_features(self, result):\n        feats = np.zeros(TOTAL_FEATURES, dtype=np.float32)\n        if not result.hand_landmarks:\n            return feats\n        for idx, hand in enumerate(result.hand_landmarks):\n            if idx >= MP_MAX_HANDS:\n                break\n            pts = np.array([[lm.x, lm.y, lm.z] for lm in hand], dtype=np.float32)\n            pts = self._normalizar_mao(pts)\n            start = idx * FEATURES_PER_HAND\n            end = start + FEATURES_PER_HAND\n            feats[start:end] = pts.flatten()\n        return feats\n\n    def liberar(self):\n        try:\n            self.detector.close()\n        except Exception:\n            pass\n'
NOVA_CARREGAR_ESTATICO = '    def _carregar_estatico(self):\n        m = DIR_MODELOS / "modelo_estatico.pkl"\n        e = DIR_MODELOS / "encoder_estatico.pkl"\n        if m.exists() and e.exists():\n            try:\n                with open(m, "rb") as f:\n                    self.modelo_estatico = pickle.load(f)\n                with open(e, "rb") as f:\n                    self.encoder_estatico = pickle.load(f)\n            except Exception as exc:\n                print(f"Erro ao carregar modelo estático antigo: {exc}")\n                print("O modelo estático será ignorado. Treine novamente pela interface.")\n                self.modelo_estatico = None\n                self.encoder_estatico = None\n'
NOVA_TREINAR_DINAMICO = '    def treinar_dinamico(\n        self,\n        X,\n        y,\n        meta,\n        rotulos_prioritarios=None,\n        peso_local=3.0,\n        log=None,\n        progresso_epoca_cb=None,\n    ):\n        NL = chr(10)\n        ok_tf, status_tf = verificar_tensorflow()\n        if not ok_tf:\n            return "❌ TensorFlow não instalado/disponível." + NL + str(status_tf)\n\n        if len(X) == 0:\n            return "❌ Nenhuma amostra dinâmica encontrada."\n\n        erro = self._validar_dataset(y)\n        if erro:\n            return erro\n\n        Xv, yv, metav = self._validar_sequencias_dinamicas(X, y, meta, log=log)\n        if len(Xv) == 0:\n            return "❌ Nenhuma sequência dinâmica válida após validação."\n\n        erro2 = self._validar_dataset(yv)\n        if erro2:\n            return erro2\n\n        pesos, prioridades = self._calcular_pesos_amostras(yv, metav, rotulos_prioritarios, peso_local)\n\n        contagem_classes = Counter(yv)\n        classes_validas = {classe for classe, qtd in contagem_classes.items() if qtd >= 2}\n\n        Xv_filtrado = []\n        yv_filtrado = []\n        metav_filtrado = []\n        pesos_filtrado = []\n\n        for x_item, y_item, meta_item, peso_item in zip(Xv, yv, metav, pesos):\n            if y_item in classes_validas:\n                Xv_filtrado.append(x_item)\n                yv_filtrado.append(y_item)\n                metav_filtrado.append(meta_item)\n                pesos_filtrado.append(peso_item)\n\n        Xv = np.array(Xv_filtrado, dtype=np.float32)\n        yv = np.array(yv_filtrado)\n        metav = metav_filtrado\n        pesos = np.array(pesos_filtrado, dtype=np.float32)\n\n        if len(Xv) == 0:\n            return "❌ Nenhuma sequência dinâmica válida após filtrar classes com poucas amostras."\n\n        if len(set(yv)) < 2:\n            return "❌ Após o filtro, restaram menos de 2 classes dinâmicas para treino."\n\n        enc = LabelEncoder()\n        y_enc = enc.fit_transform(yv)\n        n_classes = len(enc.classes_)\n\n        qtd_amostras = len(Xv)\n        qtd_classes = n_classes\n        test_size_abs = max(int(qtd_amostras * 0.2), qtd_classes)\n\n        if test_size_abs >= qtd_amostras:\n            test_size_abs = max(1, qtd_amostras - qtd_classes)\n\n        if test_size_abs <= 0 or test_size_abs >= qtd_amostras:\n            return (\n                "❌ Não há amostras suficientes para separar treino/teste." + NL\n                + f"Amostras: {qtd_amostras} | Classes: {qtd_classes}" + NL\n                + "Reduza a quantidade de classes ou colete mais amostras por classe."\n            )\n\n        if log:\n            log(f"📊 Classes dinâmicas após filtro: {qtd_classes}")\n            log(f"📊 Amostras dinâmicas após filtro: {qtd_amostras}")\n            log(f"📊 Tamanho do teste ajustado: {test_size_abs}")\n\n        Xtr, Xte, ytr_s, yte_s, wtr, _, _, _ = train_test_split(\n            Xv, y_enc, pesos, metav,\n            test_size=test_size_abs,\n            random_state=42,\n            stratify=y_enc\n        )\n\n        Xtr, Xte, media, std = self._normalizar_dinamico_train_test(Xtr, Xte)\n        self.norm_media_din = media\n        self.norm_std_din = std\n\n        Xtr_aug, ytr_aug, wtr_aug = self._aumentar_dataset_dinamico(Xtr, ytr_s, wtr, fator=1)\n\n        ytr = tf.keras.utils.to_categorical(ytr_aug, n_classes)\n        yte = tf.keras.utils.to_categorical(yte_s, n_classes)\n\n        if log:\n            log("🔄 Treinando LSTM (dinâmico)...")\n            log(f"📚 Dataset híbrido: {self._resumo_origens(metav)}")\n            log(\n                f"🎯 Sinais locais priorizados: "\n                f"{\', \'.join(sorted(prioridades)) if prioridades else \'(nenhum)\'}"\n                f" | peso extra: {peso_local:.2f}x"\n            )\n            log(f"🧪 Treino original: {len(Xtr)} | com augmentation: {len(Xtr_aug)}")\n            log(f"📐 Shape treino: {Xtr_aug.shape} | validação: {Xte.shape}")\n\n        model = self._criar_modelo_dinamico(n_classes)\n        chk_path = DIR_MODELOS / "modelo_dinamico_best.keras"\n\n        class EpochProgressCallback(tf.keras.callbacks.Callback):\n            def __init__(self, total_epochs, log_fn=None, progress_fn=None):\n                super().__init__()\n                self.total_epochs = total_epochs\n                self.log_fn = log_fn\n                self.progress_fn = progress_fn\n                self.t0 = None\n                self.epoch_times = []\n\n            def on_train_begin(self, logs=None):\n                self.t0 = time.time()\n\n            def on_epoch_begin(self, epoch, logs=None):\n                self._ep_start = time.time()\n\n            def on_epoch_end(self, epoch, logs=None):\n                logs = logs or {}\n                dur = time.time() - self._ep_start\n                self.epoch_times.append(dur)\n                media_ep = float(np.mean(self.epoch_times)) if self.epoch_times else dur\n                faltam = max(self.total_epochs - (epoch + 1), 0)\n                eta = media_ep * faltam\n                loss = float(logs.get("loss", 0.0))\n                acc = float(logs.get("accuracy", 0.0))\n                val_loss = float(logs.get("val_loss", 0.0))\n                val_acc = float(logs.get("val_accuracy", 0.0))\n\n                if self.log_fn:\n                    self.log_fn(\n                        f"📈 Época {epoch + 1}/{self.total_epochs} | "\n                        f"loss={loss:.4f} acc={acc:.4f} | "\n                        f"val_loss={val_loss:.4f} val_acc={val_acc:.4f} | "\n                        f"ETA ~ {eta/60:.1f} min"\n                    )\n                if self.progress_fn:\n                    self.progress_fn(epoch + 1, self.total_epochs, logs, eta)\n\n        callbacks = [\n            tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=18, restore_best_weights=True),\n            tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=6, min_lr=1e-6, verbose=0),\n            tf.keras.callbacks.ModelCheckpoint(\n                filepath=str(chk_path), monitor="val_loss",\n                save_best_only=True, save_weights_only=False, verbose=0,\n            ),\n            EpochProgressCallback(total_epochs=150, log_fn=log, progress_fn=progresso_epoca_cb),\n        ]\n\n        hist = model.fit(\n            Xtr_aug, ytr,\n            epochs=150,\n            batch_size=32,\n            validation_data=(Xte, yte),\n            callbacks=callbacks,\n            sample_weight=wtr_aug,\n            verbose=0,\n        )\n\n        if chk_path.exists():\n            try:\n                model = tf.keras.models.load_model(chk_path)\n            except Exception:\n                pass\n\n        _, acc = model.evaluate(Xte, yte, verbose=0)\n        pred = np.argmax(model.predict(Xte, verbose=0), axis=1)\n        report = classification_report(yte_s, pred, target_names=enc.classes_, zero_division=0)\n\n        self.modelo_dinamico = model\n        self.encoder_dinamico = enc\n\n        model.save(DIR_MODELOS / "modelo_dinamico.keras")\n        with open(DIR_MODELOS / "encoder_dinamico.pkl", "wb") as f:\n            pickle.dump(enc, f)\n\n        np.savez_compressed(\n            DIR_MODELOS / "normalizacao_dinamico.npz",\n            media=self.norm_media_din,\n            std=self.norm_std_din,\n        )\n\n        grafico = self._plotar_historico(hist)\n        msg = (\n            "✅ MODELO DINÂMICO TREINADO" + NL\n            + f"Acurácia: {acc:.2%} | Épocas executadas: {len(hist.history.get(\'loss\', []))}" + NL\n            + f"Classes treinadas: {n_classes}" + NL\n            + f"Amostras usadas: {qtd_amostras}" + NL\n            + f"Prioridades locais: {\', \'.join(sorted(prioridades)) if prioridades else \'(nenhuma)\'}" + NL\n        )\n        if grafico:\n            msg += f"📉 Gráfico salvo em: {grafico}" + NL\n        else:\n            msg += "📉 Gráfico não gerado (matplotlib indisponível)." + NL\n        msg += "─" * 50 + NL + report\n        return msg\n'


def substituir(texto, padrao, novo, nome):
    texto2, qtd = re.subn(padrao, novo, texto, flags=re.DOTALL)
    if qtd == 0:
        raise RuntimeError(f"Bloco não encontrado: {nome}")
    return texto2


def main():
    if not ARQUIVO_ORIGINAL.exists():
        raise FileNotFoundError("Não encontrei libras_recognizer.py na pasta atual.")

    shutil.copy2(ARQUIVO_ORIGINAL, BACKUP)
    texto = ARQUIVO_ORIGINAL.read_text(encoding="utf-8")
    texto = texto.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

    if "from mediapipe.framework.formats import landmark_pb2" not in texto:
        texto = texto.replace(
            "from mediapipe.tasks.python import vision",
            "from mediapipe.tasks.python import vision\nfrom mediapipe.framework.formats import landmark_pb2"
        )

    texto = re.sub(
        r'cmd\s*=\s*\[sys\.executable,\s*"-m",\s*"pip",\s*"install",\s*"tensorflow",\s*"--upgrade"\]',
        'cmd = [\n'
        '        sys.executable,\n'
        '        "-m",\n'
        '        "pip",\n'
        '        "install",\n'
        '        "tensorflow==2.16.1",\n'
        '        "numpy==1.26.4",\n'
        '        "ml-dtypes==0.3.2",\n'
        '        "--no-cache-dir"\n'
        '    ]', texto
    )

    texto = substituir(
        texto,
        r'class DetectorMaos:.*?(?=\n# ══════════════════════════════════════════════════════════════════════════════\n# GERENCIADOR DE DADOS)',
        NOVA_CLASSE_DETECTOR + "\n",
        "DetectorMaos"
    )

    texto = substituir(
        texto,
        r'    def _carregar_estatico\(self\):.*?(?=\n    # ──────────────────────────────────────────────────────────────────────────\n    # DINÂMICO \(LSTM\))',
        NOVA_CARREGAR_ESTATICO + "\n",
        "_carregar_estatico"
    )

    texto = substituir(
        texto,
        r'    def treinar_dinamico\(.*?(?=\n    def prever_dinamico\(self, sequencia\):)',
        NOVA_TREINAR_DINAMICO + "\n",
        "treinar_dinamico"
    )

    ARQUIVO_NOVO.write_text(texto, encoding="utf-8")
    py_compile.compile(str(ARQUIVO_NOVO), doraise=True)

    print("Arquivo gerado e validado com sucesso.")
    print(f"Novo arquivo: {ARQUIVO_NOVO.resolve()}")
    print(f"Backup criado: {BACKUP.resolve()}")
    print("Execute: python libras_recognizer_corrigido_v2.py")


if __name__ == "__main__":
    main()
