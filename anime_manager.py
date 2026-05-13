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

# --- CONFIGURAÇÕES DE AMBIENTE ---
class Env:
    VERSION = "2.6.0"
    APP_NAME = "AnimeTrackerPro_V26"
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
    COLOR_DASH_ITEM = ("#DBDBDB", "#333333")
    COLOR_TEXT_DIM = ("#606060", "#A0A0A0")
    STATUS_OPTIONS = ["Assistindo", "Concluído", "Planejo Assistir"]

# --- UTILS & SAFETY ---
logging.basicConfig(filename=Env.LOG_PATH, level=logging.DEBUG, format='%(asctime)s | %(message)s')

def safe_int(v, default=0):
    try: return int(float(v))
    except: return default

def safe_float(v, default=0.0):
    try: return float(str(v).replace(',', '.'))
    except: return default

# --- PERSISTÊNCIA ATÔMICA ---
class Database:
    @staticmethod
    def load():
        if not Env.DB_PATH.exists(): return []
        try:
            with open(Env.DB_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []

    @staticmethod
    def save(data):
        fd, path = tempfile.mkstemp(dir=Env.DATA_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            os.replace(path, Env.DB_PATH)
        except Exception as e:
            logging.error(f"Save Error: {e}")

# --- IMAGE ENGINE ---
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
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(90, 130))
                cls._cache[url] = ctk_img
                callback(ctk_img)
            except: pass
        threading.Thread(target=dl, daemon=True).start()

# --- ANIME CARD COMPONENT ---
class AnimeCard(ctk.CTkFrame):
    def __init__(self, master, anime, app_instance):
        super().__init__(master, fg_color=Env.COLOR_CARD, corner_radius=12)
        self.anime = anime
        self.app = app_instance
        
        self.grid_columnconfigure(1, weight=1)
        
        # Capa com clique para editar
        self.img_label = ctk.CTkLabel(self, text="🎬", width=90, height=130, fg_color=("#D0D0D0", "#1A1A1A"), corner_radius=8)
        self.img_label.grid(row=0, column=0, rowspan=4, padx=10, pady=10)
        self.img_label.bind("<Button-1>", lambda e: self.app.load_edit_data(self.anime))
        
        if anime.get('cover'):
            ImageManager.get_image(anime['cover'], self.update_img)

        # Título (Clique para editar)
        lbl_title = ctk.CTkLabel(self, text=anime['title'], font=("Segoe UI", 13, "bold"), wraplength=150, justify="left", cursor="hand2")
        lbl_title.grid(row=0, column=1, sticky="nw", pady=(10, 0))
        lbl_title.bind("<Button-1>", lambda e: self.app.load_edit_data(self.anime))

        # Status Badge
        ctk.CTkLabel(self, text=anime.get('status', 'Assistindo'), font=("Segoe UI", 10, "bold"), text_color=Env.COLOR_ACCENT).grid(row=1, column=1, sticky="nw")

        # Progresso Texto
        curr, total = safe_int(anime['eps_current']), safe_int(anime['eps_total'])
        self.lbl_prog = ctk.CTkLabel(self, text=f"Ep: {curr} / {total}", font=("Segoe UI", 11))
        self.lbl_prog.grid(row=2, column=1, sticky="nw")

        # Barra de Progresso
        progress_val = (curr / total) if total > 0 else 0
        self.bar = ctk.CTkProgressBar(self, height=8, progress_color=Env.COLOR_ACCENT)
        self.bar.set(min(progress_val, 1.0))
        self.bar.grid(row=3, column=1, sticky="ew", padx=(0, 15), pady=(0, 10))

        # Quick Controls (Direita)
        ctrls = ctk.CTkFrame(self, fg_color="transparent")
        ctrls.grid(row=0, column=2, rowspan=4, padx=5)
        
        ctk.CTkButton(ctrls, text="+", width=28, height=28, command=lambda: self.app.quick_update(anime, 1)).pack(pady=2)
        ctk.CTkButton(ctrls, text="-", width=28, height=28, fg_color="#555555", command=lambda: self.app.quick_update(anime, -1)).pack(pady=2)
        ctk.CTkButton(ctrls, text="🗑", width=28, height=28, fg_color="#A12D2D", command=lambda: self.app.remove_anime(anime)).pack(pady=(10, 0))

    def update_img(self, img):
        try: self.img_label.configure(image=img, text="")
        except: pass

# --- MAIN APP ---
class AnimeManagerV26(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Anime Manager Pro V{Env.VERSION}")
        self.geometry("1280x900")
        
        # State
        self.anime_list = Database.load()
        self.current_cover_url = ""
        self.editing_id = None
        self.filter_status = "Todos"
        
        self.setup_layout()
        self.refresh_library()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # SIDEBAR
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="GERENCIADOR", font=("Segoe UI", 18, "bold")).pack(pady=20)
        
        # Search
        self.search_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Buscar Jikan...")
        self.search_entry.pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(self.sidebar, text="Pesquisar", command=self.search_jikan).pack(fill="x", padx=20)
        self.search_res = ctk.CTkScrollableFrame(self.sidebar, height=120, label_text="Resultados")
        self.search_res.pack(fill="x", padx=20, pady=10)

        # Form
        self.lbl_form = ctk.CTkLabel(self.sidebar, text="NOVO ANIME", font=("Segoe UI", 12, "bold"), text_color=Env.COLOR_ACCENT)
        self.lbl_form.pack(pady=5)
        
        self.fields = {}
        for label, key in [("Título", "title"), ("Ep. Atual", "curr"), ("Total Eps", "total"), ("Nota", "score")]:
            ctk.CTkLabel(self.sidebar, text=label, font=("Segoe UI", 11)).pack(anchor="w", padx=25)
            ent = ctk.CTkEntry(self.sidebar)
            ent.pack(fill="x", padx=20, pady=(0, 8))
            self.fields[key] = ent

        ctk.CTkLabel(self.sidebar, text="Status de Visualização", font=("Segoe UI", 11)).pack(anchor="w", padx=25)
        self.opt_status = ctk.CTkOptionMenu(self.sidebar, values=Env.STATUS_OPTIONS)
        self.opt_status.pack(fill="x", padx=20, pady=(0, 15))

        self.btn_save = ctk.CTkButton(self.sidebar, text="SALVAR NA BIBLIOTECA", fg_color="#28a745", font=("Segoe UI", 13, "bold"), height=40, command=self.save_anime)
        self.btn_save.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkButton(self.sidebar, text="Cancelar Edição", fg_color="#555555", command=self.clear_form).pack(fill="x", padx=20)

        # MAIN
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew", padx=25, pady=25)
        self.main.grid_columnconfigure(0, weight=1)

        # Dashboard 2.0
        self.dash_frame = ctk.CTkFrame(self.main, height=120, fg_color="transparent")
        self.dash_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        # Filtros e Ordenação
        filter_bar = ctk.CTkFrame(self.main, fg_color="transparent")
        filter_bar.grid(row=1, column=0, sticky="ew", pady=10)
        
        self.seg_filter = ctk.CTkSegmentedButton(filter_bar, values=["Todos"] + Env.STATUS_OPTIONS, command=self.set_filter)
        self.seg_filter.set("Todos")
        self.seg_filter.pack(side="left")

        self.library_scroll = ctk.CTkScrollableFrame(self.main)
        self.library_scroll.grid(row=2, column=0, sticky="nsew")
        self.library_scroll.grid_columnconfigure((0, 1, 2), weight=1)

    # --- LOGIC ---
    def set_filter(self, val):
        self.filter_status = val
        self.refresh_library()

    def update_dashboard(self):
        for w in self.dash_frame.winfo_children(): w.destroy()
        animes = self.anime_list
        stats = [
            ("Total", len(animes)),
            ("Assistidos", sum(safe_int(a['eps_current']) for a in animes)),
            ("Concluídos", sum(1 for a in animes if a.get('status') == 'Concluído')),
            ("Média", f"{sum(safe_float(a['score']) for a in animes)/(len(animes) or 1):.1f}")
        ]
        for label, val in stats:
            card = ctk.CTkFrame(self.dash_frame, fg_color=Env.COLOR_DASH_ITEM, corner_radius=10, width=150)
            card.pack(side="left", expand=True, padx=5, fill="both")
            ctk.CTkLabel(card, text=str(val), font=("Segoe UI", 24, "bold"), text_color=Env.COLOR_ACCENT).pack(pady=(15, 0))
            ctk.CTkLabel(card, text=label, font=("Segoe UI", 12)).pack(pady=(0, 15))

    def save_anime(self):
        data = {
            "title": self.fields['title'].get(),
            "eps_current": self.fields['curr'].get() or "0",
            "eps_total": self.fields['total'].get() or "0",
            "score": self.fields['score'].get() or "0",
            "status": self.opt_status.get(),
            "cover": self.current_cover_url
        }
        
        if self.editing_id:
            for i, a in enumerate(self.anime_list):
                if a['id'] == self.editing_id:
                    data['id'] = self.editing_id
                    self.anime_list[i] = data
                    break
        else:
            data['id'] = int(datetime.now().timestamp() * 1000)
            self.anime_list.append(data)
            
        Database.save(self.anime_list)
        self.clear_form()
        self.refresh_library()

    def load_edit_data(self, anime):
        self.editing_id = anime['id']
        self.lbl_form.configure(text="EDITANDO: " + anime['title'][:15], text_color="#ffcc00")
        self.fields['title'].insert(0, anime['title'])
        self.fields['curr'].insert(0, anime['eps_current'])
        self.fields['total'].insert(0, anime['eps_total'])
        self.fields['score'].insert(0, anime['score'])
        self.opt_status.set(anime.get('status', 'Assistindo'))
        self.current_cover_url = anime.get('cover', "")

    def quick_update(self, anime, delta):
        curr = safe_int(anime['eps_current']) + delta
        total = safe_int(anime['eps_total'])
        anime['eps_current'] = str(max(0, curr if total == 0 else min(curr, total)))
        if total > 0 and int(anime['eps_current']) == total:
            anime['status'] = "Concluído"
        Database.save(self.anime_list)
        self.refresh_library()

    def refresh_library(self):
        for w in self.library_scroll.winfo_children(): w.destroy()
        filtered = [a for a in self.anime_list if self.filter_status == "Todos" or a.get('status') == self.filter_status]
        for i, anime in enumerate(filtered):
            card = AnimeCard(self.library_scroll, anime, self)
            card.grid(row=i//3, column=i%3, padx=10, pady=10, sticky="nsew")
        self.update_dashboard()

    def clear_form(self):
        self.editing_id = None
        self.current_cover_url = ""
        self.lbl_form.configure(text="NOVO ANIME", text_color=Env.COLOR_ACCENT)
        for f in self.fields.values(): f.delete(0, 'end')

    def search_jikan(self):
        q = self.search_entry.get()
        def run():
            try:
                res = requests.get(f"https://api.jikan.moe/v4/anime?q={q}&limit=5").json()
                self.after(0, lambda: self.render_search(res.get('data', [])))
            except: pass
        threading.Thread(target=run, daemon=True).start()

    def render_search(self, results):
        for w in self.search_res.winfo_children(): w.destroy()
        for item in results:
            btn = ctk.CTkButton(self.search_res, text=item['title'], fg_color="transparent", anchor="w", command=lambda i=item: self.pick_jikan(i))
            btn.pack(fill="x")

    def pick_jikan(self, item):
        self.clear_form()
        self.fields['title'].insert(0, item['title'])
        self.fields['total'].insert(0, str(item.get('episodes') or "0"))
        self.current_cover_url = item['images']['jpg']['image_url']

    def remove_anime(self, anime):
        if messagebox.askyesno("Excluir", f"Remover {anime['title']}?"):
            self.anime_list = [a for a in self.anime_list if a['id'] != anime['id']]
            Database.save(self.anime_list)
            self.refresh_library()

    def on_closing(self):
        Database.save(self.anime_list)
        self.destroy()

if __name__ == "__main__":
    app = AnimeManagerV26()
    app.mainloop()