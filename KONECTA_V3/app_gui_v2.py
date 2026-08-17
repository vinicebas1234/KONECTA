#!/usr/bin/env python
"""KONECTA V3 - Desktop GUI with Real-time Camera Recognition (Completo)"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
from PIL import Image, ImageTk
import numpy as np
import threading
import time
from pathlib import Path
import pickle

from vision_lab.training import BaselineTrainer
from vision_lab.realtime import RealtimeRecognizer
from vision_lab.landmarks import LandmarkExtractor, LandmarkVisualizer
from vision_lab.processing import LandmarkNormalizer
from vision_lab.core import Frame as VFrame

class KonectaV3GUIV2:
    """KONECTA V3 GUI Application - Complete Version"""

    def __init__(self, root):
        self.root = root
        self.root.title("KONECTA V3 - Reconhecimento de Libras em Tempo Real")
        self.root.geometry("1400x900")
        self.root.resizable(True, True)

        # State
        self.camera_running = False
        self.mode = "TRAIN"  # TRAIN or RECOGNIZE
        self.trainer = None
        self.recognizer = None
        self.extractor = LandmarkExtractor()
        self.cap = None
        self.current_class = "CASA"
        self.training_data = []
        self.training_labels = []
        self.history = []
        self.last_prediction = None
        self.last_confidence = 0.0

        # Create UI
        self.create_widgets()

    def create_widgets(self):
        """Create GUI widgets"""

        # ============================================
        # TOP: Title Bar
        # ============================================

        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(title_frame, text="KONECTA V3 - Reconhecimento de Libras", font=("Arial", 16, "bold")).pack(side=tk.LEFT)

        self.mode_label = ttk.Label(title_frame, text="Modo: TREINAMENTO", font=("Arial", 12), foreground="blue")
        self.mode_label.pack(side=tk.RIGHT)

        # ============================================
        # MAIN: Split View (Left: Camera, Right: Control)
        # ============================================

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # LEFT: Camera Feed
        left_frame = ttk.LabelFrame(main_frame, text="Câmera", padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.camera_label = ttk.Label(left_frame, text="Clique 'Iniciar Câmera'", background="black", foreground="white")
        self.camera_label.pack(fill=tk.BOTH, expand=True)

        # RIGHT: Control Panel
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10)

        # === SECTION 1: Camera Controls ===
        camera_ctl_frame = ttk.LabelFrame(right_frame, text="Câmera", padding=10)
        camera_ctl_frame.pack(fill=tk.X, pady=5)

        self.start_btn = ttk.Button(camera_ctl_frame, text="Iniciar Câmera", command=self.start_camera)
        self.start_btn.pack(fill=tk.X, pady=2)

        self.stop_btn = ttk.Button(camera_ctl_frame, text="Parar Câmera", command=self.stop_camera, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, pady=2)

        # === SECTION 2: Mode Selection ===
        mode_frame = ttk.LabelFrame(right_frame, text="Modo", padding=10)
        mode_frame.pack(fill=tk.X, pady=5)

        self.mode_var = tk.StringVar(value="TRAIN")
        ttk.Radiobutton(mode_frame, text="Treinamento", variable=self.mode_var, value="TRAIN", command=self.switch_mode).pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="Reconhecimento", variable=self.mode_var, value="RECOGNIZE", command=self.switch_mode).pack(anchor=tk.W)

        # === SECTION 3: Training ===
        self.train_frame = ttk.LabelFrame(right_frame, text="Treinamento", padding=10)
        self.train_frame.pack(fill=tk.X, pady=5)

        ttk.Label(self.train_frame, text="Classe:").pack(anchor=tk.W)
        self.class_var = tk.StringVar(value="CASA")
        self.class_combo = ttk.Combobox(
            self.train_frame,
            textvariable=self.class_var,
            values=["CASA", "CARRO", "LIVRO", "AMAR", "APRENDER"],
            state="readonly"
        )
        self.class_combo.pack(fill=tk.X, pady=5)

        ttk.Label(self.train_frame, text="Capturados:").pack(anchor=tk.W)
        self.captured_label = ttk.Label(self.train_frame, text="0 frames", font=("Arial", 12, "bold"), foreground="green")
        self.captured_label.pack(anchor=tk.W, pady=5)

        # Capture Mode
        ttk.Label(self.train_frame, text="Modo de Captura:").pack(anchor=tk.W, pady=(5, 5))

        self.capture_mode = tk.StringVar(value="SINGLE")
        ttk.Radiobutton(self.train_frame, text="Um Frame", variable=self.capture_mode, value="SINGLE").pack(anchor=tk.W)
        ttk.Radiobutton(self.train_frame, text="Contínuo (5 frames)", variable=self.capture_mode, value="CONTINUOUS").pack(anchor=tk.W)

        self.capture_btn = ttk.Button(self.train_frame, text="Capturar", command=self.capture_frame, state=tk.DISABLED)
        self.capture_btn.pack(fill=tk.X, pady=2)

        # Data Management
        ttk.Label(self.train_frame, text="Gerenciar Dados:").pack(anchor=tk.W, pady=(10, 5))

        data_btn_frame = ttk.Frame(self.train_frame)
        data_btn_frame.pack(fill=tk.X)

        self.view_btn = ttk.Button(data_btn_frame, text="Ver Frames", command=self.view_frames, width=12)
        self.view_btn.pack(side=tk.LEFT, padx=2)

        self.delete_btn = ttk.Button(data_btn_frame, text="Limpar Dados", command=self.clear_data, width=12)
        self.delete_btn.pack(side=tk.LEFT, padx=2)

        self.train_btn = ttk.Button(self.train_frame, text="Treinar Modelo", command=self.train_model)
        self.train_btn.pack(fill=tk.X, pady=2)

        # === SECTION 4: Recognition ===
        self.recognize_frame = ttk.LabelFrame(right_frame, text="Reconhecimento", padding=10)
        self.recognize_frame.pack(fill=tk.X, pady=5)

        ttk.Label(self.recognize_frame, text="Predição:").pack(anchor=tk.W)
        self.prediction_label = ttk.Label(self.recognize_frame, text="---", font=("Arial", 14, "bold"), foreground="blue")
        self.prediction_label.pack(anchor=tk.W, pady=5)

        ttk.Label(self.recognize_frame, text="Confiança:").pack(anchor=tk.W)
        self.confidence_label = ttk.Label(self.recognize_frame, text="0%", font=("Arial", 12, "bold"), foreground="orange")
        self.confidence_label.pack(anchor=tk.W, pady=5)

        self.recognize_frame.pack_forget()  # Hide initially

        # === SECTION 5: Model Management ===
        model_frame = ttk.LabelFrame(right_frame, text="Modelo", padding=10)
        model_frame.pack(fill=tk.X, pady=5)

        self.save_btn = ttk.Button(model_frame, text="Salvar Modelo", command=self.save_model, state=tk.DISABLED)
        self.save_btn.pack(fill=tk.X, pady=2)

        self.load_btn = ttk.Button(model_frame, text="Carregar Modelo", command=self.load_model)
        self.load_btn.pack(fill=tk.X, pady=2)

        # === SECTION 6: Stats ===
        stats_frame = ttk.LabelFrame(right_frame, text="Estatísticas", padding=10)
        stats_frame.pack(fill=tk.X, pady=5)

        self.stats_label = ttk.Label(stats_frame, text="FPS: 0.0\nLatency: 0.0ms")
        self.stats_label.pack(anchor=tk.W)

        # === SECTION 7: History ===
        history_frame = ttk.LabelFrame(right_frame, text="Histórico", padding=10)
        history_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.history_text = tk.Text(history_frame, height=5, width=30)
        self.history_text.pack(fill=tk.BOTH, expand=True)

        # ============================================
        # STATUS BAR
        # ============================================

        self.status_var = tk.StringVar(value="Pronto. Clique em 'Iniciar Câmera'")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def switch_mode(self):
        """Switch between training and recognition mode"""
        mode = self.mode_var.get()

        if mode == "TRAIN":
            self.train_frame.pack(fill=tk.X, pady=5)
            self.recognize_frame.pack_forget()
            self.mode_label.config(text="Modo: TREINAMENTO", foreground="blue")
            self.status_var.set("Modo TREINAMENTO - Selecione classe e capture frames")

        else:  # RECOGNIZE
            if not self.trainer:
                messagebox.showwarning("Aviso", "Treine um modelo primeiro!")
                self.mode_var.set("TRAIN")
                self.switch_mode()
                return

            self.train_frame.pack_forget()
            self.recognize_frame.pack(fill=tk.X, pady=5)
            self.mode_label.config(text="Modo: RECONHECIMENTO", foreground="green")
            self.status_var.set("Modo RECONHECIMENTO - Faça o sinal!")

    def start_camera(self):
        """Start camera"""
        self.camera_running = True
        self.cap = cv2.VideoCapture(0)

        if not self.cap.isOpened():
            messagebox.showerror("Erro", "Nao foi possivel abrir a camera!")
            self.camera_running = False
            return

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        if self.mode_var.get() == "TRAIN":
            self.capture_btn.config(state=tk.NORMAL)

        self.status_var.set("Camera aberta!")

        # Start camera thread
        thread = threading.Thread(target=self.camera_loop, daemon=True)
        thread.start()

    def stop_camera(self):
        """Stop camera"""
        self.camera_running = False
        if self.cap:
            self.cap.release()

        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.capture_btn.config(state=tk.DISABLED)
        self.status_var.set("Camera fechada")

    def camera_loop(self):
        """Main camera loop"""
        frame_count = 0
        start_time = time.time()

        while self.camera_running and self.cap:
            ret, frame = self.cap.read()
            if not ret:
                break

            # Flip for mirror effect
            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]

            # Extract landmarks
            vframe = VFrame(frame_count, time.time(), frame)
            vframe = self.extractor.extract(vframe)

            # Draw landmarks if available
            if vframe.landmarks is not None:
                try:
                    frame = LandmarkVisualizer.draw_landmarks(vframe, vframe.landmarks)
                except:
                    pass
                cv2.putText(frame, "OK: Landmarks detectados", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            else:
                cv2.putText(frame, "Detectando corpo...", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 2)

            # TRAINING MODE: Show class
            if self.mode_var.get() == "TRAIN":
                cv2.putText(frame, f"Classe: {self.class_var.get()}", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            # RECOGNITION MODE: Show prediction
            else:
                if self.recognizer and vframe.landmarks is not None:
                    try:
                        pred, conf, lat = self.recognizer.process_frame(frame)
                        if pred:
                            self.last_prediction = pred
                            self.last_confidence = conf
                            color = (0, 255, 0) if conf > 0.8 else (0, 165, 255)
                            cv2.putText(frame, f"Sinal: {pred} ({conf:.1%})", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                            self.add_to_history(f"{pred} ({conf:.1%})")
                    except:
                        pass

            # Show FPS
            frame_count += 1
            elapsed = time.time() - start_time
            if elapsed > 0:
                fps = frame_count / elapsed
                cv2.putText(frame, f"FPS: {fps:.1f}", (20, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Convert to PhotoImage
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb)
            image = image.resize((640, 480), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)

            self.camera_label.config(image=photo)
            self.camera_label.image = photo

            # Update prediction label in recognition mode
            if self.mode_var.get() == "RECOGNIZE":
                self.prediction_label.config(text=self.last_prediction or "---")
                self.confidence_label.config(text=f"{self.last_confidence:.1%}")

            # Update stats
            self.stats_label.config(text=f"FPS: {fps:.1f}\nFrames: {frame_count}\nCapturados: {len(self.training_labels)}")

            time.sleep(0.01)

    def capture_frame(self):
        """Capture frame(s) for training"""
        if not self.camera_running or not self.cap:
            messagebox.showwarning("Aviso", "Camera nao esta aberta!")
            return

        mode = self.capture_mode.get()
        num_frames = 5 if mode == "CONTINUOUS" else 1
        captured = 0

        for _ in range(num_frames):
            ret, frame = self.cap.read()
            if not ret:
                break

            # Extract landmarks
            vframe = VFrame(0, time.time(), frame)
            vframe = self.extractor.extract(vframe)

            if vframe.landmarks is None:
                continue

            # Normalize
            landmarks = LandmarkNormalizer.normalize_body_centered(vframe.landmarks)

            # Store
            self.training_data.append(landmarks)
            self.training_labels.append(self.class_var.get())
            captured += 1

            time.sleep(0.05)  # Small delay between frames

        if captured == 0:
            messagebox.showwarning("Aviso", "Nao foi possivel detectar landmarks!")
            return

        count = len(self.training_labels)
        self.captured_label.config(text=f"{count} frames")
        msg = f"{captured} frame(s) '{self.class_var.get()}' capturado(s)!" if mode == "CONTINUOUS" else f"Frame capturado! Total: {count}"
        self.status_var.set(msg)

    def train_model(self):
        """Train model"""
        if len(self.training_data) < 2:
            messagebox.showwarning("Aviso", "Capture pelo menos 2 frames de classes diferentes!")
            return

        self.status_var.set("Treinando modelo...")
        self.root.update()

        try:
            X_train = np.array(self.training_data, dtype=np.float32)
            y_train = np.array(self.training_labels)

            self.trainer = BaselineTrainer(n_estimators=50)
            metrics = self.trainer.train(X_train, y_train)

            self.recognizer = RealtimeRecognizer(model=self.trainer)
            self.save_btn.config(state=tk.NORMAL)

            msg = f"Modelo treinado com sucesso!\n\nAccuracy: {metrics['accuracy']:.2%}\nF1: {metrics['f1']:.4f}\nClasses: {len(np.unique(y_train))}"
            messagebox.showinfo("Sucesso", msg)
            self.status_var.set("Modelo treinado! Pode reconhecer agora.")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao treinar: {str(e)}")

    def view_frames(self):
        """View captured frames"""
        if not self.training_data:
            messagebox.showinfo("Aviso", "Nenhum frame capturado!")
            return

        # Count by class
        from collections import Counter
        class_counts = Counter(self.training_labels)

        msg = "Frames Capturados:\n\n"
        for cls, count in sorted(class_counts.items()):
            msg += f"{cls}: {count} frames\n"

        msg += f"\nTotal: {len(self.training_labels)} frames"
        messagebox.showinfo("Dados Capturados", msg)

    def clear_data(self):
        """Clear all training data"""
        if not self.training_data:
            messagebox.showinfo("Aviso", "Nenhum dado para limpar!")
            return

        if messagebox.askyesno("Confirmar", "Tem certeza que quer limpar TODOS os dados?"):
            self.training_data = []
            self.training_labels = []
            self.captured_label.config(text="0 frames")
            self.status_var.set("Dados limpos!")

    def add_to_history(self, text):
        """Add text to history"""
        self.history.append(text)
        if len(self.history) > 10:
            self.history.pop(0)

        self.history_text.config(state=tk.NORMAL)
        self.history_text.delete("1.0", tk.END)
        self.history_text.insert(tk.END, "\n".join(self.history))
        self.history_text.config(state=tk.DISABLED)

    def save_model(self):
        """Save trained model"""
        if not self.trainer:
            messagebox.showwarning("Aviso", "Nenhum modelo treinado!")
            return

        path = filedialog.asksaveasfilename(defaultextension=".model", filetypes=[("Model Files", "*.model")])
        if path:
            try:
                self.trainer.save(path)
                messagebox.showinfo("Sucesso", f"Modelo salvo em:\n{path}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar: {str(e)}")

    def load_model(self):
        """Load trained model"""
        path = filedialog.askopenfilename(filetypes=[("Model Files", "*.model")])
        if path:
            try:
                self.trainer = BaselineTrainer.load(path)
                self.recognizer = RealtimeRecognizer(model=self.trainer)
                self.save_btn.config(state=tk.NORMAL)
                messagebox.showinfo("Sucesso", "Modelo carregado!")
                self.status_var.set("Modelo carregado. Pronto para reconhecer!")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao carregar: {str(e)}")

    def run(self):
        """Run application"""
        self.root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    app = KonectaV3GUIV2(root)
    app.run()
