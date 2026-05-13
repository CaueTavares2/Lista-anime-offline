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

# --- CONFIGURAÇÕES DE AMBIENTE E CAMINHOS ABSOLUTOS ---
class Env:
    APP_NAME = "AnimeTrackerPro_V24"
    if getattr(sys, 'frozen', False):
        BASE_DIR = Path(sys.executable).parent
    else:
        BASE_DIR = Path(__file__).parent.absolute()

    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(exist_ok=True)
    
    DB_PATH = DATA_DIR / "animes.json"
    LOG_PATH = DATA_DIR / "debug_log.txt"
    
    # Cores de UI
    COLOR_ACCENT = ("#3B8ED0", "#1F6AA5")
    COLOR_CARD = ("#EBEBEB", "#2B2B2B")
    COLOR_TEXT_DIM = ("#606060", "#A0A0A0")

# --- SISTEMA DE LOGGING ---
logging.basicConfig(
    filename=Env.LOG_PATH, level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(message)s', encoding='utf-8'
)

# --- GESTÃO DE PERSISTÊNCIA (ATOMIC DATABASE) ---
class Database:
    @staticmethod
    def load():
        if not Env.DB_PATH.exists(): return []
        try:
            with open(Env.DB_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
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
            logging.error(f"Erro atômico: {e}")
            if os.path.exists(temp_path): os.remove(temp_path)

# --- GERENCIADOR DE IMAGENS ASYNC ---
class ImageManager:
    _cache = {}

    @classmethod
    def get_image(cls, url, callback):
        if not url: return
        if url in cls._cache:
            callback(cls._cache[url])
            return

        def download():
            try:
                response = requests.get(url, timeout=5)
                img_data = Image.open(io.BytesIO(response.content))
                ctk_img = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(100, 140))
                cls._cache[url] = ctk_img
                callback(ctk_img)
            except Exception as e:
                logging.error(f"Erro ao baixar capa: {e}")

        threading.Thread(target=download, daemon=True).start()

# --- COMPONENTES DE UI ---
class AnimeCard(ctk.CTkFrame):
    def __init__(self, master, anime, delete_callback, copy_callback):
        super().__init__(master, fg_color=Env.COLOR_CARD, corner_radius=10)
        self.anime = anime
        
        # Layout do Card
        self.grid_columnconfigure(1, weight=1)
        
        # Placeholder da Capa
        self.img_label = ctk.CTkLabel(self, text="⌛", width=100, height=140, 
                                      fg_color=("#D0D0D0", "#1A1A1A"), corner_radius=6)
        self.img_label.grid(row=0, column=0, rowspan=3, padx=10, pady=10)
        
        if anime.get('cover'):
            ImageManager.get_image(anime['cover'], self.update_image)

        # Infos
        ctk.CTkLabel(self, text=anime['title'], font=("Segoe UI", 13, "bold"), 
                     wraplength=160, justify="left").grid(row=0, column=1, sticky="nw", pady=(10, 0))
        
        info_text = f"Eps: {anime.get('eps_total', '?')} | Nota: {anime.get('score', '0')}/10"
        ctk.CTkLabel(self, text=info_text, font=("Segoe UI", 11), 
                     text_color=Env.COLOR_TEXT_DIM).grid(row=1, column=1, sticky="nw")

        # Botões de Ação
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=1, sticky="sw", pady=10)
        
        ctk.CTkButton(actions, text="Discord", width=60, height=22, font=("Segoe UI", 10),
                      fg_color="#5865F2", hover_color="#4752C4",
                      command=lambda: copy_callback(anime)).pack(side="left", padx=2)
        
        ctk.CTkButton(actions, text="Excluir", width=60, height=22, font=("Segoe UI", 10),
                      fg_color="#A12D2D", hover_color="#822424",
                      command=lambda: delete_callback(anime)).pack(side="left", padx=2)

    def update_image(self, ctk_img):
        self.img_label.configure(image=ctk_img, text="")

# --- APLICAÇÃO PRINCIPAL ---
class AnimeManagerV24(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Anime Manager Pro V2.4")
        self.geometry("1200x850")
        ctk.set_appearance_mode("system")
        
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
        self.sidebar = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(self.sidebar, text="CONTROLES", font=("Segoe UI", 16, "bold")).pack(pady=20)
        
        # Busca Jikan
        self.search_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Buscar na Jikan API...")
        self.search_entry.pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(self.sidebar, text="Pesquisar Anime", command=self.search_jikan).pack(fill="x", padx=20, pady=5)
        
        self.search_results_frame = ctk.CTkScrollableFrame(self.sidebar, height=180, label_text="Resultados")
        self.search_results_frame.pack(fill="x", padx=20, pady=10)

        # Campos de entrada
        self.ent_title = ctk.CTkEntry(self.sidebar, placeholder_text="Título do Anime")
        self.ent_title.pack(fill="x", padx=20, pady=5)
        self.ent_eps = ctk.CTkEntry(self.sidebar, placeholder_text="Total de Episódios")
        self.ent_eps.pack(fill="x", padx=20, pady=5)
        self.ent_score = ctk.CTkEntry(self.sidebar, placeholder_text="Nota (0-10)")
        self.ent_score.pack(fill="x", padx=20, pady=5)

        ctk.CTkButton(self.sidebar, text="SALVAR NA LISTA", fg_color="#28a745", 
                      command=self.add_anime).pack(fill="x", padx=20, pady=15)
        
        # O ORÁCULO
        ctk.CTkLabel(self.sidebar, text="DIVERSÃO", font=("Segoe UI", 12, "bold")).pack(pady=(20, 0))
        ctk.CTkButton(self.sidebar, text="🔮 O Oráculo (Sorteio)", fg_color="#6f42c1", 
                      command=self.run_oracle).pack(fill="x", padx=20, pady=10)

        # MAIN CONTENT
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_content.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(1, weight=1)

        # DASHBOARD FRAME
        self.stats_frame = ctk.CTkFrame(self.main_content, height=100)
        self.stats_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        # BIBLIOTECA HEADER
        header_lib = ctk.CTkFrame(self.main_content, fg_color="transparent")
        header_lib.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(header_lib, text="MINHA BIBLIOTECA", font=("Segoe UI", 18, "bold")).pack(side="left")
        
        self.sort_menu = ctk.CTkOptionMenu(header_lib, values=["Nome (A-Z)", "Nota (Maior-Menor)"],
                                          command=self.change_sort)
        self.sort_menu.pack(side="right")

        self.library_scroll = ctk.CTkScrollableFrame(self.main_content)
        self.library_scroll.grid(row=2, column=0, sticky="nsew")
        self.library_scroll.grid_columnconfigure((0, 1, 2), weight=1)

    # --- LOGICA DASHBOARD ---
    def update_dashboard(self):
        for w in self.stats_frame.winfo_children(): w.destroy()
        
        total_animes = len(self.anime_list)
        total_eps = sum(int(a.get('eps_total', 0) or 0) for a in self.anime_list)
        scores = [float(a.get('score', 0) or 0) for a in self.anime_list if a.get('score')]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        metrics = [
            ("Animes", total_animes),
            ("Total Episódios", total_eps),
            ("Média Notas", f"{avg_score:.2f}")
        ]
        
        for label, value in metrics:
            f = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
            f.pack(side="left", expand=True)
            ctk.CTkLabel(f, text=str(value), font=("Segoe UI", 24, "bold")).pack()
            ctk.CTkLabel(f, text=label, font=("Segoe UI", 12), text_color=Env.COLOR_TEXT_DIM).pack()

    # --- O ORÁCULO ---
    def run_oracle(self):
        if not self.anime_list:
            messagebox.showwarning("Oráculo", "Sua lista está vazia! Adicione animes primeiro.")
            return
        escolhido = random.choice(self.anime_list)
        messagebox.showinfo("🔮 O Oráculo diz:", f"Sua próxima maratona será:\n\n⭐ {escolhido['title']} ⭐")

    # --- CLIPBOARD EXPORT ---
    def copy_status(self, anime):
        status = f"📺 Assistindo: {anime['title']} | Nota: {anime.get('score', '0')}/10"
        self.clipboard_clear()
        self.clipboard_append(status)
        logging.info(f"Status copiado: {anime['title']}")
        # Feedback visual simples
        messagebox.showinfo("Copiado!", "Status pronto para colar no Discord!")

    # --- ORDENAÇÃO ---
    def change_sort(self, choice):
        self.sort_mode = choice
        self.refresh_library()

    def refresh_library(self):
        for w in self.library_scroll.winfo_children(): w.destroy()
        
        # Aplicar Ordenação
        data = list(self.anime_list)
        if self.sort_mode == "Nome (A-Z)":
            data.sort(key=lambda x: x['title'].lower())
        else:
            data.sort(key=lambda x: float(x.get('score', 0) or 0), reverse=True)

        for i, anime in enumerate(data):
            row, col = divmod(i, 3)
            card = AnimeCard(self.library_scroll, anime, self.remove_anime, self.copy_status)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        self.update_dashboard()

    # --- OPERAÇÕES DE DADOS ---
    def add_anime(self):
        title = self.ent_title.get()
        if not title: return
        
        new_anime = {
            "id": random.randint(1000, 99999),
            "title": title,
            "eps_total": self.ent_eps.get(),
            "score": self.ent_score.get(),
            "cover": self.current_cover_url
        }
        self.anime_list.append(new_anime)
        Database.save(self.anime_list)
        self.refresh_library()
        self.clear_form()

    def remove_anime(self, anime):
        if messagebox.askyesno("Confirmar", f"Excluir {anime['title']}?"):
            self.anime_list = [a for a in self.anime_list if a['id'] != anime['id']]
            Database.save(self.anime_list)
            self.refresh_library()

    def clear_form(self):
        self.ent_title.delete(0, 'end'); self.ent_eps.delete(0, 'end'); self.ent_score.delete(0, 'end')
        self.current_cover_url = ""

    # --- API JIKAN ---
    def search_jikan(self):
        query = self.search_entry.get()
        if len(query) < 3: return
        
        def run():
            try:
                res = requests.get(f"https://api.jikan.moe/v4/anime?q={query}&limit=5").json()
                self.after(0, lambda: self.render_search_results(res.get('data', [])))
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
        self.ent_eps.delete(0, 'end'); self.ent_eps.insert(0, str(data.get('episodes') or ""))
        self.current_cover_url = data['images']['jpg']['image_url']

    def on_closing(self):
        Database.save(self.anime_list)
        self.destroy()

if __name__ == "__main__":
    app = AnimeManagerV24()
    app.mainloop()