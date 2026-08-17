#!/usr/bin/env python
"""KONECTA V3 - Desktop GUI with Real-time Camera Recognition"""

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import numpy as np
import threading
import time
from pathlib import Path

from vision_lab.training import BaselineTrainer
from vision_lab.realtime import RealtimeRecognizer
from vision_lab.landmarks import LandmarkExtractor
from vision_lab.processing import LandmarkNormalizer

class KonectaV3GUI:
    """KONECTA V3 GUI Application"""

    def __init__(self, root):
        self.root = root
        self.root.title("KONECTA V3 - Real-time Sign Recognition")
        self.root.geometry("1200x800")

        # State
        self.camera_running = False
        self.model_trained = False
        self.trainer = None
        self.recognizer = None
        self.cap = None
        self.current_class = "CASA"
        self.training_data = []
        self.training_labels = []

        # Create UI
        self.create_widgets()

    def create_widgets(self):
        """Create GUI widgets"""

        # ============================================
        # TOP: Camera Display
        # ============================================

        camera_frame = ttk.Frame(self.root)
        camera_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Camera label (for video)
        self.camera_label = ttk.Label(camera_frame, text="Camera Feed", background="black")
        self.camera_label.pack(fill=tk.BOTH, expand=True)

        # ============================================
        # BOTTOM: Control Panel
        # ============================================

        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        # Left: Camera Controls
        left_panel = ttk.LabelFrame(control_frame, text="Camera", padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.start_btn = ttk.Button(left_panel, text="Iniciar Câmera", command=self.start_camera)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(left_panel, text="Parar Câmera", command=self.stop_camera, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Middle: Class Selection & Training
        middle_panel = ttk.LabelFrame(control_frame, text="Treinar", padding=10)
        middle_panel.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        ttk.Label(middle_panel, text="Classe:").pack(side=tk.LEFT, padx=5)

        self.class_var = tk.StringVar(value="CASA")
        self.class_combo = ttk.Combobox(
            middle_panel,
            textvariable=self.class_var,
            values=["CASA", "CARRO", "LIVRO", "AMAR", "APRENDER"],
            state="readonly",
            width=15
        )
        self.class_combo.pack(side=tk.LEFT, padx=5)

        self.capture_btn = ttk.Button(middle_panel, text="Capturar Frame", command=self.capture_frame, state=tk.DISABLED)
        self.capture_btn.pack(side=tk.LEFT, padx=5)

        self.train_btn = ttk.Button(middle_panel, text="Treinar Modelo", command=self.train_model)
        self.train_btn.pack(side=tk.LEFT, padx=5)

        # Right: Stats
        right_panel = ttk.LabelFrame(control_frame, text="Stats", padding=10)
        right_panel.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        self.stats_label = ttk.Label(right_panel, text="Frames: 0\nFPS: 0.0\nLatency: 0.0ms")
        self.stats_label.pack()

        # ============================================
        # STATUS BAR
        # ============================================

        self.status_var = tk.StringVar(value="Pronto. Clique em 'Iniciar Câmera'")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

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
        self.capture_btn.config(state=tk.NORMAL)
        self.status_var.set("Camera aberta. Selecione uma classe e clique em 'Capturar Frame'")

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
        extractor = LandmarkExtractor()
        frame_count = 0
        start_time = time.time()

        while self.camera_running:
            ret, frame = self.cap.read()
            if not ret:
                break

            # Flip for mirror effect
            frame = cv2.flip(frame, 1)

            # Try to extract landmarks
            from vision_lab.core import Frame as VFrame
            vframe = VFrame(frame_count, time.time(), frame)
            vframe = extractor.extract(vframe)

            # Draw landmarks if available
            if vframe.landmarks is not None:
                cv2.putText(frame, "Landmarks detectados!", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            else:
                cv2.putText(frame, "Detectando corpo...", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 2)

            # Show class
            cv2.putText(frame, f"Classe: {self.class_var.get()}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            # Show FPS
            frame_count += 1
            elapsed = time.time() - start_time
            if elapsed > 0:
                fps = frame_count / elapsed
                cv2.putText(frame, f"FPS: {fps:.1f}", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Convert to PhotoImage
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb)
            image = image.resize((640, 480), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)

            # Update label
            self.camera_label.config(image=photo)
            self.camera_label.image = photo

            # Update stats
            self.stats_label.config(text=f"Frames: {frame_count}\nFPS: {fps:.1f}\nCapturados: {len(self.training_labels)}")

            # Small delay
            time.sleep(0.01)

    def capture_frame(self):
        """Capture a frame for training"""
        if not self.camera_running or not self.cap:
            messagebox.showwarning("Aviso", "Camera nao esta aberta!")
            return

        ret, frame = self.cap.read()
        if not ret:
            messagebox.showerror("Erro", "Erro ao capturar frame!")
            return

        # Extract landmarks
        extractor = LandmarkExtractor()
        from vision_lab.core import Frame as VFrame
        vframe = VFrame(0, time.time(), frame)
        vframe = extractor.extract(vframe)

        if vframe.landmarks is None:
            messagebox.showwarning("Aviso", "Nao foi possivel detectar landmarks! Tente novamente.")
            return

        # Normalize
        landmarks = LandmarkNormalizer.normalize_body_centered(vframe.landmarks)

        # Store
        self.training_data.append(landmarks)
        self.training_labels.append(self.class_var.get())

        count = len(self.training_labels)
        self.status_var.set(f"Frame capturado! Total: {count} frames")
        messagebox.showinfo("Sucesso", f"Frame '{self.class_var.get()}' capturado! Total: {count}")

    def train_model(self):
        """Train model"""
        if len(self.training_data) < 2:
            messagebox.showwarning("Aviso", "Capture pelo menos 2 frames!")
            return

        self.status_var.set("Treinando modelo... Aguarde...")
        self.root.update()

        try:
            # Convert to numpy
            X_train = np.array(self.training_data, dtype=np.float32)
            y_train = np.array(self.training_labels)

            # Train
            self.trainer = BaselineTrainer(n_estimators=50)
            metrics = self.trainer.train(X_train, y_train)

            # Create recognizer
            self.recognizer = RealtimeRecognizer(model=self.trainer)
            self.model_trained = True

            msg = f"Modelo treinado!\n\nAccuracy: {metrics['accuracy']:.2%}\nF1: {metrics['f1']:.4f}\nClasses: {len(np.unique(y_train))}"
            messagebox.showinfo("Sucesso", msg)
            self.status_var.set("Modelo treinado! Pronto para reconhecer.")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao treinar: {str(e)}")
            self.status_var.set("Erro ao treinar modelo")

    def run(self):
        """Run application"""
        self.root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    app = KonectaV3GUI(root)
    app.run()
