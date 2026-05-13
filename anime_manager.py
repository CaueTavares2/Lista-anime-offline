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
    VERSION = "2.5.0"
    APP_NAME = "AnimeTrackerPro_V25"
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
    COLOR_TEXT_DIM = ("#606060", "#A0A0A0")

# --- LOGGING ---
logging.basicConfig(
    filename=Env.LOG_PATH, level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(message)s', encoding='utf-8'
)

# --- UTILITÁRIOS DE SEGURANÇA ---
def safe_int(value, default=0):
    try:
        if value is None or str(value).strip() == "": return default
        return int(float(value))
    except: return default

def safe_float(value, default=0.0):
    try:
        if value is None or str(value).strip() == "": return default
        return float(str(value).replace(',', '.'))
    except: return default

# --- PERSISTÊNCIA ATÔMICA ---
class Database:
    @staticmethod
    def load():
        if not Env.DB_PATH.exists(): return []
        try:
            with open(Env.DB_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logging.error(f"Erro ao carregar DB: {e}")
            return []

    @staticmethod
    def save(data):
        temp_fd, temp_path = tempfile.mkstemp(dir=Env.DATA_DIR, suffix=".tmp")
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            os.replace(temp_path, Env.DB_PATH)
        except Exception as e:
            logging.error(f"Erro no salvamento: {e}")
            if os.path.exists(temp_path): os.remove(temp_path)

# --- IMAGE ENGINE ASYNC ---
class ImageManager:
    _cache = {}

    @classmethod
    def get_image(cls, url, callback):
        if not url or not url.startswith("http"): return
        if url in cls._cache:
            callback(cls._cache[url])
            return

        def download():
            try:
                response = requests.get(url, timeout=5)
                img_raw = Image.open(io.BytesIO(response.content))
                ctk_img = ctk.CTkImage(light_image=img_raw, dark_image=img_raw, size=(100, 140))
                cls._cache[url] = ctk_img
                callback(ctk_img)
            except Exception as e:
                logging.error(f"Erro imagem: {e}")

        threading.Thread(target=download, daemon=True).start()

# --- ANIME CARD COMPONENT ---
class AnimeCard(ctk.CTkFrame):
    def __init__(self, master, anime, delete_callback, copy_callback):
        super().__init__(master, fg_color=Env.COLOR_CARD, corner_radius=10)
        self.anime = anime
        self.grid_columnconfigure(1, weight=1)
        
        # Capa
        self.img_label = ctk.CTkLabel(self, text="🎬", width=100, height=140, 
                                      fg_color=("#D0D0D0", "#1A1A1A"), corner_radius=6)
        self.img_label.grid(row=0, column=0, rowspan=4, padx=10, pady=10)
        
        if anime.get('cover'):
            ImageManager.get_image(anime['cover'], self.update_image)

        # Título
        ctk.CTkLabel(self, text=anime.get('title', 'Sem Título'), font=("Segoe UI", 13, "bold"), 
                     wraplength=160, justify="left").grid(row=0, column=1, sticky="nw", pady=(10, 0))
        
        # Progresso com destaque Accent
        curr = safe_int(anime.get('eps_current'), 0)
        total = safe_int(anime.get('eps_total'), 0)
        
        prog_frame = ctk.CTkFrame(self, fg_color="transparent")
        prog_frame.grid(row=1, column=1, sticky="nw")
        
        ctk.CTkLabel(prog_frame, text="Progresso: ", font=("Segoe UI", 11), 
                     text_color=Env.COLOR_TEXT_DIM).pack(side="left")
        ctk.CTkLabel(prog_frame, text=f"{curr} / {total}", font=("Segoe UI", 11, "bold"), 
                     text_color=Env.COLOR_ACCENT).pack(side="left")

        # Nota
        score = safe_float(anime.get('score'), 0.0)
        ctk.CTkLabel(self, text=f"Nota: {score}/10", font=("Segoe UI", 11), 
                     text_color=Env.COLOR_TEXT_DIM).grid(row=2, column=1, sticky="nw")

        # Ações
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=1, sticky="sw", pady=10)
        
        ctk.CTkButton(actions, text="Discord", width=60, height=22, font=("Segoe UI", 10),
                      fg_color="#5865F2", hover_color="#4752C4",
                      command=lambda: copy_callback(anime)).pack(side="left", padx=2)
        
        ctk.CTkButton(actions, text="Excluir", width=60, height=22, font=("Segoe UI", 10),
                      fg_color="#A12D2D", hover_color="#822424",
                      command=lambda: delete_callback(anime)).pack(side="left", padx=2)

    def update_image(self, ctk_img):
        try: self.img_label.configure(image=ctk_img, text="")
        except: pass

# --- MAIN APPLICATION ---
class AnimeManagerV25(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Anime Manager Pro V{Env.VERSION}")
        self.geometry("1240x880")
        
        self.anime_list = Database.load()
        self.current_cover_url = ""
        self.sort_mode = "Nome (A-Z)"
        
        self.setup_layout()
        self.refresh_library()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # SIDEBAR
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(self.sidebar, text="CONTROLES", font=("Segoe UI", 16, "bold")).pack(pady=(20, 10))
        
        # Busca Jikan
        self.search_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Procurar na Nuvem...")
        self.search_entry.pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(self.sidebar, text="Pesquisar Jikan", command=self.search_jikan).pack(fill="x", padx=20, pady=5)
        
        self.search_results_frame = ctk.CTkScrollableFrame(self.sidebar, height=150, label_text="Resultados")
        self.search_results_frame.pack(fill="x", padx=20, pady=10)

        # FORMULÁRIO COM LABELS (Evolução V2.5)
        self.create_label("Título do Anime")
        self.ent_title = ctk.CTkEntry(self.sidebar, placeholder_text="Ex: One Piece")
        self.ent_title.pack(fill="x", padx=20, pady=(0, 10))

        self.create_label("Progresso (Episódio Atual)")
        self.ent_current_ep = ctk.CTkEntry(self.sidebar, placeholder_text="0")
        self.ent_current_ep.pack(fill="x", padx=20, pady=(0, 10))

        self.create_label("Total de Episódios")
        self.ent_eps = ctk.CTkEntry(self.sidebar, placeholder_text="Ex: 12")
        self.ent_eps.pack(fill="x", padx=20, pady=(0, 10))

        self.create_label("Sua Nota (0.0 - 10.0)")
        self.ent_score = ctk.CTkEntry(self.sidebar, placeholder_text="8.5")
        self.ent_score.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkButton(self.sidebar, text="SALVAR NA BIBLIOTECA", fg_color="#28a745", 
                      font=("Segoe UI", 12, "bold"), height=40,
                      command=self.add_anime).pack(fill="x", padx=20, pady=10)
        
        ctk.CTkButton(self.sidebar, text="🔮 O Oráculo (Sortear)", fg_color="#6f42c1", 
                      command=self.run_oracle).pack(fill="x", padx=20, pady=5)

        # MAIN CONTENT
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_content.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(2, weight=1)

        self.stats_frame = ctk.CTkFrame(self.main_content, height=120)
        self.stats_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        header_lib = ctk.CTkFrame(self.main_content, fg_color="transparent")
        header_lib.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(header_lib, text="MINHA BIBLIOTECA", font=("Segoe UI", 20, "bold")).pack(side="left")
        
        self.sort_menu = ctk.CTkOptionMenu(header_lib, values=["Nome (A-Z)", "Nota (Maior-Menor)"],
                                          command=self.change_sort)
        self.sort_menu.pack(side="right")

        self.library_scroll = ctk.CTkScrollableFrame(self.main_content)
        self.library_scroll.grid(row=2, column=0, sticky="nsew")
        self.library_scroll.grid_columnconfigure((0, 1, 2), weight=1)

    def create_label(self, text):
        lbl = ctk.CTkLabel(self.sidebar, text=text, font=("Segoe UI", 11, "bold"), 
                           text_color=Env.COLOR_TEXT_DIM)
        lbl.pack(anchor="w", padx=22)

    def update_dashboard(self):
        for w in self.stats_frame.winfo_children(): w.destroy()
        
        total_animes = len(self.anime_list)
        total_watched = sum(safe_int(a.get('eps_current')) for a in self.anime_list)
        valid_scores = [safe_float(a.get('score')) for a in self.anime_list if a.get('score')]
        avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
        
        metrics = [
            ("Animes", total_animes),
            ("Eps. Assistidos", total_watched),
            ("Média Global", f"{avg_score:.1f}")
        ]
        
        for label, value in metrics:
            f = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
            f.pack(side="left", expand=True)
            ctk.CTkLabel(f, text=str(value), font=("Segoe UI", 28, "bold"), text_color=Env.COLOR_ACCENT).pack()
            ctk.CTkLabel(f, text=label, font=("Segoe UI", 12)).pack()

    def add_anime(self):
        title = self.ent_title.get().strip()
        if not title:
            messagebox.showwarning("Aviso", "Título é obrigatório!")
            return
        
        self.anime_list.append({
            "id": int(datetime.now().timestamp() * 1000),
            "title": title,
            "eps_current": self.ent_current_ep.get() or "0",
            "eps_total": self.ent_eps.get() or "0",
            "score": self.ent_score.get() or "0",
            "cover": self.current_cover_url
        })
        Database.save(self.anime_list)
        self.refresh_library()
        self.clear_form()

    def run_oracle(self):
        if not self.anime_list: return
        a = random.choice(self.anime_list)
        messagebox.showinfo("🔮 O Oráculo", f"Sugestão de hoje:\n\n{a['title']}")

    def copy_status(self, anime):
        txt = f"📺 Assistindo: {anime['title']} | Progresso: {anime.get('eps_current')}/{anime.get('eps_total')} | Nota: {anime.get('score')}/10"
        self.clipboard_clear()
        self.clipboard_append(txt)
        messagebox.showinfo("Clipboard", "Status copiado para o Discord!")

    def change_sort(self, choice):
        self.sort_mode = choice
        self.refresh_library()

    def refresh_library(self):
        for w in self.library_scroll.winfo_children(): w.destroy()
        
        data = list(self.anime_list)
        if self.sort_mode == "Nome (A-Z)":
            data.sort(key=lambda x: str(x.get('title')).lower())
        else:
            data.sort(key=lambda x: safe_float(x.get('score')), reverse=True)

        for i, anime in enumerate(data):
            row, col = divmod(i, 3)
            card = AnimeCard(self.library_scroll, anime, self.remove_anime, self.copy_status)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        self.update_dashboard()

    def remove_anime(self, anime):
        if messagebox.askyesno("Excluir", f"Remover {anime['title']}?"):
            self.anime_list = [a for a in self.anime_list if a['id'] != anime['id']]
            Database.save(self.anime_list)
            self.refresh_library()

    def clear_form(self):
        for ent in [self.ent_title, self.ent_current_ep, self.ent_eps, self.ent_score]:
            ent.delete(0, 'end')
        self.current_cover_url = ""

    def search_jikan(self):
        q = self.search_entry.get().strip()
        if len(q) < 3: return
        def run():
            try:
                r = requests.get(f"https://api.jikan.moe/v4/anime?q={q}&limit=5", timeout=10)
                self.after(0, lambda: self.render_search_results(r.json().get('data', [])))
            except: pass
        threading.Thread(target=run, daemon=True).start()

    def render_search_results(self, results):
        for w in self.search_results_frame.winfo_children(): w.destroy()
        for item in results:
            btn = ctk.CTkButton(self.search_results_frame, text=item['title'], height=30,
                                fg_color="transparent", anchor="w",
                                command=lambda i=item: self.select_jikan(i))
            btn.pack(fill="x", pady=2)

    def select_jikan(self, data):
        self.ent_title.delete(0, 'end'); self.ent_title.insert(0, data['title'])
        self.ent_eps.delete(0, 'end'); self.ent_eps.insert(0, str(data.get('episodes') or "0"))
        self.current_cover_url = data.get('images', {}).get('jpg', {}).get('image_url', '')

    def on_closing(self):
        Database.save(self.anime_list)
        self.destroy()

if __name__ == "__main__":
    app = AnimeManagerV25()
    app.mainloop()