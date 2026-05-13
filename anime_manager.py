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
    VERSION = "2.6-Ultra"
    APP_NAME = "AnimeTrackerPro_Ultra"
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
    STATUS_OPTIONS = ["Assistindo", "Concluído", "Planejo Assistir"]

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
            logging.error(f"Erro de Salvamento: {e}")

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

# --- COMPONENTE ANIME CARD ---
class AnimeCard(ctk.CTkFrame):
    def __init__(self, master, anime, app):
        super().__init__(master, fg_color=Env.COLOR_CARD, corner_radius=12)
        self.anime = anime
        self.app = app
        self.grid_columnconfigure(1, weight=1)
        
        # Capa
        self.img_label = ctk.CTkLabel(self, text="🎬", width=100, height=145, fg_color=("#CCCCCC", "#1A1A1A"), corner_radius=8)
        self.img_label.grid(row=0, column=0, rowspan=4, padx=12, pady=12)
        self.img_label.bind("<Button-1>", lambda e: self.app.load_edit(self.anime))

        # Infos
        lbl_title = ctk.CTkLabel(self, text=anime['title'], font=("Segoe UI", 14, "bold"), wraplength=180, justify="left", cursor="hand2")
        lbl_title.grid(row=0, column=1, sticky="nw", pady=(15, 0))
        lbl_title.bind("<Button-1>", lambda e: self.app.load_edit(self.anime))

        curr, total = int(anime.get('eps_current', 0)), int(anime.get('eps_total', 0))
        prog_text = f"Progresso: {curr}/{total}"
        ctk.CTkLabel(self, text=prog_text, font=("Segoe UI", 11)).grid(row=1, column=1, sticky="nw")

        # Barra de Progresso
        bar = ctk.CTkProgressBar(self, height=8, progress_color=Env.COLOR_ACCENT)
        bar.set((curr/total) if total > 0 else 0)
        bar.grid(row=2, column=1, sticky="ew", padx=(0, 20))

        # Botão Discord
        ctk.CTkButton(self, text="Copiado p/ Discord", height=24, font=("Segoe UI", 10), command=lambda: self.app.copy_status(anime)).grid(row=3, column=1, sticky="sw", pady=15)

        # Quick Control
        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.grid(row=0, column=2, rowspan=4, padx=10)
        ctk.CTkButton(btn_f, text="+", width=30, command=lambda: self.app.quick_update(anime, 1)).pack(pady=5)
        ctk.CTkButton(btn_f, text="-", width=30, fg_color="#555555", command=lambda: self.app.quick_update(anime, -1)).pack(pady=5)

        if anime.get('cover'): ImageManager.get_image(anime['cover'], self.set_img)

    def set_img(self, img):
        try: self.img_label.configure(image=img, text="")
        except: pass

# --- APP PRINCIPAL ---
class AnimeManagerUltra(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Anime Tracker Pro {Env.VERSION}")
        
        # Fullscreen Config
        self.attributes('-fullscreen', True)
        self.is_fullscreen = True
        self.bind("<Escape>", self.toggle_fullscreen)

        # State
        self.anime_list = Database.load()
        self.editing_id = None
        self.current_cover = ""
        self.search_limit = 5

        self.setup_ui()
        self.refresh_library()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes('-fullscreen', self.is_fullscreen)
        if not self.is_fullscreen: self.geometry("1280x800")

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Tabview Principal
        self.tabs = ctk.CTkTabview(self, segmented_button_selected_color=Env.COLOR_ACCENT)
        self.tabs.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.tab_lib = self.tabs.add("📚 Biblioteca")
        self.tab_cfg = self.tabs.add("⚙️ Configurações")

        self.setup_library_tab()
        self.setup_settings_tab()

    def setup_library_tab(self):
        self.tab_lib.grid_columnconfigure(1, weight=1)
        self.tab_lib.grid_rowconfigure(0, weight=1)

        # Sidebar (Col 0)
        side = ctk.CTkFrame(self.tab_lib, width=320, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        side.grid_propagate(False)

        ctk.CTkLabel(side, text="PAINEL DE CONTROLE", font=("Segoe UI", 16, "bold")).pack(pady=15)
        
        # Busca Jikan
        self.ent_search = ctk.CTkEntry(side, placeholder_text="Buscar Jikan...")
        self.ent_search.pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(side, text="Pesquisar", command=self.search_jikan).pack(fill="x", padx=20)
        
        self.search_scroll = ctk.CTkScrollableFrame(side, height=140, label_text="Resultados")
        self.search_scroll.pack(fill="x", padx=20, pady=10)

        # Form fields
        self.form = {}
        for label, key in [("Título", "title"), ("Ep. Atual", "curr"), ("Total Eps", "total")]:
            ctk.CTkLabel(side, text=label, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=25)
            self.form[key] = ctk.CTkEntry(side)
            self.form[key].pack(fill="x", padx=20, pady=(0, 5))
        
        # Locked Score Logic
        ctk.CTkLabel(side, text="Sua Nota (Somente se concluído)", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=25)
        self.form['score'] = ctk.CTkEntry(side, state="disabled")
        self.form['score'].pack(fill="x", padx=20, pady=(0, 5))
        
        self.form['curr'].bind("<KeyRelease>", self.validate_score_logic)
        self.form['total'].bind("<KeyRelease>", self.validate_score_logic)

        self.opt_status = ctk.CTkOptionMenu(side, values=Env.STATUS_OPTIONS)
        self.opt_status.pack(fill="x", padx=20, pady=10)

        self.btn_save = ctk.CTkButton(side, text="SALVAR ALTERAÇÕES", fg_color="#28a745", font=("Segoe UI", 12, "bold"), height=35, command=self.save_anime)
        self.btn_save.pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(side, text="Limpar/Cancelar", fg_color="#555555", command=self.clear_form).pack(fill="x", padx=20)

        # Main Area (Col 1)
        main = ctk.CTkFrame(self.tab_lib, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)

        # Dashboard sticky
        self.dash = ctk.CTkFrame(main, height=110)
        self.dash.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        # Filtros
        self.filters = ctk.CTkSegmentedButton(main, values=["Todos"] + Env.STATUS_OPTIONS, command=self.apply_filter)
        self.filters.set("Todos")
        self.filters.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        self.scroll = ctk.CTkScrollableFrame(main)
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        self.scroll.grid_columnconfigure((0,1,2), weight=1)
        main.grid_rowconfigure(2, weight=1)

    def setup_settings_tab(self):
        cfg = self.tab_cfg
        ctk.CTkLabel(cfg, text="CONFIGURAÇÕES DO SISTEMA", font=("Segoe UI", 20, "bold")).pack(pady=30)

        # Tema
        ctk.CTkLabel(cfg, text="Tema da Interface").pack()
        self.opt_theme = ctk.CTkOptionMenu(cfg, values=["Dark", "Light"], command=lambda v: ctk.set_appearance_mode(v))
        self.opt_theme.pack(pady=10)

        # Ações
        ctk.CTkButton(cfg, text="📂 Abrir Pasta de Dados", command=lambda: os.startfile(Env.DATA_DIR)).pack(pady=10)
        ctk.CTkButton(cfg, text="⚠️ RESETAR BANCO DE DADOS", fg_color="#A12D2D", command=self.reset_db).pack(pady=30)
        
        ctk.CTkLabel(cfg, text=f"Anime Tracker Pro Version {Env.VERSION}\nDeveloper Context: Arquiteto Sênior", text_color="gray").pack(side="bottom", pady=20)

    # --- LOGIC ---
    def validate_score_logic(self, event=None):
        try:
            curr = int(self.form['curr'].get())
            total = int(self.form['total'].get())
            if curr >= total and total > 0:
                self.form['score'].configure(state="normal")
            else:
                self.form['score'].delete(0, 'end')
                self.form['score'].configure(state="disabled")
        except:
            self.form['score'].configure(state="disabled")

    def search_jikan(self):
        q = self.ent_search.get()
        def run():
            try:
                r = requests.get(f"https://api.jikan.moe/v4/anime?q={q}&limit={self.search_limit}").json()
                self.after(0, lambda: self.render_search(r.get('data', [])))
            except: pass
        threading.Thread(target=run, daemon=True).start()

    def render_search(self, results):
        for w in self.search_scroll.winfo_children(): w.destroy()
        for item in results:
            btn = ctk.CTkButton(self.search_scroll, text=item['title'], fg_color="transparent", anchor="w", command=lambda i=item: self.pick_jikan(i))
            btn.pack(fill="x")
        
        if self.search_limit == 5:
            ctk.CTkButton(self.search_scroll, text="Exibir Mais...", fg_color=Env.COLOR_ACCENT, command=self.show_more_search).pack(pady=5)

    def show_more_search(self):
        self.search_limit = 10
        self.search_jikan()

    def pick_jikan(self, item):
        self.form['title'].delete(0, 'end'); self.form['title'].insert(0, item['title'])
        self.form['total'].delete(0, 'end'); self.form['total'].insert(0, str(item.get('episodes') or 0))
        self.current_cover = item['images']['jpg']['image_url']
        self.validate_score_logic()

    def save_anime(self):
        title = self.form['title'].get()
        if not title: return
        
        data = {
            "id": self.editing_id or int(datetime.now().timestamp() * 1000),
            "title": title,
            "eps_current": self.form['curr'].get() or "0",
            "eps_total": self.form['total'].get() or "0",
            "score": self.form['score'].get() if self.form['score'].cget("state") == "normal" else "0",
            "status": self.opt_status.get(),
            "cover": self.current_cover
        }

        if self.editing_id:
            for i, a in enumerate(self.anime_list):
                if a['id'] == self.editing_id: self.anime_list[i] = data
        else:
            self.anime_list.append(data)

        Database.save(self.anime_list)
        self.clear_form()
        self.refresh_library()

    def load_edit(self, anime):
        self.clear_form()
        self.editing_id = anime['id']
        self.form['title'].insert(0, anime['title'])
        self.form['curr'].insert(0, anime['eps_current'])
        self.form['total'].insert(0, anime['eps_total'])
        self.opt_status.set(anime['status'])
        self.current_cover = anime.get('cover', "")
        self.validate_score_logic()
        if self.form['score'].cget("state") == "normal":
            self.form['score'].insert(0, anime.get('score', '0'))

    def quick_update(self, anime, delta):
        c = max(0, int(anime['eps_current']) + delta)
        t = int(anime['eps_total'])
        anime['eps_current'] = str(c if t == 0 else min(c, t))
        if t > 0 and int(anime['eps_current']) == t: anime['status'] = "Concluído"
        Database.save(self.anime_list)
        self.refresh_library()

    def apply_filter(self, val):
        self.refresh_library(val)

    def refresh_library(self, filter_val="Todos"):
        for w in self.scroll.winfo_children(): w.destroy()
        data = [a for a in self.anime_list if filter_val == "Todos" or a['status'] == filter_val]
        for i, a in enumerate(data):
            AnimeCard(self.scroll, a, self).grid(row=i//3, column=i%3, padx=10, pady=10, sticky="nsew")
        self.update_dash()

    def update_dash(self):
        for w in self.dash.winfo_children(): w.destroy()
        total_eps = sum(int(a['eps_current']) for a in self.anime_list)
        stats = [("Itens", len(self.anime_list)), ("Eps Assistidos", total_eps), ("Concluídos", sum(1 for a in self.anime_list if a['status'] == 'Concluído'))]
        for label, val in stats:
            f = ctk.CTkFrame(self.dash, fg_color=Env.COLOR_DASH_ITEM)
            f.pack(side="left", expand=True, fill="both", padx=5, pady=5)
            ctk.CTkLabel(f, text=str(val), font=("Segoe UI", 24, "bold"), text_color=Env.COLOR_ACCENT).pack(pady=(10,0))
            ctk.CTkLabel(f, text=label).pack(pady=(0,10))

    def reset_db(self):
        if messagebox.askyesno("PERIGO", "Isso apagará TODOS os seus dados. Continuar?"):
            self.anime_list = []
            Database.save([])
            self.refresh_library()

    def clear_form(self):
        self.editing_id = None
        self.current_cover = ""
        for k in self.form:
            self.form[k].configure(state="normal")
            self.form[k].delete(0, 'end')
        self.form['score'].configure(state="disabled")
        self.search_limit = 5

    def copy_status(self, a):
        self.clipboard_clear()
        self.clipboard_append(f"📺 {a['title']} | Progress: {a['eps_current']}/{a['eps_total']} | Score: {a['score']}/10")

    def on_closing(self):
        Database.save(self.anime_list)
        self.destroy()

if __name__ == "__main__":
    app = AnimeManagerUltra()
    app.mainloop()