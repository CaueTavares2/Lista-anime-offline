# ═══════════════════════════════════════════════════════════════════════════════
#  ✦  Anime Manager  v2.0
#  Dependências: pip install customtkinter pillow requests
#  Dados: Jikan API (MyAnimeList) — https://jikan.moe
# ═══════════════════════════════════════════════════════════════════════════════
import customtkinter as ctk
import json, os, sys, shutil, threading, io, random, time, re
from datetime import datetime
from tkinter import messagebox, filedialog

try:
    import requests
    from PIL import Image
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# ── Portabilidade ──────────────────────────────────────────────────────────────
def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR    = _base_dir()
DATA_FILE   = os.path.join(BASE_DIR, "animes.json")
BACKUP_FILE = os.path.join(BASE_DIR, "animes_backup.json")
COVERS_DIR  = os.path.join(BASE_DIR, "assets", "covers")
os.makedirs(COVERS_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
#  SISTEMA DE TEMAS DINÂMICO
# ══════════════════════════════════════════════════════════════════════════════
THEMES = {
    "Azul":     {"accent": "#3b8ed0", "accent_hover": "#2a7abf", "accent_dark": "#1a4a7a"},
    "Laranja":  {"accent": "#ff9500", "accent_hover": "#e08400", "accent_dark": "#7a4200"},
    "Vermelho": {"accent": "#ff3b30", "accent_hover": "#e02a20", "accent_dark": "#7a1510"},
}

class ThemeManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._mode    = "dark"
            cls._instance._theme   = "Azul"
            cls._instance._listeners = []
        return cls._instance

    @property
    def mode(self):  return self._mode
    @property
    def theme(self): return self._theme

    def set_mode(self, mode):
        self._mode = mode
        ctk.set_appearance_mode(mode)
        self._notify()

    def set_theme(self, name):
        if name in THEMES:
            self._theme = name
            self._notify()

    def accent(self):       return THEMES[self._theme]["accent"]
    def accent_hover(self): return THEMES[self._theme]["accent_hover"]
    def accent_dark(self):  return THEMES[self._theme]["accent_dark"]

    def C(self, key):
        """Retorna cor de acordo com modo e tema."""
        dark = {
            "bg0": "#07070e", "bg1": "#0f0f1a", "bg2": "#141428",
            "bg3": "#1c1c38", "bg4": "#12122a",
            "bg_fav": "#1a1230",
            "border": "#202038", "border_fav": "#8855cc",
            "green": "#2ea043", "yellow": "#f0b429", "purple": "#9966ff",
            "muted": "#555577", "dim": "#888899", "text": "#e0e8ff",
        }
        light = {
            "bg0": "#d0d8f0", "bg1": "#e8ecfa", "bg2": "#f0f2fc",
            "bg3": "#dde2f5", "bg4": "#eaeef8",
            "bg_fav": "#f0e8fc",
            "border": "#c0c8e8", "border_fav": "#8855cc",
            "green": "#1a7a30", "yellow": "#c07000", "purple": "#7744cc",
            "muted": "#8890b0", "dim": "#606888", "text": "#1a1a2e",
        }
        palette = dark if self._mode == "dark" else light
        return palette.get(key, "#ff00ff")

TM = ThemeManager()

# ── Paleta fixa de suporte ────────────────────────────────────────────────────
MOTIVATIONAL = [
    "O que vamos assistir hoje? 🍿",
    "Sua próxima aventura te espera ✨",
    "Qual história vai te conquistar? 🌸",
    "O próximo clássico está logo ali 🏆",
    "Anime bom nunca é demais 🎌",
]

JIKAN_SEARCH = "https://api.jikan.moe/v4/anime?q={q}&limit=5&sfw=true"
JIKAN_RECS   = "https://api.jikan.moe/v4/anime?genres={g}&order_by=score&sort=desc&limit=5&sfw=true"

# ══════════════════════════════════════════════════════════════════════════════
#  PERSISTÊNCIA
# ══════════════════════════════════════════════════════════════════════════════
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:    return json.load(f)
        except: return []

def save_data(animes):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(animes, f, ensure_ascii=False, indent=2)

def backup_on_startup():
    if os.path.exists(DATA_FILE):
        shutil.copy2(DATA_FILE, BACKUP_FILE)

def export_backup():
    today = datetime.now().strftime("%Y-%m-%d")
    dest  = filedialog.asksaveasfilename(
        title="Exportar Backup", initialfile=f"animes_backup_{today}.json",
        defaultextension=".json", filetypes=[("JSON", "*.json")]
    )
    if dest and os.path.exists(DATA_FILE):
        shutil.copy2(DATA_FILE, dest)
        messagebox.showinfo("Backup exportado", f"Salvo em:\n{dest}")

def today_str():
    return datetime.now().strftime("%d/%m/%Y")

# ══════════════════════════════════════════════════════════════════════════════
#  JIKAN API
# ══════════════════════════════════════════════════════════════════════════════
_last_req = 0.0

def _jikan_get(url):
    global _last_req
    gap = time.monotonic() - _last_req
    if gap < 0.6:
        time.sleep(0.6 - gap)
    try:
        r = requests.get(url, timeout=9)
        _last_req = time.monotonic()
        return r.json()
    except Exception:
        return {}

def search_jikan(query):
    if not REQUESTS_OK or not query.strip():
        return []
    data = _jikan_get(JIKAN_SEARCH.format(q=requests.utils.quote(query.strip()))).get("data", [])
    out  = []
    for item in data[:5]:
        genres_raw = item.get("genres", [])
        genres_str = ", ".join(g["name"] for g in genres_raw) if genres_raw else "Não definido"
        out.append({
            "mal_id":    item.get("mal_id"),
            "title":     item.get("title_english") or item.get("title", ""),
            "title_jp":  item.get("title", ""),
            "genres":    genres_str,
            "episodes":  item.get("episodes") or 0,
            "cover_url": item.get("images", {}).get("jpg", {}).get("image_url", ""),
            "year":      item.get("year") or "",
            "score":     item.get("score") or 0.0,
            "synopsis":  (item.get("synopsis") or "")[:200],
        })
    return out

def get_recommendations(genre_ids_str):
    """Busca animes recomendados pelos IDs de gênero (ex: '1,2')."""
    if not REQUESTS_OK:
        return []
    data = _jikan_get(JIKAN_RECS.format(g=genre_ids_str)).get("data", [])
    out  = []
    for item in data[:5]:
        genres_raw = item.get("genres", [])
        out.append({
            "title":     item.get("title_english") or item.get("title", ""),
            "genres":    ", ".join(g["name"] for g in genres_raw),
            "score":     item.get("score") or 0.0,
            "episodes":  item.get("episodes") or 0,
            "cover_url": item.get("images", {}).get("jpg", {}).get("image_url", ""),
            "year":      item.get("year") or "",
        })
    return out

def load_ctk_image(url, size=(80, 112)):
    if not REQUESTS_OK or not url:
        return None
    try:
        raw = requests.get(url, timeout=8).content
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception:
        return None

def make_placeholder(size=(80, 112)):
    if not REQUESTS_OK:
        return None
    color = (26, 26, 56, 255) if TM.mode == "dark" else (200, 210, 240, 255)
    img   = Image.new("RGBA", size, color=color)
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)

# ══════════════════════════════════════════════════════════════════════════════
#  MODAL DE ADIÇÃO / EDIÇÃO
# ══════════════════════════════════════════════════════════════════════════════
class AnimeFormModal(ctk.CTkToplevel):
    def __init__(self, parent, on_save, anime=None):
        super().__init__(parent)
        self.on_save    = on_save
        self.anime      = anime
        self._is_edit   = anime is not None
        self._api_data  = {}
        self.cover_var  = ctk.StringVar(value=(anime or {}).get("cover_url", ""))

        self.title("✦ Editar Anime" if self._is_edit else "✦ Adicionar Anime")
        self.geometry("520x680")
        self.resizable(False, False)
        self.grab_set()
        self.focus()
        self._build()
        if self._is_edit:
            self._populate(anime)

    def _build(self):
        # ── Header ──────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=TM.C("bg0"), corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr,
                     text="Editar Anime" if self._is_edit else "Adicionar Anime",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20, 4))
        sub = "Altere os dados abaixo" if self._is_edit else "Busque pelo nome e selecione o resultado"
        ctk.CTkLabel(hdr, text=sub,
                     font=ctk.CTkFont(size=11), text_color=TM.C("dim")).pack(pady=(0, 14))

        # ── Busca (somente modo Adicionar) ───────────────────────────────────
        if not self._is_edit:
            sr = ctk.CTkFrame(self, fg_color="transparent")
            sr.pack(fill="x", padx=26, pady=(10, 0))

            self.search_ent = ctk.CTkEntry(sr,
                                           placeholder_text="🔍  Nome do anime...",
                                           height=40, corner_radius=10,
                                           border_color=TM.accent())
            self.search_ent.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self.search_ent.bind("<Return>", lambda _: self._do_search())

            self.search_btn = ctk.CTkButton(sr, text="Buscar", width=80, height=40,
                                            fg_color=TM.accent(), hover_color=TM.accent_hover(),
                                            font=ctk.CTkFont(size=13, weight="bold"),
                                            command=self._do_search)
            self.search_btn.pack(side="left")

            self.status_lbl = ctk.CTkLabel(self, text="",
                                           font=ctk.CTkFont(size=11),
                                           text_color=TM.accent())
            self.status_lbl.pack(anchor="w", padx=26, pady=(4, 0))

            self.res_frame = ctk.CTkFrame(self, fg_color=TM.C("bg0"),
                                          border_width=1, border_color=TM.C("border"),
                                          corner_radius=10)
            self.res_frame.pack(fill="x", padx=26)
            self.res_frame.pack_forget()

            ctk.CTkFrame(self, height=1, fg_color=TM.C("border")).pack(fill="x", padx=26, pady=(10, 0))
            ctk.CTkLabel(self, text="DETALHES",
                         font=ctk.CTkFont(size=10), text_color=TM.C("muted")
                         ).pack(anchor="w", padx=26, pady=(6, 0))

        p = {"padx": 26, "pady": (6, 0)}

        ctk.CTkLabel(self, text="Título *", anchor="w").pack(fill="x", **p)
        self.title_ent = ctk.CTkEntry(self, placeholder_text="Ex.: Attack on Titan", height=36)
        self.title_ent.pack(fill="x", **p)

        ctk.CTkLabel(self, text="Gênero", anchor="w").pack(fill="x", **p)
        self.genre_ent = ctk.CTkEntry(self, placeholder_text="Ação, Aventura...", height=36)
        self.genre_ent.pack(fill="x", **p)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", **p)
        for attr, label, ph in [
            ("eps_watched_ent", "Vistos", "0"),
            ("eps_total_ent",   "Total",  "12"),
            ("score_ent",       "Nota (0-10)", "8.5"),
        ]:
            f = ctk.CTkFrame(row, fg_color="transparent")
            f.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ctk.CTkLabel(f, text=label, anchor="w").pack(fill="x")
            vcmd = (self.register(lambda s: re.match(r"^\d*\.?\d*$", s) is not None), "%P")
            ent = ctk.CTkEntry(f, placeholder_text=ph, height=36,
                               validate="key", validatecommand=vcmd)
            ent.pack(fill="x")
            setattr(self, attr, ent)

        ctk.CTkLabel(self, text="Status", anchor="w").pack(fill="x", **p)
        self.status_var = ctk.StringVar(value="Planejo Assistir")
        ctk.CTkOptionMenu(self, values=["Assistindo", "Planejo Assistir", "Concluído"],
                          variable=self.status_var, height=36,
                          fg_color=TM.C("bg2"), button_color=TM.accent(),
                          button_hover_color=TM.accent_hover()).pack(fill="x", **p)

        ctk.CTkLabel(self, text="Nota Pessoal", anchor="w").pack(fill="x", **p)
        self.note_ent = ctk.CTkEntry(self,
                                     placeholder_text="Comentário rápido sobre o anime...",
                                     height=36)
        self.note_ent.pack(fill="x", **p)

        ctk.CTkLabel(self, text="URL da Capa", anchor="w").pack(fill="x", **p)
        self.cover_ent = ctk.CTkEntry(self, textvariable=self.cover_var,
                                      placeholder_text="Preenchido automaticamente pela busca",
                                      height=36, text_color=TM.C("dim"))
        self.cover_ent.pack(fill="x", **p)

        ctk.CTkButton(self, text="💾  Salvar Anime", height=42,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      fg_color=TM.accent(), hover_color=TM.accent_hover(),
                      command=self._save).pack(fill="x", padx=26, pady=(16, 10))

        if not REQUESTS_OK:
            ctk.CTkLabel(self, text="⚠ pip install requests pillow  para busca automática",
                         font=ctk.CTkFont(size=10), text_color="#ff8844").pack(pady=(0, 4))

    def _populate(self, a):
        self.title_ent.insert(0, a.get("title", ""))
        self.genre_ent.insert(0, a.get("genre", ""))
        self.score_ent.insert(0, str(a.get("score", "")))
        self.eps_watched_ent.insert(0, str(a.get("eps_watched", 0)))
        self.eps_total_ent.insert(0,   str(a.get("eps_total", 0)))
        self.status_var.set(a.get("status", "Planejo Assistir"))
        self.note_ent.insert(0, a.get("note", ""))

    # ── Busca ────────────────────────────────────────────────────────────────
    def _do_search(self):
        if not REQUESTS_OK:
            messagebox.showwarning("Dependência", "pip install requests pillow", parent=self)
            return
        q = self.search_ent.get().strip()
        if not q:
            return
        self.search_btn.configure(state="disabled", text="⏳")
        self.status_lbl.configure(text="Buscando na Jikan / MyAnimeList...")
        self.res_frame.pack_forget()
        threading.Thread(target=lambda: self.after(0, self._show_results(search_jikan(q))),
                         daemon=True).start()

    def _show_results(self, results):
        self.search_btn.configure(state="normal", text="Buscar")
        for w in self.res_frame.winfo_children():
            w.destroy()

        if not results:
            self.status_lbl.configure(text="❌  Sem resultados. Tente outro nome.",
                                      text_color="#ff6644")
            return

        self.status_lbl.configure(
            text=f"✅  {len(results)} resultado(s) — clique para selecionar",
            text_color=TM.C("green"))

        for i, r in enumerate(results):
            y = f" ({r['year']})" if r.get("year") else ""
            e = f" · {r['episodes']} eps" if r.get("episodes") else ""
            s = f" · ★{r['score']:.1f}" if r.get("score") else ""

            row = ctk.CTkFrame(self.res_frame, fg_color="transparent", cursor="hand2")
            row.pack(fill="x", padx=4, pady=2)

            ctk.CTkButton(row, text=f"{r['title']}{y}{e}{s}",
                          anchor="w", height=32,
                          fg_color=TM.C("bg2"), hover_color=TM.C("bg3"),
                          font=ctk.CTkFont(size=12, weight="bold"),
                          corner_radius=8,
                          command=lambda res=r: self._pick(res)).pack(fill="x")

            if r.get("genres"):
                ctk.CTkLabel(row, text=f"  {r['genres']}",
                             font=ctk.CTkFont(size=10), text_color=TM.C("muted"),
                             anchor="w").pack(fill="x", padx=4)

            if i < len(results) - 1:
                ctk.CTkFrame(self.res_frame, height=1,
                             fg_color=TM.C("border")).pack(fill="x", padx=8)

        self.res_frame.pack(fill="x", padx=26)

    def _pick(self, r):
        self._api_data = r
        self.res_frame.pack_forget()
        self.status_lbl.configure(text=f"✦  Selecionado: {r['title']}",
                                  text_color=TM.C("green"))
        for ent, val in [
            (self.title_ent,       r["title"]),
            (self.genre_ent,       r["genres"] or "Não definido"),
            (self.eps_total_ent,   str(r["episodes"]) if r["episodes"] else ""),
        ]:
            ent.delete(0, "end")
            ent.insert(0, val)
        if not self.score_ent.get().strip() and r.get("score"):
            self.score_ent.insert(0, str(r["score"]))
        self.cover_var.set(r.get("cover_url", ""))

    # ── Salvar ───────────────────────────────────────────────────────────────
    def _save(self):
        title = self.title_ent.get().strip()
        if not title:
            messagebox.showwarning("Obrigatório", "Título é obrigatório.", parent=self)
            return

        def si(v, d=0):
            try:    return max(0, int(float(v)))
            except: return d
        def sf(v, d=0.0):
            try:    return round(max(0.0, min(10.0, float(v))), 1)
            except: return d

        data = {
            "title":       title,
            "genre":       self.genre_ent.get().strip() or "Não definido",
            "score":       sf(self.score_ent.get()),
            "eps_watched": si(self.eps_watched_ent.get()),
            "eps_total":   si(self.eps_total_ent.get()),
            "status":      self.status_var.get(),
            "cover_url":   self.cover_var.get().strip(),
            "note":        self.note_ent.get().strip(),
            "favorito":    (self.anime or {}).get("favorito", False),
            "data_adicao": (self.anime or {}).get("data_adicao") or today_str(),
            "mal_id":      self._api_data.get("mal_id") or (self.anime or {}).get("mal_id"),
        }
        prev = (self.anime or {}).get("status", "")
        if data["status"] == "Concluído" and prev != "Concluído":
            data["data_conclusao"] = today_str()
        elif data["status"] != "Concluído":
            data["data_conclusao"] = None
        else:
            data["data_conclusao"] = (self.anime or {}).get("data_conclusao")

        self.on_save(data)
        self.destroy()

# ══════════════════════════════════════════════════════════════════════════════
#  CARD HORIZONTAL
# ══════════════════════════════════════════════════════════════════════════════
class AnimeCard(ctk.CTkFrame):
    STATUS_COLORS = {
        "Assistindo":       "#3d7ef5",
        "Planejo Assistir": "#5588ff",
        "Concluído":        "#2ea043",
    }

    def __init__(self, parent, anime, index, callbacks):
        fav        = anime.get("favorito", False)
        border_col = TM.C("border_fav") if fav else TM.C("border")
        bg_col     = TM.C("bg_fav")     if fav else TM.C("bg2")

        super().__init__(parent, corner_radius=12,
                         fg_color=bg_col, border_width=1, border_color=border_col)
        self.anime        = anime
        self.index        = index
        self.cbs          = callbacks
        self._bg_normal   = bg_col
        self._cover_img   = None
        self._build()
        self._bind_hover(self)

    def _bind_hover(self, w):
        w.bind("<Enter>", lambda _: self.configure(fg_color=TM.C("bg3")), add="+")
        w.bind("<Leave>", lambda _: self.configure(fg_color=self._bg_normal), add="+")
        for c in w.winfo_children():
            self._bind_hover(c)

    def _build(self):
        a  = self.anime
        sc = self.STATUS_COLORS.get(a.get("status", ""), "#555")

        # Stripe
        ctk.CTkFrame(self, width=4, corner_radius=0, fg_color=sc).pack(side="left", fill="y")

        # ── Capa ──────────────────────────────────────────────────────────
        thumb = ctk.CTkFrame(self, width=88, fg_color="transparent")
        thumb.pack(side="left", padx=(10, 8), pady=10)
        thumb.pack_propagate(False)

        url = a.get("cover_url", "")
        if url and REQUESTS_OK:
            ph = make_placeholder()
            if ph:
                self._img_lbl = ctk.CTkLabel(thumb, image=ph, text="")
            else:
                self._img_lbl = ctk.CTkLabel(thumb, text="🎬", font=ctk.CTkFont(size=26))
            self._img_lbl.pack(expand=True)
            threading.Thread(target=self._load_cover, args=(url,), daemon=True).start()
        else:
            box = ctk.CTkFrame(thumb, width=80, height=112, corner_radius=8,
                               fg_color=TM.C("bg0"), border_width=1, border_color=TM.C("border"))
            box.pack(expand=True)
            box.pack_propagate(False)
            ctk.CTkLabel(box, text="🎬", font=ctk.CTkFont(size=28)
                         ).place(relx=.5, rely=.5, anchor="center")

        # ── Info ──────────────────────────────────────────────────────────
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, pady=10, padx=(0, 4))

        tr = ctk.CTkFrame(info, fg_color="transparent")
        tr.pack(fill="x")
        fav_ico = "⭐" if a.get("favorito") else "☆"
        ctk.CTkButton(tr, text=fav_ico, width=26, height=22,
                      fg_color="transparent", hover_color=TM.accent_dark(),
                      font=ctk.CTkFont(size=15),
                      command=lambda: self.cbs["fav"](self.index)).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(tr, text=a.get("title", "—"),
                     font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w", wraplength=260).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(info, text=f"🎭  {a.get('genre') or '—'}",
                     font=ctk.CTkFont(size=11), text_color=TM.C("dim"),
                     anchor="w").pack(fill="x", pady=(2, 0))

        meta = ctk.CTkFrame(info, fg_color="transparent")
        meta.pack(fill="x", pady=(4, 0))
        score = a.get("score", 0)
        sc_c  = TM.C("yellow") if score >= 8 else ("#88aaff" if score >= 6 else TM.C("muted"))
        ctk.CTkLabel(meta, text=f"★ {score:.1f}",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=sc_c, anchor="w").pack(side="left")
        ctk.CTkLabel(meta, text=a.get("status", "—"),
                     font=ctk.CTkFont(size=10), text_color=sc,
                     fg_color=TM.C("bg0"), corner_radius=5).pack(side="left", padx=8)

        # Nota pessoal
        note = a.get("note", "").strip()
        if note:
            ctk.CTkLabel(info, text=f"💬 {note}",
                         font=ctk.CTkFont(size=10), text_color=TM.C("muted"),
                         anchor="w", wraplength=260).pack(fill="x", pady=(2, 0))

        # Datas
        parts = []
        if a.get("data_adicao"):    parts.append(f"📅 {a['data_adicao']}")
        if a.get("data_conclusao"): parts.append(f"✅ {a['data_conclusao']}")
        if parts:
            ctk.CTkLabel(info, text="  •  ".join(parts),
                         font=ctk.CTkFont(size=10), text_color=TM.C("muted"),
                         anchor="w").pack(fill="x", pady=(2, 0))

        # ── Controles ──────────────────────────────────────────────────────
        ctrl = ctk.CTkFrame(self, fg_color="transparent", width=155)
        ctrl.pack(side="right", padx=(0, 12), pady=10)
        ctrl.pack_propagate(False)

        ar = ctk.CTkFrame(ctrl, fg_color="transparent")
        ar.pack(fill="x")
        ctk.CTkButton(ar, text="✏", width=32, height=28, corner_radius=8,
                      fg_color=TM.C("bg0"), hover_color=TM.C("bg3"),
                      command=lambda: self.cbs["edit"](self.index)).pack(side="left")
        ctk.CTkButton(ar, text="✕", width=32, height=28, corner_radius=8,
                      fg_color="#3a1a1a", hover_color="#6e2020", text_color="#ff6b6b",
                      command=lambda: self.cbs["del"](self.index)).pack(side="left", padx=(6, 0))

        er = ctk.CTkFrame(ctrl, fg_color="transparent")
        er.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(er, text="−", width=28, height=28, corner_radius=6,
                      fg_color=TM.C("bg0"), hover_color=TM.C("bg3"),
                      command=lambda: self.cbs["eps"](self.index, -1)).pack(side="left")
        watched = a.get("eps_watched", 0)
        total   = a.get("eps_total", 0)
        ctk.CTkLabel(er, text=f"Ep {watched}/{total}" if total else f"Ep {watched}",
                     font=ctk.CTkFont(size=11), width=66).pack(side="left", padx=2)
        ctk.CTkButton(er, text="+", width=28, height=28, corner_radius=6,
                      fg_color=TM.accent_dark(), hover_color=TM.accent(),
                      command=lambda: self.cbs["eps"](self.index, +1)).pack(side="left")

        if total:
            prog = ctk.CTkProgressBar(ctrl, height=5, corner_radius=3,
                                      progress_color=sc, fg_color=TM.C("bg0"))
            prog.set(min(watched / total, 1.0))
            prog.pack(fill="x", pady=(6, 0))

    def _load_cover(self, url):
        img = load_ctk_image(url, (80, 112))
        if img:
            self._cover_img = img
            try: self.after(0, lambda: self._img_lbl.configure(image=img, text=""))
            except: pass

# ══════════════════════════════════════════════════════════════════════════════
#  ABA: MINHA LISTA
# ══════════════════════════════════════════════════════════════════════════════
class ListaTab(ctk.CTkFrame):
    FILTERS = ["Todos", "Favoritos", "Assistindo", "Planejo Assistir", "Concluído"]

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app        = app
        self.filter_var = ctk.StringVar(value="Todos")
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        self._build()

    def _build(self):
        # Toolbar
        tb = ctk.CTkFrame(self, fg_color=TM.C("bg0"), corner_radius=10)
        tb.pack(fill="x", padx=16, pady=(12, 8))

        ctk.CTkEntry(tb, textvariable=self.search_var,
                     placeholder_text="🔍  Filtrar por nome...",
                     height=34, width=220, corner_radius=8,
                     border_color=TM.C("border")).pack(side="left", padx=12, pady=8)

        for f in self.FILTERS:
            ctk.CTkButton(tb, text=f, height=30, corner_radius=8, width=0,
                          fg_color="transparent", hover_color=TM.accent_dark(),
                          font=ctk.CTkFont(size=12),
                          command=lambda x=f: self._set_filter(x)).pack(side="left", padx=3, pady=8)

        ctk.CTkButton(tb, text="＋  Adicionar", height=30, corner_radius=8,
                      fg_color=TM.accent(), hover_color=TM.accent_hover(),
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=self.app.open_add_modal).pack(side="right", padx=12, pady=8)

        # Scrollable list
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self.scroll.grid_columnconfigure(0, weight=1)

    def _set_filter(self, f):
        self.filter_var.set(f)
        self.refresh()

    def refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        query  = self.search_var.get().strip().lower()
        filt   = self.filter_var.get()
        animes = self.app.animes

        items = []
        for i, a in enumerate(animes):
            if filt == "Favoritos" and not a.get("favorito"):    continue
            if filt not in ("Todos","Favoritos") and a.get("status") != filt: continue
            if query and query not in a.get("title","").lower(): continue
            items.append((i, a))

        # Favoritos no topo
        items.sort(key=lambda x: (not x[1].get("favorito", False),))

        if not items:
            ctk.CTkLabel(self.scroll, text="Nenhum anime encontrado  🌙",
                         font=ctk.CTkFont(size=15), text_color=TM.C("muted")
                         ).grid(row=0, column=0, pady=60)
            return

        cbs = {"edit": self.app.open_edit_modal,
               "del":  self.app.delete_anime,
               "eps":  self.app.update_eps,
               "fav":  self.app.toggle_fav}
        for pos, (idx, anime) in enumerate(items):
            card = AnimeCard(self.scroll, anime, idx, cbs)
            card.grid(row=pos, column=0, sticky="ew", padx=4, pady=5)

# ══════════════════════════════════════════════════════════════════════════════
#  ABA: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
class DashboardTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._rec_thread = None
        self._build()

    def _build(self):
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=16, pady=12)

    def refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        animes    = self.app.animes
        total     = len(animes)
        watching  = sum(1 for a in animes if a.get("status") == "Assistindo")
        planned   = sum(1 for a in animes if a.get("status") == "Planejo Assistir")
        completed = sum(1 for a in animes if a.get("status") == "Concluído")
        favs      = sum(1 for a in animes if a.get("favorito"))
        scored    = [a["score"] for a in animes if a.get("score", 0) > 0]
        avg       = round(sum(scored) / len(scored), 1) if scored else 0
        eps_total = sum(a.get("eps_watched", 0) for a in animes)
        hours     = round(eps_total * 24 / 60, 1)

        # ── Título ──
        ctk.CTkLabel(self.scroll, text="📊  Dashboard",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     anchor="w").pack(fill="x", pady=(8, 14))

        # ── Stat chips ──
        chips_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        chips_frame.pack(fill="x", pady=(0, 16))

        stats = [
            ("🎬", str(total),   "Total de Animes", TM.accent()),
            ("✅", str(completed),"Concluídos",      TM.C("green")),
            ("▶",  str(watching), "Assistindo",      "#5588ff"),
            ("⭐", str(favs),     "Favoritos",       TM.C("yellow")),
            ("★",  f"{avg:.1f}", "Nota Média",      TM.C("yellow")),
            ("⏱",  f"{hours}h",  "Horas Assistidas",TM.accent()),
        ]
        for ico, val, lbl, col in stats:
            chip = ctk.CTkFrame(chips_frame, fg_color=TM.C("bg2"), corner_radius=12,
                                border_width=1, border_color=TM.C("border"))
            chip.pack(side="left", padx=4, fill="y")
            ctk.CTkLabel(chip, text=ico, font=ctk.CTkFont(size=20)).pack(pady=(10, 0), padx=16)
            ctk.CTkLabel(chip, text=val, font=ctk.CTkFont(size=22, weight="bold"),
                         text_color=col).pack(padx=16)
            ctk.CTkLabel(chip, text=lbl, font=ctk.CTkFont(size=10),
                         text_color=TM.C("muted")).pack(padx=16, pady=(0, 10))

        # ── Barra de progresso geral ──
        ctk.CTkLabel(self.scroll, text="PROGRESSO GERAL",
                     font=ctk.CTkFont(size=11), text_color=TM.C("muted"),
                     anchor="w").pack(fill="x", pady=(8, 4))

        prog_frame = ctk.CTkFrame(self.scroll, fg_color=TM.C("bg2"), corner_radius=10)
        prog_frame.pack(fill="x", pady=(0, 16))

        for label, count, color in [
            ("Concluídos",      completed, TM.C("green")),
            ("Assistindo",      watching,  TM.accent()),
            ("Planejo Assistir",planned,   "#5588ff"),
        ]:
            pct = count / total if total else 0
            row = ctk.CTkFrame(prog_frame, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(row, text=f"{label} ({count})", width=180,
                         font=ctk.CTkFont(size=12), anchor="w").pack(side="left")
            bar = ctk.CTkProgressBar(row, height=8, corner_radius=4,
                                     progress_color=color, fg_color=TM.C("bg0"))
            bar.set(pct)
            bar.pack(side="left", fill="x", expand=True, padx=(8, 12))
            ctk.CTkLabel(row, text=f"{pct*100:.0f}%", width=36,
                         font=ctk.CTkFont(size=11), text_color=TM.C("dim")).pack(side="left")

        # ── Top Favoritos ──
        favs_list = [a for a in animes if a.get("favorito")][:5]
        if favs_list:
            ctk.CTkLabel(self.scroll, text="⭐  TOP FAVORITOS",
                         font=ctk.CTkFont(size=11), text_color=TM.C("muted"),
                         anchor="w").pack(fill="x", pady=(8, 4))
            fav_frame = ctk.CTkFrame(self.scroll, fg_color=TM.C("bg2"), corner_radius=10)
            fav_frame.pack(fill="x", pady=(0, 16))
            for a in sorted(favs_list, key=lambda x: -x.get("score", 0)):
                r = ctk.CTkFrame(fav_frame, fg_color="transparent")
                r.pack(fill="x", padx=16, pady=4)
                ctk.CTkLabel(r, text=f"⭐  {a['title']}",
                             font=ctk.CTkFont(size=12), anchor="w").pack(side="left")
                ctk.CTkLabel(r, text=f"★ {a.get('score',0):.1f}",
                             font=ctk.CTkFont(size=12), text_color=TM.C("yellow"),
                             anchor="e").pack(side="right")

        # ── Recomendações Inteligentes ──
        ctk.CTkLabel(self.scroll, text="🤖  RECOMENDAÇÕES INTELIGENTES",
                     font=ctk.CTkFont(size=11), text_color=TM.C("muted"),
                     anchor="w").pack(fill="x", pady=(8, 4))

        self.rec_frame = ctk.CTkFrame(self.scroll, fg_color=TM.C("bg2"), corner_radius=10)
        self.rec_frame.pack(fill="x", pady=(0, 12))

        if not REQUESTS_OK:
            ctk.CTkLabel(self.rec_frame,
                         text="⚠  pip install requests pillow  para recomendações",
                         text_color=TM.C("muted")).pack(pady=16)
            return

        self._loading_lbl = ctk.CTkLabel(self.rec_frame,
                                         text="⏳  Buscando recomendações...",
                                         text_color=TM.accent())
        self._loading_lbl.pack(pady=16)
        threading.Thread(target=self._load_recs, daemon=True).start()

    def _load_recs(self):
        animes = self.app.animes
        # Coleta gêneros dos favoritos
        fav_genres_raw = []
        for a in animes:
            if a.get("favorito") and a.get("genre"):
                fav_genres_raw += [g.strip() for g in a["genre"].split(",")]

        # Mapeia nomes → IDs básicos do Jikan
        GENRE_IDS = {
            "Action":1, "Ação":1, "Adventure":2, "Aventura":2,
            "Comedy":4, "Comédia":4, "Drama":8, "Fantasy":10,
            "Fantasia":10, "Horror":14, "Terror":14, "Romance":22,
            "Sci-Fi":24, "Ficção Científica":24, "Sports":30, "Esportes":30,
            "Slice of Life":36, "Supernatural":37, "Sobrenatural":37,
            "Thriller":41, "Mystery":7, "Mistério":7, "Music":19, "Música":19,
        }

        if fav_genres_raw:
            from collections import Counter
            common = Counter(fav_genres_raw).most_common(3)
            genre_ids = [str(GENRE_IDS[g]) for g, _ in common if g in GENRE_IDS]
            genre_str = ",".join(genre_ids) if genre_ids else "1"
        else:
            genre_str = "1"   # Ação como fallback

        recs = get_recommendations(genre_str)
        self.after(0, lambda: self._show_recs(recs))

    def _show_recs(self, recs):
        try:
            self._loading_lbl.destroy()
        except: pass

        if not recs:
            ctk.CTkLabel(self.rec_frame, text="Nenhuma recomendação disponível no momento.",
                         text_color=TM.C("muted")).pack(pady=12)
            return

        note = ctk.CTkLabel(self.rec_frame,
                            text="Baseado nos gêneros dos seus favoritos via Jikan/MyAnimeList",
                            font=ctk.CTkFont(size=10), text_color=TM.C("muted"))
        note.pack(anchor="w", padx=16, pady=(8, 4))

        for r in recs:
            row = ctk.CTkFrame(self.rec_frame, fg_color=TM.C("bg0"), corner_radius=8)
            row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(row, text=r["title"],
                         font=ctk.CTkFont(size=12, weight="bold"),
                         anchor="w").pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(row, text=f"★ {r['score']:.1f}",
                         font=ctk.CTkFont(size=12), text_color=TM.C("yellow"),
                         anchor="e").pack(side="right", padx=12)
        ctk.CTkFrame(self.rec_frame, height=8, fg_color="transparent").pack()

# ══════════════════════════════════════════════════════════════════════════════
#  ABA: CONFIGURAÇÕES
# ══════════════════════════════════════════════════════════════════════════════
class ConfigTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        s = ctk.CTkScrollableFrame(self, fg_color="transparent")
        s.pack(fill="both", expand=True, padx=24, pady=16)

        ctk.CTkLabel(s, text="⚙️  Configurações",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     anchor="w").pack(fill="x", pady=(0, 20))

        # ── Aparência ──
        self._section(s, "🎨  APARÊNCIA")

        mf = ctk.CTkFrame(s, fg_color=TM.C("bg2"), corner_radius=10)
        mf.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(mf, text="Modo", font=ctk.CTkFont(size=13),
                     anchor="w").pack(side="left", padx=16, pady=12)
        self.mode_var = ctk.StringVar(value=TM.mode.capitalize())
        ctk.CTkSegmentedButton(mf, values=["Dark", "Light"],
                               variable=self.mode_var,
                               command=self._change_mode,
                               fg_color=TM.C("bg0"),
                               selected_color=TM.accent(),
                               selected_hover_color=TM.accent_hover()
                               ).pack(side="right", padx=16, pady=12)

        tf = ctk.CTkFrame(s, fg_color=TM.C("bg2"), corner_radius=10)
        tf.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(tf, text="Tema de cor", font=ctk.CTkFont(size=13),
                     anchor="w").pack(side="left", padx=16, pady=12)
        self.theme_var = ctk.StringVar(value=TM.theme)
        ctk.CTkSegmentedButton(tf, values=list(THEMES.keys()),
                               variable=self.theme_var,
                               command=self._change_theme,
                               fg_color=TM.C("bg0"),
                               selected_color=TM.accent(),
                               selected_hover_color=TM.accent_hover()
                               ).pack(side="right", padx=16, pady=12)

        # Prévia de cor
        self.preview = ctk.CTkFrame(s, height=8, corner_radius=4,
                                    fg_color=TM.accent())
        self.preview.pack(fill="x", pady=(0, 20))

        # ── Dados ──
        self._section(s, "💾  DADOS")

        df = ctk.CTkFrame(s, fg_color=TM.C("bg2"), corner_radius=10)
        df.pack(fill="x", pady=(0, 12))

        for label, desc, cmd in [
            ("Exportar Backup",  "Salva cópia datada do animes.json", export_backup),
            ("Abrir pasta",      "Abre a pasta onde os dados estão salvos",
             lambda: os.startfile(BASE_DIR) if sys.platform == "win32"
                     else os.system(f"open '{BASE_DIR}' 2>/dev/null || xdg-open '{BASE_DIR}' 2>/dev/null")),
        ]:
            r = ctk.CTkFrame(df, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=8)
            ctk.CTkLabel(r, text=label, font=ctk.CTkFont(size=13),
                         anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=desc, font=ctk.CTkFont(size=10),
                         text_color=TM.C("muted"), anchor="w").pack(side="left", padx=8)
            ctk.CTkButton(r, text="→", width=36, height=28, corner_radius=6,
                          fg_color=TM.accent(), hover_color=TM.accent_hover(),
                          command=cmd).pack(side="right")

        # ── Sobre ──
        self._section(s, "ℹ️  SOBRE")

        af = ctk.CTkFrame(s, fg_color=TM.C("bg2"), corner_radius=10)
        af.pack(fill="x")

        for line in [
            ("✦ Anime Manager v2.0",     TM.accent(),    True),
            ("Desenvolvido com CustomTkinter + Pillow", TM.C("text"), False),
            ("",                          TM.C("muted"),  False),
            ("📡 Dados fornecidos por Jikan API",       TM.C("dim"),  False),
            ("  api.jikan.moe — wrapper não-oficial do MyAnimeList", TM.C("muted"), False),
            ("",                          TM.C("muted"),  False),
            ("🗂 Seus dados ficam 100% locais em animes.json", TM.C("dim"), False),
            ("  Nenhuma informação é enviada a servidores externos.", TM.C("muted"), False),
        ]:
            ctk.CTkLabel(af, text=line[0],
                         font=ctk.CTkFont(size=13, weight="bold" if line[2] else "normal"),
                         text_color=line[1], anchor="w").pack(anchor="w", padx=16,
                                                               pady=(10, 0) if line[2] else (1, 0))
        ctk.CTkFrame(af, height=12, fg_color="transparent").pack()

    def _section(self, parent, text):
        ctk.CTkLabel(parent, text=text,
                     font=ctk.CTkFont(size=11), text_color=TM.C("muted"),
                     anchor="w").pack(fill="x", pady=(4, 6))

    def _change_mode(self, val):
        TM.set_mode(val.lower())
        self.app.apply_theme()

    def _change_theme(self, val):
        TM.set_theme(val)
        self.app.apply_theme()
        try:
            self.preview.configure(fg_color=TM.accent())
        except: pass

# ══════════════════════════════════════════════════════════════════════════════
#  APLICAÇÃO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
class AnimeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("✦ Anime Manager")
        self.geometry("1160x740")
        self.minsize(920, 560)

        self.animes = load_data()
        backup_on_startup()

        self._build_layout()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Top bar ──
        topbar = ctk.CTkFrame(self, height=52, fg_color=TM.C("bg0"),
                              corner_radius=0)
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_propagate(False)

        ctk.CTkLabel(topbar, text="  ✦  ANIME MANAGER",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=TM.accent()).pack(side="left", padx=16)

        # Contadores rápidos no topbar
        self.topbar_stats = ctk.CTkFrame(topbar, fg_color="transparent")
        self.topbar_stats.pack(side="right", padx=16)
        self._rebuild_topbar_stats()

        # ── Tabs ──
        self.tabs = ctk.CTkTabview(self, corner_radius=0,
                                   fg_color=TM.C("bg1"),
                                   segmented_button_fg_color=TM.C("bg0"),
                                   segmented_button_selected_color=TM.accent(),
                                   segmented_button_selected_hover_color=TM.accent_hover(),
                                   segmented_button_unselected_color=TM.C("bg0"),
                                   segmented_button_unselected_hover_color=TM.C("bg2"))
        self.tabs.grid(row=1, column=0, sticky="nsew")

        for name in ["🏠  Minha Lista", "📊  Dashboard", "⚙️  Configurações"]:
            self.tabs.add(name)

        # Instancia abas
        self.lista_tab   = ListaTab(self.tabs.tab("🏠  Minha Lista"), self)
        self.lista_tab.pack(fill="both", expand=True)

        self.dash_tab    = DashboardTab(self.tabs.tab("📊  Dashboard"), self)
        self.dash_tab.pack(fill="both", expand=True)

        self.config_tab  = ConfigTab(self.tabs.tab("⚙️  Configurações"), self)
        self.config_tab.pack(fill="both", expand=True)

        # Atualiza dashboard ao trocar de aba
        self.tabs.configure(command=self._on_tab_change)

        self.lista_tab.refresh()

    def _on_tab_change(self):
        tab = self.tabs.get()
        if "Dashboard" in tab:
            self.dash_tab.refresh()

    # ── Stats no topbar ───────────────────────────────────────────────────────
    def _rebuild_topbar_stats(self):
        for w in self.topbar_stats.winfo_children():
            w.destroy()
        for val, lbl, col in [
            (len(self.animes),                                         "Total",      TM.C("text")),
            (sum(1 for a in self.animes if a.get("status")=="Assistindo"), "▶",    TM.accent()),
            (sum(1 for a in self.animes if a.get("favorito")),         "⭐",         TM.C("yellow")),
            (sum(1 for a in self.animes if a.get("status")=="Concluído"),"✅",       TM.C("green")),
        ]:
            f = ctk.CTkFrame(self.topbar_stats, fg_color=TM.C("bg2"),
                             corner_radius=8, border_width=1, border_color=TM.C("border"))
            f.pack(side="left", padx=3)
            ctk.CTkLabel(f, text=f"{lbl} {val}",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=col).pack(padx=10, pady=5)

    # ── Callbacks públicos ────────────────────────────────────────────────────
    def open_add_modal(self):
        AnimeFormModal(self, on_save=self._add_anime)

    def open_edit_modal(self, idx):
        AnimeFormModal(self, on_save=lambda d: self._edit_anime(idx, d),
                       anime=self.animes[idx])

    def delete_anime(self, idx):
        name = self.animes[idx].get("title", "este anime")
        if messagebox.askyesno("Confirmar", f'Deletar "{name}"?'):
            self.animes.pop(idx)
            save_data(self.animes)
            self._refresh_all()

    def update_eps(self, idx, delta):
        a       = self.animes[idx]
        watched = max(0, a.get("eps_watched", 0) + delta)
        total   = a.get("eps_total", 0)
        if total and watched > total: watched = total
        self.animes[idx]["eps_watched"] = watched
        if total and watched == total and self.animes[idx].get("status") != "Concluído":
            self.animes[idx]["status"]         = "Concluído"
            self.animes[idx]["data_conclusao"] = today_str()
        save_data(self.animes)
        self._refresh_all()

    def toggle_fav(self, idx):
        self.animes[idx]["favorito"] = not self.animes[idx].get("favorito", False)
        save_data(self.animes)
        self._refresh_all()

    def _add_anime(self, data):
        self.animes.append(data)
        save_data(self.animes)
        self._refresh_all()

    def _edit_anime(self, idx, data):
        self.animes[idx] = data
        save_data(self.animes)
        self._refresh_all()

    def _refresh_all(self):
        self._rebuild_topbar_stats()
        self.lista_tab.refresh()

    # ── Tema dinâmico ─────────────────────────────────────────────────────────
    def apply_theme(self):
        """Reconstrói o layout inteiro para aplicar novo tema/modo."""
        for w in self.winfo_children():
            w.destroy()
        self._build_layout()

# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not REQUESTS_OK:
        print("⚠  Para busca automática e capas:  pip install pillow requests")
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = AnimeApp()
    app.mainloop()
