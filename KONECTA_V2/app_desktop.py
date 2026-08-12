"""
App Desktop KONECTA - Simples e robusto
Captura frames → Envia ao backend → Backend processa com MediaPipe
"""

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import numpy as np
import requests
import base64
import os
import warnings

os.environ['OPENCV_LOG_LEVEL'] = 'OFF'
warnings.filterwarnings('ignore')

class KonectaDesktop:
    def __init__(self, root):
        self.root = root
        self.root.title("KONECTA V2")
        self.root.geometry("1000x700")

        # Camera
        self.cap = cv2.VideoCapture(1)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # Estado
        self.capturando = False
        self.frames_buffer = []
        self.sinal_nome = ""

        self.create_ui()
        self.update_frame()

    def create_ui(self):
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Video
        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(left, bg='black', width=640, height=480)
        self.canvas.pack()

        # Controls
        right = ttk.Frame(main)
        right.pack(side=tk.RIGHT, padx=20, fill=tk.BOTH)

        ttk.Button(right, text="🔍 Testar", command=self.testar).pack(fill=tk.X, pady=5)
        self.status = ttk.Label(right, text="Aguardando...", foreground="blue")
        self.status.pack(fill=tk.X, pady=5)

        ttk.Separator(right).pack(fill=tk.X, pady=10)

        ttk.Label(right, text="Sinal:").pack()
        self.sinal_entry = ttk.Entry(right, width=20)
        self.sinal_entry.pack(fill=tk.X, pady=5)

        ttk.Label(right, text="Frames:").pack()
        self.frame_label = ttk.Label(right, text="0", font=('Arial', 20, 'bold'))
        self.frame_label.pack()

        self.btn_cap = ttk.Button(right, text="📹 Iniciar", command=self.toggle_cap)
        self.btn_cap.pack(fill=tk.X, pady=5)

        ttk.Button(right, text="🚀 Treinar", command=self.treinar).pack(fill=tk.X, pady=5)
        ttk.Button(right, text="✓ Reconhecer", command=self.reconhecer).pack(fill=tk.X, pady=5)

        self.result = ttk.Label(right, text="-", font=('Arial', 14, 'bold'), foreground='blue')
        self.result.pack(fill=tk.X, pady=10)

        ttk.Label(right, text="Log:").pack()
        self.log_text = tk.Text(right, height=10, width=30)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, msg):
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def testar(self):
        try:
            r = requests.get('http://localhost:9000/api/health', timeout=3)
            if r.status_code == 200:
                self.status.config(text="✅ Backend OK", foreground="green")
                self.log("✓ Conectado!")
            else:
                self.status.config(text="❌ Erro", foreground="red")
        except:
            self.status.config(text="❌ Sem conexão", foreground="red")
            self.log("❌ Backend não respondeu")

    def toggle_cap(self):
        sinal = self.sinal_entry.get().strip().upper()
        if not sinal:
            messagebox.showwarning("Aviso", "Digite o sinal!")
            return

        if not self.capturando:
            self.capturando = True
            self.sinal_nome = sinal
            self.frames_buffer = []
            self.btn_cap.config(text="⏹️ Parar")
            self.log(f"🔴 Capturando {sinal}...")
        else:
            self.capturando = False
            self.btn_cap.config(text="📹 Iniciar")
            self.log(f"✓ Parado. {len(self.frames_buffer)} frames")

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            self.root.after(30, self.update_frame)
            return

        frame = cv2.flip(frame, 1)

        if self.capturando:
            self.frames_buffer.append(frame.copy())
            self.frame_label.config(text=str(len(self.frames_buffer)))

        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        img_tk = ImageTk.PhotoImage(img_pil)
        self.canvas.create_image(0, 0, image=img_tk, anchor=tk.NW)
        self.canvas.image = img_tk

        self.root.after(30, self.update_frame)

    def treinar(self):
        if not self.sinal_nome or not self.frames_buffer:
            messagebox.showwarning("Aviso", "Capture frames!")
            return

        self.log("📤 Processando...")

        try:
            # Codificar frames
            frames_b64 = []
            for frame in self.frames_buffer:
                _, buf = cv2.imencode('.jpg', frame)
                frames_b64.append(base64.b64encode(buf).decode())

            # Enviar ao backend
            payload = {"sinal": self.sinal_nome, "frames": frames_b64}
            r = requests.post('http://localhost:9000/api/processar-frames', json=payload, timeout=30)

            if r.status_code == 200:
                data = r.json()
                if data.get('sucesso'):
                    lms = data.get('landmarks', [])
                    self.log(f"✅ {len(lms)} frames processados")

                    # Treinar
                    dados = {self.sinal_nome: lms}
                    r2 = requests.post('http://localhost:9000/api/treinar', json=dados, timeout=30)
                    res2 = r2.json()

                    if res2.get('sucesso'):
                        self.log("✅ Modelo treinado!")
                        self.log(res2.get('mensagem', ''))
                        self.frames_buffer = []
                        self.frame_label.config(text="0")
                    else:
                        self.log(f"❌ {res2.get('erro', '')}")
                else:
                    self.log(f"❌ {data.get('erro', '')}")
            else:
                self.log(f"❌ Erro {r.status_code}")

        except Exception as e:
            self.log(f"❌ {str(e)[:50]}")

    def reconhecer(self):
        if not self.sinal_nome or not self.frames_buffer:
            messagebox.showwarning("Aviso", "Capture frames!")
            return

        self.log("🎯 Reconhecendo...")

        try:
            frames_b64 = []
            for frame in self.frames_buffer[:30]:
                _, buf = cv2.imencode('.jpg', frame)
                frames_b64.append(base64.b64encode(buf).decode())

            payload = {"sinal": self.sinal_nome, "frames": frames_b64}
            r = requests.post('http://localhost:9000/api/processar-frames', json=payload, timeout=30)

            if r.status_code == 200:
                data = r.json()
                lms = data.get('landmarks', [])

                # Flatten landmarks
                lms_flat = []
                for frame_lm in lms:
                    for point in frame_lm:
                        lms_flat.extend(point)

                r2 = requests.post('http://localhost:9000/api/reconhecer', json=lms_flat, timeout=10)
                res = r2.json()

                sinal = res.get('sinal', '?')
                conf = res.get('confianca', 0) * 100
                cor = 'green' if conf > 65 else 'orange'
                self.result.config(text=f"{sinal}\n{conf:.0f}%", foreground=cor)
                self.log(f"✓ {sinal} - {conf:.1f}%")
            else:
                self.log(f"❌ Erro {r.status_code}")

        except Exception as e:
            self.log(f"❌ {str(e)[:50]}")


if __name__ == '__main__':
    root = tk.Tk()
    app = KonectaDesktop(root)
    root.mainloop()
