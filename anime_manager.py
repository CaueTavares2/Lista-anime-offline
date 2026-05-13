import os
import sys
import json
import logging
import threading
import tempfile
import requests
import random
import io
from pathlib import Path
from datetime import datetime
from PIL import Image
import customtkinter as ctk
from tkinter import messagebox

# --- INTEGRAÇÃO DISCORD RPC ---
try:
    from pypresence import Presence
    RPC_AVAILABLE = True
except ImportError:
    RPC_AVAILABLE = False

# --- CONFIGURAÇÕES DE AMBIENTE ---
class Env:
    VERSION = "3.0.1"
    APP_NAME = "Anime Tracker Ecosystem"
    CLIENT_ID = "1214567890123456789" # ID de Aplicação
    
    if getattr(sys, 'frozen', False):
        BASE_DIR = Path(sys.executable).parent
    else:
        BASE_DIR = Path(__file__).parent.absolute()

    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(exist_ok=True)
    DB_PATH = DATA_DIR / "animes.json"
    LOG_PATH = DATA_DIR / "debug_log.txt"
    
    COLOR_ACCENT = ("#3B8ED0", "#1F6AA5")
    COLOR_CARD = ("#EBEBEB", "#2B2B2B")
    COLOR_DASH_ITEM = ("#D1D1D1", "#333333")

logging.basicConfig(filename=Env.LOG_PATH, level=logging.DEBUG, format='%(asctime)s | %(message)s')

# --- GESTÃO DE DADOS ATÔMICA ---
class Database:
    @staticmethod
    def load():
        if not Env.DB_PATH.exists(): 
            return {"user": "Otaku", "rpc": True, "list": []}
        try:
            with open(Env.DB_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if "list" in data else {"user": "Otaku", "rpc": True, "list": data}
        except: 
            return {"user": "Otaku", "rpc": True, "list": []}

    @staticmethod
    def save(data):
        fd, path = tempfile.mkstemp(dir=Env.DATA_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            os.replace(path, Env.DB_PATH)
        except Exception as e:
            logging.error(f"Falha Atômica: {e}")

# --- IMAGE ENGINE ASYNC ---
class ImageManager:
    _cache = {}
    @classmethod
    def get_image(cls, url, callback):
        if not url or url in cls._cache:
            if url in cls._cache: callback(cls._cache[url])
            return
        def dl():
            try:
                r = requests.get(url, timeout=5)
                img = Image.open(io.BytesIO(r.content))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(100, 145))
                cls._cache[url] = ctk_img
                callback(ctk_img)
            except: pass
        threading.Thread(target=dl, daemon=True).start()

# --- COMPONENTES DE UI ---
class ConcludeRitual(ctk.CTkToplevel):
    def __init__(self, parent, anime, save_callback):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"400x350+{(self.winfo_screenwidth()//2)-200}+{(self.winfo_screenheight()//2)-175}")
        
        self.anime = anime
        self.save_callback = save_callback
        
        f = ctk.CTkFrame(self, border_width=2, border_color="#FFD700")
        f.pack(fill="both", expand=True)
        
        ctk.CTkLabel(f, text="✨ JORNADA CONCLUÍDA ✨", font=("Segoe UI", 22, "bold"), text_color="#FFD700").pack(pady=20)
        ctk.CTkLabel(f, text=f"Parabéns por finalizar\n{anime['title']}", wraplength=350).pack(pady=10)
        
        ctk.CTkLabel(f, text="Qual a nota final desta obra? (0-10)", font=("Segoe UI", 11)).pack(pady=10)
        self.ent_score = ctk.CTkEntry(f, placeholder_text="Ex: 9.5", width=120, justify="center")
        self.ent_score.pack()
        
        ctk.CTkButton(f, text="ENCERRAR RITUAL", fg_color="#28a745", command=self.finalize).pack(pady=30, padx=40, fill="x")

    def finalize(self):
        score = self.ent_score.get() or "0"
        self.save_callback(self.anime, score)
        self.destroy()

class AnimeCard(ctk.CTkFrame):
    def __init__(self, master, anime, app):
        super().__init__(master, fg_color=Env.COLOR_CARD, corner_radius=12)
        self.grid_columnconfigure(1, weight=1)
        self.anime = anime
        self.app = app
        
        self.img_lbl = ctk.CTkLabel(self, text="🎬", width=100, height=145, fg_color=("#CCCCCC", "#1A1A1A"), corner_radius=8)
        self.img_lbl.grid(row=0, column=0, rowspan=4, padx=12, pady=12)
        
        ctk.CTkLabel(self, text=anime['title'], font=("Segoe UI", 13, "bold"), wraplength=180, justify="left").grid(row=0, column=1, sticky="nw", pady=(15,0))
        
        curr, total = int(anime['eps_current']), int(anime['eps_total'])
        ctk.CTkLabel(self, text=f"Ep: {curr} / {total}", font=("Segoe UI", 11)).grid(row=1, column=1, sticky="nw")
        
        self.bar = ctk.CTkProgressBar(self, height=8, progress_color=Env.COLOR_ACCENT)
        self.bar.set(curr/total if total > 0 else 0)
        self.bar.grid(row=2, column=1, sticky="ew", padx=(0, 20))

        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.grid(row=0, column=2, rowspan=4, padx=10)
        ctk.CTkButton(btn_f, text="+", width=30, command=lambda: self.app.quick_up(anime, 1)).pack(pady=5)
        ctk.CTkButton(btn_f, text="-", width=30, fg_color="#555555", command=lambda: self.app.quick_up(anime, -1)).pack(pady=5)
        ctk.CTkButton(btn_f, text="🗑", width=30, fg_color="#A12D2D", command=lambda: self.app.delete_anime(anime)).pack(pady=15)

        if anime.get('cover'): ImageManager.get_image(anime['cover'], self.set_img)

    def set_img(self, img):
        try: self.img_lbl.configure(image=img, text="")
        except: pass

# --- MAIN ENGINE ---
class AnimeManagerV3(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.is_fullscreen = True
        self.attributes("-fullscreen", True)
        
        # Splash Setup
        self.splash = ctk.CTkToplevel()
        self.splash.overrideredirect(True)
        self.splash.attributes("-topmost", True)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.splash.geometry(f"400x250+{(sw//2)-200}+{(sh//2)-125}")
        
        splash_f = ctk.CTkFrame(self.splash, border_width=2, border_color=Env.COLOR_ACCENT)
        splash_f.pack(fill="both", expand=True)
        ctk.CTkLabel(splash_f, text="ANIME MANAGER PRO", font=("Segoe UI", 22, "bold")).pack(pady=40)
        self.splash_prog = ctk.CTkProgressBar(splash_f, width=300)
        self.splash_prog.pack(pady=20)
        self.splash_prog.set(0)

        # Iniciar Carregamento em Thread
        self.data_ready = False
        threading.Thread(target=self.boot_process, daemon=True).start()
        self.check_boot()

    def boot_process(self):
        # 1. Carregar DB
        self.db_data = Database.load()
        self.anime_list = self.db_data['list']
        # 2. RPC Discord
        self.rpc = None
        if RPC_AVAILABLE and self.db_data.get('rpc', True):
            try:
                self.rpc = Presence(Env.CLIENT_ID)
               