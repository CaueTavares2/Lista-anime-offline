import os
import sys
import json
import logging
import threading
import tempfile
import requests
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageOps
import customtkinter as ctk
from tkinter import messagebox

# --- CONFIGURAÇÕES DE AMBIENTE E CAMINHOS ABSOLUTOS ---
class Env:
    APP_NAME = "AnimeTrackerPro_V231"
    
    # Detecção de execução via .exe (PyInstaller) ou Script
    if getattr(sys, 'frozen', False):
        BASE_DIR = Path(sys.executable).parent
    else:
        BASE_DIR = Path(__file__).parent.absolute()

    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(exist_ok=True)
    
    DB_PATH = DATA_DIR / "animes.json"
    LOG_PATH = DATA_DIR / "debug_log.txt"
    COVERS_DIR = DATA_DIR / "covers"
    COVERS_DIR.mkdir(exist_ok=True)

# --- SISTEMA DE LOGGING ---
logging.basicConfig(
    filename=Env.LOG_PATH,
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(message)s',
    encoding='utf-8'
)

def log(msg, level="info"):
    if level == "error": logging.error(msg)
    elif level == "debug": logging.debug(msg)
    else: logging.info(msg)

# --- GESTÃO DE PERSISTÊNCIA (ATOMIC DATABASE) ---
class Database:
    @staticmethod
    def load():
        if not Env.DB_PATH.exists():
            return []
        try:
            with open(Env.DB_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Falha ao carregar DB: {e}", "error")
            return []

    @staticmethod
    def save(data):
        """Implementação de Atomic Save: Grava em TMP e substitui o original."""
        temp_fd, temp_path = tempfile.mkstemp(dir=Env.DATA_DIR, suffix=".tmp")
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            # Substituição atômica (Thread-safe no SO)
            os.replace(temp_path, Env.DB_PATH)
            log("Database salvo com sucesso (Atômico).")
        except Exception as e:
            log(f"ERRO CRÍTICO NO SALVAMENTO: {e}", "error")
            if os.path.exists(temp_path):
                os.remove(temp_path)

# --- COMPONENTES DE UI ---
class JikanResultItem(ctk.CTkFrame):
    def __init__(self, master, data, select_callback):
        # Contraste adaptativo para Light Mode
        super().__init__(master, fg_color=("#D1D1D1", "#2B2B2B"), corner_radius=6)
        self.data = data
        
        self.columnconfigure(0, weight=1)
        
        title = data.get('title', 'Unknown')
        year = data.get('year') or "N/A"
        
        lbl = ctk.CTkLabel(self, text=f"{title} ({year})", 
                           font=("Segoe UI", 12, "bold"), 
                           wraplength=200, justify="left",
                           text_color=("#000000", "#FFFFFF"))
        lbl.grid(row=0, column=0, padx=10, pady=(5, 0), sticky="w")
        
        btn = ctk.CTkButton(self, text="Selecionar", height=24, 
                            command=lambda: select_callback(data),
                            fg_color=("#3B8ED0", "#1F6AA5"))
        btn.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

# --- APLICAÇÃO PRINCIPAL ---
class AnimeManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configurações de Janela
        self.title("Anime Manager Pro V2.3.1")
        self.geometry("1200x800")
        ctk.set_appearance_mode("system")
        
        # Estado
        self.anime_list = Database.load()
        self.current_cover_url = ""
        
        self.setup_layout()
        self.refresh_library()
        
        # Protocolo de fechamento
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        log("Aplicação iniciada com sucesso.")

    def setup_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ================= COLUNA 0: SIDEBAR (CONTROLES) =================
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar.grid_propagate(False)

        # Seção de Busca Jikan
        ctk.CTkLabel(self.sidebar, text="PESQUISAR JIKAN API", font=("Segoe UI", 14, "bold")).pack(pady=(20, 10))
        
        self.search_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Digite o nome do anime...")
        self.search_entry.pack(fill="x", padx=20, pady=5)
        self.search_entry.bind("<Return>", lambda e: self.search_jikan())

        self.btn_search = ctk.CTkButton(self.sidebar, text="Buscar na Nuvem", command=self.search_jikan)
        self.btn_search.pack(fill="x", padx=20, pady=5)

        # Resultados da Busca (Onde o erro de renderização foi corrigido)
        self.search_results_frame = ctk.CTkScrollableFrame(self.sidebar, height=200, 
                                                           label_text="Resultados da Busca",
                                                           fg_color=("#E0E0E0", "#1D1E1E"))
        self.search_results_frame.pack(fill="x", padx=15, pady=10)

        # Formulário Manual/Edição
        ctk.CTkLabel(self.sidebar, text="DADOS DO ANIME", font=("Segoe UI", 13, "bold")).pack(pady=(15, 5))
        
        self.ent_title = ctk.CTkEntry(self.sidebar, placeholder_text="Título")
        self.ent_title.pack(fill="x", padx=20, pady=5)
        
        self.ent_eps = ctk.CTkEntry(self.sidebar, placeholder_text="Episódios Totais")
        self.ent_eps.pack(fill="x", padx=20, pady=5)

        self.ent_score = ctk.CTkEntry(self.sidebar, placeholder_text="Nota (0-10)")
        self.ent_score.pack(fill="x", padx=20, pady=5)

        self.btn_add = ctk.CTkButton(self.sidebar, text="ADICIONAR À LISTA", 
                                     fg_color="#28a745", hover_color="#218838",
                                     command=self.add_anime_to_list)
        self.btn_add.pack(fill="x", padx=20, pady=20)

        # ================= COLUNA 1: MAIN (LIBRARY) =================
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        # Header de Estatísticas
        self.stats_frame = ctk.CTkFrame(self.main_frame, height=80)
        self.stats_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        self.render_stats()

        # Lista de Animes
        self.library_scroll = ctk.CTkScrollableFrame(self.main_frame, label_text="MINHA BIBLIOTECA")
        self.library_scroll.grid(row=1, column=0, sticky="nsew")
        self.library_scroll.grid_columnconfigure((0, 1, 2), weight=1)

    # --- LÓGICA DE BUSCA JIKAN ---
    def search_jikan(self):
        query = self.search_entry.get().strip()
        if len(query) < 3: return

        self.btn_search.configure(state="disabled", text="Buscando...")
        
        def run():
            try:
                log(f"Requisição Jikan: {query}")
                url = f"https://api.jikan.moe/v4/anime?q={query}&limit=5"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    results = response.json().get('data', [])
                    self.after(0, lambda: self.render_search_results(results))
                else:
                    log(f"Erro API: {response.status_code}", "error")
            except Exception as e:
                log(f"Falha na conexão: {e}", "error")
            finally:
                self.after(0, lambda: self.btn_search.configure(state="normal", text="Buscar na Nuvem"))

        threading.Thread(target=run, daemon=True).start()

    def render_search_results(self, results):
        # Limpeza robusta antes de renderizar
        for widget in self.search_results_frame.winfo_children():
            widget.destroy()

        if not results:
            ctk.CTkLabel(self.search_results_frame, text="Nada encontrado.").pack()
            return

        for item in results:
            card = JikanResultItem(self.search_results_frame, item, self.select_jikan_anime)
            # Fix de Renderização: .pack(fill="x") garante visibilidade no CTkScrollableFrame
            card.pack(fill="x", pady=4, padx=5)

    def select_jikan_anime(self, data):
        self.ent_title.delete(0, 'end')
        self.ent_title.insert(0, data.get('title', ''))
        self.ent_eps.delete(0, 'end')
        self.ent_eps.insert(0, str(data.get('episodes', '0')))
        self.current_cover_url = data.get('images', {}).get('jpg', {}).get('image_url', '')
        log(f"Anime selecionado da API: {data.get('title')}")

    # --- LÓGICA DA BIBLIOTECA ---
    def add_anime_to_list(self):
        title = self.ent_title.get()
        if not title:
            messagebox.showwarning("Erro", "O título é obrigatório!")
            return

        new_anime = {
            "id": int(datetime.now().timestamp()),
            "title": title,
            "eps_total": self.ent_eps.get(),
            "score": self.ent_score.get(),
            "cover": self.current_cover_url,
            "date": datetime.now().strftime("%d/%m/%Y")
        }

        self.anime_list.append(new_anime)
        Database.save(self.anime_list) # Auto-save Atômico
        self.refresh_library()
        self.clear_form()

    def refresh_library(self):
        for widget in self.library_scroll.winfo_children():
            widget.destroy()

        for i, anime in enumerate(self.anime_list):
            row, col = divmod(i, 3)
            card = ctk.CTkFrame(self.library_scroll, fg_color=("#F0F0F0", "#333333"))
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            ctk.CTkLabel(card, text=anime['title'], font=("Segoe UI", 12, "bold"), wraplength=150).pack(pady=10)
            ctk.CTkLabel(card, text=f"Eps: {anime['eps_total']} | Nota: {anime['score']}").pack()
            
            btn_del = ctk.CTkButton(card, text="Remover", fg_color="#c82333", height=20,
                                   command=lambda a=anime: self.remove_anime(a))
            btn_del.pack(pady=10)
        
        self.render_stats()

    def remove_anime(self, anime_obj):
        self.anime_list = [a for a in self.anime_list if a['id'] != anime_obj['id']]
        Database.save(self.anime_list)
        self.refresh_library()

    def render_stats(self):
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
        
        total = len(self.anime_list)
        ctk.CTkLabel(self.stats_frame, text=f"Total na Lista: {total}", font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)

    def clear_form(self):
        self.ent_title.delete(0, 'end')
        self.ent_eps.delete(0, 'end')
        self.ent_score.delete(0, 'end')
        self.current_cover_url = ""

    def on_closing(self):
        try:
            Database.save(self.anime_list)
            log("Aplicação encerrada com salvamento final.")
        finally:
            self.destroy()

if __name__ == "__main__":
    app = AnimeManagerApp()
    app.mainloop()
