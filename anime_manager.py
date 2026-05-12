# ═══════════════════════════════════════════════════════════════════════════════
#  ✦  Anime Tracker Pro  v2.2.1
#  Dependências: pip install customtkinter pillow requests
#  Dados: Jikan API (MyAnimeList) — https://jikan.moe
#
#  FIXES v2.2.1:
#  - text_color usa tuplas (light, dark) em TODO o app → contraste automático
#  - Busca Jikan: botões de resultado criados diretamente no CTkScrollableFrame
#    sem container intermediário que bloqueava o render
# ═══════════════════════════════════════════════════════════════════════════════
import customtkinter as ctk
import json, os, sys, shutil, threading, io, time, re, webbrowser
from datetime import datetime
from tkinter import messagebox, filedialog

try:
    import requests
    from PIL import Image
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# ══════════════════════════════════════════════════════════════════════════════
#  VERSÃO / GITHUB
# ══════════════════════════════════════════════════════════════════════════════
CURRENT_VERSION = "2.2.1"
GITHUB_REPO     = "seu-usuario/anime-tracker-pro"
GITHUB_API_URL  = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_REL_URL  = f"https://github.com/{GITHUB_REPO}/releases/latest"

CHANGELOG = {
    "2.2.1": [
        "🔧 FIX CRÍTICO: text_color usa tuplas (light,dark) em todo o app — light mode corrigido",
        "🔧 FIX CRÍTICO: Busca Jikan — botões de resultado renderizados corretamente no ScrollableFrame",
        "🔧 FIX: Seleção de resultado preenche todos os campos e fecha a lista imediatamente",
    ],
    "2.2.0": [
        "🔧 FIX: Resultados da Jikan exibidos em ScrollableFrame dentro do modal",
        "🔧 FIX: UI atualizada corretamente na main thread após busca em background",
        "🔧 FIX: Temas aplicam accent color em TODOS os widgets via rebuild completo",
        "➕ Botão 'Modo Manual' no modal — desbloqueia campos sem depender da API",
        "🔧 FIX: App não trava sem internet — fallback gracioso",
        "🔄 Migração silenciosa de dados entre versões",
        "📋 Changelog completo na aba Configurações",
        "🎉 Popup de novidades no primeiro login de cada versão",
    ],
    "2.1.0": [
        "✨ Auto-Update via GitHub Releases",
        "🔄 Migração de dados sem perda de informação",
        "🌐 Graceful offline em toda chamada de rede",
    ],
    "2.0.0": [
        "🗂 Navegação por abas: Minha Lista, Dashboard, Configurações",
        "📊 Dashboard com estatísticas e recomendações inteligentes",
        "🎨 Temas dinâmicos: Azul, Laranja, Vermelho + Dark/Light",
    ],
    "1.x": [
        "🎌 CRUD completo, busca, filtros, favoritos, capas via Jikan",
        "💾 Backup automático, datas, progresso de episódios",
    ],
}

# ══════════════════════════════════════════════════════════════════════════════
#  PORTABILIDADE
# ══════════════════════════════════════════════════════════════════════════════
def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR    = _base_dir()
DATA_FILE   = os.path.join(BASE_DIR, "animes.json")
BACKUP_FILE = os.path.join(BASE_DIR, "animes_backup.json")
META_FILE   = os.path.join(BASE_DIR, ".app_meta.json")
os.makedirs(os.path.join(BASE_DIR, "assets", "covers"), exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
#  SISTEMA DE TEMAS
#  FIX v2.2.1: TM.T(key) retorna TUPLA (light_color, dark_color)
#  para que CTkinter faça o contraste automaticamente.
#  TM.C(key) ainda existe para fg_color de frames (não suporta tupla).
# ══════════════════════════════════════════════════════════════════════════════
ACCENT_PRESETS = {
    "Azul":     {"accent": "#3b8ed0", "hover": "#2a7abf", "dark": "#163a5e"},
    "Laranja":  {"accent": "#ff9500", "hover": "#e08400", "dark": "#5e3800"},
    "Vermelho": {"accent": "#e84040", "hover": "#cc2020", "dark": "#5e1010"},
}

# Paletas: (valor_light, valor_dark)
_PALETTE_TUPLES = {
    # fundos
    "bg0":        ("#c8d0ec", "#07070e"),
    "bg1":        ("#dce4f8", "#0d0d1a"),
    "bg2":        ("#e8eefa", "#12122a"),
    "bg3":        ("#d0d8f0", "#1a1a36"),
    "bg_card":    ("#eef1fd", "#141426"),
    "bg_fav":     ("#e8e0f8", "#16102a"),
    # bordas
    "border":     ("#b0b8d8", "#1e1e3a"),
    "border_fav": ("#7744cc", "#7744cc"),
    # textos com contraste automático
    "green":      ("#1a6e2a", "#2ea043"),
    "yellow":     ("#a06000", "#f0b429"),
    "red":        ("#cc2020", "#e84040"),
    "muted":      ("#7080a0", "#50507a"),
    "dim":        ("#4060a0", "#8080a8"),
    "text":       ("#0a0a2a", "#dde4ff"),
}

class _ThemeManager:
    _inst = None
    def __new__(cls):
        if cls._inst is None:
            cls._inst              = super().__new__(cls)
            cls._inst._mode        = "dark"
            cls._inst._preset_name = "Azul"
        return cls._inst

    @property
    def mode(self):   return self._mode
    @property
    def preset(self): return self._preset_name

    def accent(self) -> str: return ACCENT_PRESETS[self._preset_name]["accent"]
    def hover(self)  -> str: return ACCENT_PRESETS[self._preset_name]["hover"]
    def dark(self)   -> str: return ACCENT_PRESETS[self._preset_name]["dark"]

    def C(self, key: str) -> str:
        """Retorna cor como STRING para fg_color de frames (index 0=light, 1=dark)."""
        idx = 0 if self._mode == "light" else 1
        return _PALETTE_TUPLES.get(key, ("#ff00ff", "#ff00ff"))[idx]

    def T(self, key: str) -> tuple:
        """
        FIX v2.2.1 — Retorna TUPLA (light, dark) para text_color / border_color.
        O CTkinter escolhe automaticamente a cor certa pelo modo atual.
        """
        return _PALETTE_TUPLES.get(key, ("#ff00ff", "#ff00ff"))

    def set_mode(self, mode: str):
        self._mode = mode.lower()
        ctk.set_appearance_mode(self._mode)

    def set_preset(self, name: str):
        if name in ACCENT_PRESETS:
            self._preset_name = name

TM = _ThemeManager()

# ══════════════════════════════════════════════════════════════════════════════
#  MIGRAÇÃO / PERSISTÊNCIA
# ══════════════════════════════════════════════════════════════════════════════
ANIME_SCHEMA = {
    "title": "", "genre": "Não definido", "score": 0.0,
    "eps_watched": 0, "eps_total": 0, "status": "Planejo Assistir",
    "cover_url": "", "note": "", "favorito": False,
    "data_adicao": "", "data_conclusao": None, "mal_id": None,
}

def _migrate(a: dict) -> tuple:
    changed = False
    for f, d in ANIME_SCHEMA.items():
        if f not in a:
            a[f] = d
            changed = True
    return a, changed

def load_data() -> list:
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:    raw = json.load(f)
        except: return []
    animes, dirty = [], False
    for item in raw:
        item, m = _migrate(item)
        if m: dirty = True
        animes.append(item)
    if dirty:
        save_data(animes)
    return animes

def save_data(animes: list):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(animes, f, ensure_ascii=False, indent=2)

def backup_on_startup():
    if os.path.exists(DATA_FILE):
        shutil.copy2(DATA_FILE, BACKUP_FILE)

def export_backup():
    today = datetime.now().strftime("%Y-%m-%d")
    dest  = filedialog.asksaveasfilename(
        title="Exportar Backup", initialfile=f"animes_backup_{today}.json",
        defaultextension=".json", filetypes=[("JSON", "*.json")])
    if dest and os.path.exists(DATA_FILE):
        shutil.copy2(DATA_FILE, dest)
        messagebox.showinfo("Backup exportado", f"Salvo em:\n{dest}")

def today_str() -> str:
    return datetime.now().strftime("%d/%m/%Y")

# ══════════════════════════════════════════════════════════════════════════════
#  META / AUTO-UPDATE
# ══════════════════════════════════════════════════════════════════════════════
def _load_meta() -> dict:
    try:
        if os.path.exists(META_FILE):
            with open(META_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_meta(m: dict):
    try:
        with open(META_FILE, "w") as f:
            json.dump(m, f, indent=2)
    except Exception:
        pass

def is_first_run() -> bool:
    return _load_meta().get("last_version") != CURRENT_VERSION

def mark_version_seen():
    m = _load_meta()
    m["last_version"] = CURRENT_VERSION
    _save_meta(m)

def _ver(v: str) -> tuple:
    try:    return tuple(int(x) for x in re.sub(r"[^0-9.]", "", v).split(".") if x)
    except: return (0,)

def check_for_updates() -> dict | None:
    if not REQUESTS_OK:
        return None
    try:
        r = requests.get(GITHUB_API_URL, timeout=5,
                         headers={"Accept": "application/vnd.github+json"})
        if r.status_code != 200:
            return None
        d   = r.json()
        tag = d.get("tag_name", "").lstrip("v")
        if _ver(tag) > _ver(CURRENT_VERSION):
            return {"version": tag,
                    "url":     d.get("html_url", GITHUB_REL_URL),
                    "notes":   (d.get("body") or "")[:600]}
    except Exception:
        pass
    return None

# ══════════════════════════════════════════════════════════════════════════════
#  JIKAN API
# ══════════════════════════════════════════════════════════════════════════════
_LAST_REQ = 0.0
_JIKAN_SEARCH = "https://api.jikan.moe/v4/anime?q={q}&limit=5&sfw=true"
_JIKAN_RECS   = "https://api.jikan.moe/v4/anime?genres={g}&order_by=score&sort=desc&limit=6&sfw=true"

def _jikan_get(url: str) -> dict:
    global _LAST_REQ
    gap = time.monotonic() - _LAST_REQ
    if gap < 0.7:
        time.sleep(0.7 - gap)
    try:
        r = requests.get(url, timeout=9)
        _LAST_REQ = time.monotonic()
        return r.json()
    except Exception:
        return {}

def _parse_item(d: dict) -> dict:
    gr = d.get("genres", [])
    return {
        "mal_id":    d.get("mal_id"),
        "title":     d.get("title_english") or d.get("title", ""),
        "genres":    ", ".join(g["name"] for g in gr) if gr else "Não definido",
        "episodes":  d.get("episodes") or 0,
        "cover_url": d.get("images", {}).get("jpg", {}).get("image_url", ""),
        "year":      str(d.get("year") or ""),
        "score":     float(d.get("score") or 0),
    }

def jikan_search(query: str) -> list:
    if not REQUESTS_OK or not query.strip():
        return []
    data = _jikan_get(_JIKAN_SEARCH.format(q=requests.utils.quote(query.strip()))).get("data", [])
    return [_parse_item(i) for i in data[:5]]

def jikan_recs(genre_ids: str) -> list:
    if not REQUESTS_OK:
        return []
    data = _jikan_get(_JIKAN_RECS.format(g=genre_ids)).get("data", [])
    return [_parse_item(i) for i in data[:6]]

def _dl_image(url: str, size=(82, 114)) -> "ctk.CTkImage | None":
    if not REQUESTS_OK or not url:
        return None
    try:
        raw = requests.get(url, timeout=8).content
        pil = Image.open(io.BytesIO(raw)).convert("RGBA")
        return ctk.CTkImage(light_image=pil, dark_image=pil, size=size)
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════════════════════
#  POPUPS
# ══════════════════════════════════════════════════════════════════════════════
class WhatsNewModal(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(f"✦ Novidades — v{CURRENT_VERSION}")
        self.geometry("520x500")
        self.resizable(False, False)
        self.grab_set()
        self.focus()
        self._build()

    def _build(self):
        ctk.CTkLabel(self,
                     text=f"✨  Novidades na v{CURRENT_VERSION}",
                     font=ctk.CTkFont(size=19, weight="bold"),
                     text_color=TM.accent()).pack(pady=(22, 4))
        ctk.CTkLabel(self,
                     text="Obrigado por usar o Anime Tracker Pro!",
                     font=ctk.CTkFont(size=12),
                     text_color=TM.T("dim")).pack()
        ctk.CTkFrame(self, height=1, fg_color=TM.C("border")).pack(fill="x", padx=28, pady=12)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", height=310)
        scroll.pack(fill="x", padx=24, pady=(0, 8))
        for line in CHANGELOG.get(CURRENT_VERSION, []):
            f = ctk.CTkFrame(scroll, fg_color=TM.C("bg2"), corner_radius=8)
            f.pack(fill="x", pady=3)
            ctk.CTkLabel(f, text=line, anchor="w",
                         font=ctk.CTkFont(size=12),
                         text_color=TM.T("text"),
                         wraplength=440).pack(fill="x", padx=12, pady=6)

        ctk.CTkButton(self, text="🚀  Começar",
                      height=40, fg_color=TM.accent(), hover_color=TM.hover(),
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self.destroy).pack(pady=(8, 16))


class _UpdateBanner(ctk.CTkFrame):
    def __init__(self, parent, info: dict):
        super().__init__(parent, fg_color="#0f2010",
                         border_width=1, border_color="#2a5020", corner_radius=8)
        ctk.CTkLabel(self,
                     text=f"🔔  Nova versão disponível: v{info['version']}",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#77dd44").pack(side="left", padx=14, pady=8)
        ctk.CTkButton(self, text="Ver novidades →", height=26, corner_radius=6,
                      fg_color="#1a4010", hover_color="#2a6020", text_color="#aaffaa",
                      font=ctk.CTkFont(size=11),
                      command=lambda: webbrowser.open(info["url"])
                      ).pack(side="right", padx=(0, 8), pady=8)
        ctk.CTkButton(self, text="✕", width=26, height=26, corner_radius=6,
                      fg_color="transparent", hover_color="#1a2a10",
                      text_color="#557733", command=self.destroy
                      ).pack(side="right", pady=8)

# ══════════════════════════════════════════════════════════════════════════════
#  MODAL DE ADIÇÃO / EDIÇÃO
#
#  FIX v2.2.1 — Busca Jikan:
#  - _results_scroll é um CTkScrollableFrame filho DIRETO de self (não aninhado)
#  - Botões criados com .pack(fill="x", pady=2) direto no _results_scroll
#  - Sem container intermediário que bloqueava o render
#  - _results_scroll.pack() / pack_forget() controlam visibilidade
# ══════════════════════════════════════════════════════════════════════════════
class AnimeFormModal(ctk.CTkToplevel):
    def __init__(self, parent, on_save, anime=None):
        super().__init__(parent)
        self.on_save   = on_save
        self.anime     = anime
        self._is_edit  = anime is not None
        self._api_pick = {}
        self.cover_var = ctk.StringVar(value=(anime or {}).get("cover_url", ""))

        self.title("✦ Editar Anime" if self._is_edit else "✦ Adicionar Anime")
        self.geometry("520x740")
        self.resizable(False, False)
        self.grab_set()
        self.focus()
        self._build()
        if self._is_edit:
            self._fill_fields(anime)

    def _build(self):
        # ── Header ──────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=TM.C("bg0"), corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr,
                     text="Editar Anime" if self._is_edit else "Adicionar Anime",
                     font=ctk.CTkFont(size=20, weight="bold")
                     # sem text_color → CTkinter escolhe automaticamente
                     ).pack(pady=(18, 2))
        ctk.CTkLabel(hdr,
                     text="Edite os campos abaixo" if self._is_edit
                          else "Busque pelo nome ou use o Modo Manual",
                     font=ctk.CTkFont(size=11),
                     text_color=TM.T("dim")   # ← TUPLA: contraste automático
                     ).pack(pady=(0, 14))

        # ── Barra de busca (somente modo Adicionar) ─────────────────────────
        if not self._is_edit:
            sf = ctk.CTkFrame(self, fg_color="transparent")
            sf.pack(fill="x", padx=22, pady=(10, 0))

            self._search_ent = ctk.CTkEntry(
                sf, placeholder_text="🔍  Nome do anime...",
                height=40, corner_radius=10, border_color=TM.accent())
            self._search_ent.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self._search_ent.bind("<Return>", lambda _: self._do_search())

            self._search_btn = ctk.CTkButton(
                sf, text="Buscar", width=82, height=40,
                fg_color=TM.accent(), hover_color=TM.hover(),
                font=ctk.CTkFont(size=13, weight="bold"),
                command=self._do_search)
            self._search_btn.pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                sf, text="✏ Manual", width=82, height=40,
                fg_color=TM.C("bg3"), hover_color=TM.C("bg2"),
                text_color=TM.T("text"),   # ← TUPLA
                font=ctk.CTkFont(size=12),
                command=self._activate_manual
            ).pack(side="left")

            # Label de status
            self._status_lbl = ctk.CTkLabel(
                self, text="", font=ctk.CTkFont(size=11), text_color=TM.accent())
            self._status_lbl.pack(anchor="w", padx=22, pady=(4, 0))

            # ── FIX v2.2.1: CTkScrollableFrame filho DIRETO de self ──────────
            # Sem wrapper intermediário. pack_forget() / pack() controlam visibilidade.
            self._results_scroll = ctk.CTkScrollableFrame(
                self,
                fg_color=TM.C("bg0"),
                border_width=1,
                border_color=TM.C("border"),
                corner_radius=10,
                height=170,
                label_text="",
            )
            # Começa oculto — mostrado só quando há resultados
            # (não chamamos .pack() aqui)

        # ── Separador ────────────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color=TM.C("border")).pack(fill="x", padx=22, pady=(10, 0))
        ctk.CTkLabel(self, text="DETALHES DO ANIME",
                     font=ctk.CTkFont(size=10),
                     text_color=TM.T("muted")   # ← TUPLA
                     ).pack(anchor="w", padx=22, pady=(4, 0))

        p = {"padx": 22, "pady": (5, 0)}

        # ── Campos ───────────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Título *", anchor="w",
                     text_color=TM.T("text")).pack(fill="x", **p)
        self._title_ent = ctk.CTkEntry(self, placeholder_text="Ex.: Fullmetal Alchemist", height=36)
        self._title_ent.pack(fill="x", **p)

        ctk.CTkLabel(self, text="Gênero", anchor="w",
                     text_color=TM.T("text")).pack(fill="x", **p)
        self._genre_ent = ctk.CTkEntry(self, placeholder_text="Ação, Aventura...", height=36)
        self._genre_ent.pack(fill="x", **p)

        row_num = ctk.CTkFrame(self, fg_color="transparent")
        row_num.pack(fill="x", **p)
        _vcmd = (self.register(lambda s: re.match(r"^\d*\.?\d*$", s) is not None), "%P")
        for attr, lbl, ph in [("_eps_w","Ep. Vistos","0"),
                               ("_eps_t","Ep. Total","12"),
                               ("_score","Nota (0-10)","0.0")]:
            col = ctk.CTkFrame(row_num, fg_color="transparent")
            col.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ctk.CTkLabel(col, text=lbl, anchor="w",
                         text_color=TM.T("text")).pack(fill="x")
            ent = ctk.CTkEntry(col, placeholder_text=ph, height=36,
                               validate="key", validatecommand=_vcmd)
            ent.pack(fill="x")
            setattr(self, attr, ent)

        ctk.CTkLabel(self, text="Status", anchor="w",
                     text_color=TM.T("text")).pack(fill="x", **p)
        self._status_var = ctk.StringVar(value="Planejo Assistir")
        self._status_opt = ctk.CTkOptionMenu(
            self, values=["Assistindo","Planejo Assistir","Concluído"],
            variable=self._status_var, height=36,
            fg_color=TM.C("bg2"),
            button_color=TM.accent(), button_hover_color=TM.hover())
        self._status_opt.pack(fill="x", **p)

        ctk.CTkLabel(self, text="Nota Pessoal", anchor="w",
                     text_color=TM.T("text")).pack(fill="x", **p)
        self._note_ent = ctk.CTkEntry(
            self, placeholder_text="Comentário rápido...", height=36)
        self._note_ent.pack(fill="x", **p)

        ctk.CTkLabel(self, text="URL da Capa", anchor="w",
                     text_color=TM.T("text")).pack(fill="x", **p)
        self._cover_ent = ctk.CTkEntry(
            self, textvariable=self.cover_var,
            placeholder_text="Preenchida automaticamente pela busca", height=36)
        self._cover_ent.pack(fill="x", **p)

        ctk.CTkButton(
            self, text="💾  Salvar Anime", height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=TM.accent(), hover_color=TM.hover(),
            command=self._save
        ).pack(fill="x", padx=22, pady=(14, 6))

        if not REQUESTS_OK:
            ctk.CTkLabel(self,
                         text="⚠  pip install requests pillow  para busca automática",
                         font=ctk.CTkFont(size=10),
                         text_color=("#b05000", "#dd8844")  # ← TUPLA
                         ).pack(pady=(0, 4))

        # Bloqueia campos até selecionar resultado ou ativar modo manual
        if not self._is_edit:
            self._lock_fields()

    # ── Estado dos campos ────────────────────────────────────────────────────
    def _lock_fields(self):
        for w in [self._title_ent, self._genre_ent, self._eps_w,
                  self._eps_t, self._score, self._note_ent, self._cover_ent]:
            w.configure(state="disabled")
        self._status_opt.configure(state="disabled")

    def _unlock_fields(self):
        for w in [self._title_ent, self._genre_ent, self._eps_w,
                  self._eps_t, self._score, self._note_ent, self._cover_ent]:
            w.configure(state="normal")
        self._status_opt.configure(state="normal")

    def _activate_manual(self):
        self._hide_results()
        self._unlock_fields()
        self._status_lbl.configure(
            text="✏  Modo Manual ativo — preencha os campos livremente",
            text_color=TM.T("dim"))

    # ── Mostrar / ocultar lista de resultados ────────────────────────────────
    def _show_results(self):
        self._results_scroll.pack(fill="x", padx=22, pady=(2, 0))

    def _hide_results(self):
        self._results_scroll.pack_forget()

    # ── Busca ────────────────────────────────────────────────────────────────
    def _do_search(self):
        if not REQUESTS_OK:
            self._activate_manual()
            self._status_lbl.configure(
                text="❌  requests não instalado — modo manual ativado",
                text_color=("#cc2000", "#ff6644"))
            return
        q = self._search_ent.get().strip()
        if not q:
            return

        self._search_btn.configure(state="disabled", text="⏳")
        self._status_lbl.configure(
            text="⏳  Buscando em Jikan / MyAnimeList...",
            text_color=TM.accent())
        self._hide_results()

        # Limpa resultados anteriores
        for w in self._results_scroll.winfo_children():
            w.destroy()

        threading.Thread(target=self._search_thread, args=(q,), daemon=True).start()

    def _search_thread(self, q: str):
        results = jikan_search(q)
        # FIX: sempre volta para a main thread via after()
        self.after(0, lambda: self._on_results(results))

    def _on_results(self, results: list):
        """
        FIX v2.2.1 — Botões criados DIRETAMENTE no CTkScrollableFrame.
        Sem frames intermediários que bloqueavam a renderização.
        """
        self._search_btn.configure(state="normal", text="Buscar")

        if not results:
            self._status_lbl.configure(
                text="❌  Sem resultados. Tente outro nome ou use Modo Manual.",
                text_color=("#cc2000", "#ff6644"))
            return

        self._status_lbl.configure(
            text=f"✅  {len(results)} resultado(s) — clique para selecionar",
            text_color=TM.T("green"))

        for r in results:
            y = f" ({r['year']})" if r.get("year") else ""
            e = f" · {r['episodes']} eps" if r.get("episodes") else ""
            s = f" · ★{r['score']:.1f}" if r.get("score") else ""
            top_line = f"{r['title']}{y}{e}{s}"
            sub_line  = f"🎭 {r['genres']}" if r.get("genres") else ""

            # Botão principal — clicável, preenche campos
            ctk.CTkButton(
                self._results_scroll,
                text=top_line,
                anchor="w",
                height=34,
                fg_color=TM.C("bg2"),
                hover_color=TM.C("bg3"),
                text_color=TM.T("text"),      # ← TUPLA: contraste automático
                font=ctk.CTkFont(size=12, weight="bold"),
                corner_radius=8,
                command=lambda res=r: self._pick(res),
            ).pack(fill="x", padx=4, pady=(4, 0))

            # Sublabel de gênero
            if sub_line:
                ctk.CTkLabel(
                    self._results_scroll,
                    text=f"  {sub_line}",
                    font=ctk.CTkFont(size=10),
                    text_color=TM.T("muted"),  # ← TUPLA
                    anchor="w",
                ).pack(fill="x", padx=10, pady=(0, 2))

        self._show_results()

    def _pick(self, r: dict):
        """Preenche campos e fecha a lista."""
        self._api_pick = r
        self._hide_results()
        self._status_lbl.configure(
            text=f"✦  Selecionado: {r['title']}",
            text_color=TM.T("green"))
        self._unlock_fields()

        # Preenche automaticamente
        for ent, val in [
            (self._title_ent, r["title"]),
            (self._genre_ent, r["genres"] or "Não definido"),
            (self._eps_t,     str(r["episodes"]) if r.get("episodes") else ""),
        ]:
            ent.delete(0, "end")
            ent.insert(0, val)

        if not self._score.get().strip() and r.get("score"):
            self._score.insert(0, str(r["score"]))
        self.cover_var.set(r.get("cover_url", ""))

    def _fill_fields(self, a: dict):
        for ent, key in [(self._title_ent,"title"),(self._genre_ent,"genre"),
                         (self._score,"score"),(self._eps_w,"eps_watched"),
                         (self._eps_t,"eps_total"),(self._note_ent,"note")]:
            ent.insert(0, str(a.get(key, "")))
        self._status_var.set(a.get("status","Planejo Assistir"))

    def _save(self):
        title = self._title_ent.get().strip()
        if not title:
            messagebox.showwarning("Campo obrigatório","O Título é obrigatório.",parent=self)
            return
        def si(v,d=0):
            try:    return max(0,int(float(v)))
            except: return d
        def sf(v,d=0.0):
            try:    return round(max(0.0,min(10.0,float(v))),1)
            except: return d
        prev   = (self.anime or {}).get("status","")
        status = self._status_var.get()
        data = {
            "title":         title,
            "genre":         self._genre_ent.get().strip() or "Não definido",
            "score":         sf(self._score.get()),
            "eps_watched":   si(self._eps_w.get()),
            "eps_total":     si(self._eps_t.get()),
            "status":        status,
            "cover_url":     self.cover_var.get().strip(),
            "note":          self._note_ent.get().strip(),
            "favorito":      (self.anime or {}).get("favorito",False),
            "data_adicao":   (self.anime or {}).get("data_adicao") or today_str(),
            "mal_id":        self._api_pick.get("mal_id") or (self.anime or {}).get("mal_id"),
        }
        if status == "Concluído" and prev != "Concluído":
            data["data_conclusao"] = today_str()
        elif status != "Concluído":
            data["data_conclusao"] = None
        else:
            data["data_conclusao"] = (self.anime or {}).get("data_conclusao")
        self.on_save(data)
        self.destroy()

# ══════════════════════════════════════════════════════════════════════════════
#  CARD HORIZONTAL
# ══════════════════════════════════════════════════════════════════════════════
_ST_COLORS = {
    "Assistindo":       "#3d7ef5",
    "Planejo Assistir": "#5577ee",
    "Concluído":        "#2ea043",
}

class AnimeCard(ctk.CTkFrame):
    def __init__(self, parent, anime, index, cbs):
        fav = anime.get("favorito", False)
        super().__init__(
            parent, corner_radius=12,
            fg_color=TM.C("bg_fav") if fav else TM.C("bg_card"),
            border_width=1,
            border_color=TM.C("border_fav") if fav else TM.C("border"))
        self.anime    = anime
        self.index    = index
        self.cbs      = cbs
        self._bg_n    = TM.C("bg_fav") if fav else TM.C("bg_card")
        self._img_ref = None
        self._build()
        self._bind_hover(self)

    def _bind_hover(self, w):
        w.bind("<Enter>", lambda _: self.configure(fg_color=TM.C("bg3")), add="+")
        w.bind("<Leave>", lambda _: self.configure(fg_color=self._bg_n),  add="+")
        for c in w.winfo_children():
            self._bind_hover(c)

    def _build(self):
        a  = self.anime
        sc = _ST_COLORS.get(a.get("status",""), TM.C("muted"))

        # Stripe lateral
        ctk.CTkFrame(self, width=4, corner_radius=0, fg_color=sc).pack(side="left", fill="y")

        # ── Capa ──────────────────────────────────────────────────────────
        thumb = ctk.CTkFrame(self, width=90, fg_color="transparent")
        thumb.pack(side="left", padx=(8,8), pady=8)
        thumb.pack_propagate(False)
        url = a.get("cover_url","")
        if url and REQUESTS_OK:
            self._img_lbl = ctk.CTkLabel(thumb, text="🎬", font=ctk.CTkFont(size=26))
            self._img_lbl.pack(expand=True)
            threading.Thread(target=self._load_cover, args=(url,), daemon=True).start()
        else:
            box = ctk.CTkFrame(thumb, width=82, height=114, corner_radius=8,
                               fg_color=TM.C("bg0"), border_width=1, border_color=TM.C("border"))
            box.pack(expand=True)
            box.pack_propagate(False)
            ctk.CTkLabel(box, text="🎬", font=ctk.CTkFont(size=28)
                         ).place(relx=.5, rely=.5, anchor="center")

        # ── Informações ────────────────────────────────────────────────────
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, pady=8)

        tr = ctk.CTkFrame(info, fg_color="transparent")
        tr.pack(fill="x")
        fav_ico = "⭐" if a.get("favorito") else "☆"
        ctk.CTkButton(tr, text=fav_ico, width=24, height=22,
                      fg_color="transparent", hover_color=TM.dark(),
                      font=ctk.CTkFont(size=14),
                      command=lambda: self.cbs["fav"](self.index)).pack(side="left", padx=(0,4))
        ctk.CTkLabel(tr, text=a.get("title","—"),
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=TM.T("text"),      # ← TUPLA
                     anchor="w", wraplength=265).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(info, text=f"🎭  {a.get('genre') or '—'}",
                     font=ctk.CTkFont(size=11),
                     text_color=TM.T("dim"),        # ← TUPLA
                     anchor="w").pack(fill="x", pady=(2,0))

        meta = ctk.CTkFrame(info, fg_color="transparent")
        meta.pack(fill="x", pady=(3,0))
        score   = a.get("score",0)
        sc_col  = TM.T("yellow") if score >= 8 else (("#4455cc","#88aaff") if score >= 6 else TM.T("muted"))
        ctk.CTkLabel(meta, text=f"★ {score:.1f}",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=sc_col, anchor="w").pack(side="left")
        ctk.CTkLabel(meta, text=f"  {a.get('status','—')}  ",
                     font=ctk.CTkFont(size=10), text_color=sc,
                     fg_color=TM.C("bg0"), corner_radius=5).pack(side="left", padx=6)

        if a.get("note","").strip():
            ctk.CTkLabel(info, text=f"💬 {a['note']}",
                         font=ctk.CTkFont(size=10),
                         text_color=TM.T("muted"),  # ← TUPLA
                         anchor="w", wraplength=255).pack(fill="x", pady=(2,0))

        parts = []
        if a.get("data_adicao"):    parts.append(f"📅 {a['data_adicao']}")
        if a.get("data_conclusao"): parts.append(f"✅ {a['data_conclusao']}")
        if parts:
            ctk.CTkLabel(info, text="  •  ".join(parts),
                         font=ctk.CTkFont(size=10),
                         text_color=TM.T("muted"),  # ← TUPLA
                         anchor="w").pack(fill="x", pady=(2,0))

        # ── Controles ─────────────────────────────────────────────────────
        ctrl = ctk.CTkFrame(self, fg_color="transparent", width=158)
        ctrl.pack(side="right", padx=(0,12), pady=8)
        ctrl.pack_propagate(False)

        ar = ctk.CTkFrame(ctrl, fg_color="transparent")
        ar.pack(fill="x")
        ctk.CTkButton(ar, text="✏", width=32, height=28, corner_radius=8,
                      fg_color=TM.C("bg0"), hover_color=TM.C("bg3"),
                      command=lambda: self.cbs["edit"](self.index)).pack(side="left")
        ctk.CTkButton(ar, text="✕", width=32, height=28, corner_radius=8,
                      fg_color="#3a1010", hover_color="#6e1a1a", text_color="#ff7070",
                      command=lambda: self.cbs["del"](self.index)).pack(side="left", padx=(6,0))

        er = ctk.CTkFrame(ctrl, fg_color="transparent")
        er.pack(fill="x", pady=(8,0))
        ctk.CTkButton(er, text="−", width=28, height=28, corner_radius=6,
                      fg_color=TM.C("bg0"), hover_color=TM.C("bg3"),
                      command=lambda: self.cbs["eps"](self.index,-1)).pack(side="left")
        watched = a.get("eps_watched",0)
        total   = a.get("eps_total",0)
        ctk.CTkLabel(er,
                     text=f"Ep {watched}/{total}" if total else f"Ep {watched}",
                     font=ctk.CTkFont(size=11),
                     text_color=TM.T("text"),  # ← TUPLA
                     width=68).pack(side="left", padx=2)
        ctk.CTkButton(er, text="+", width=28, height=28, corner_radius=6,
                      fg_color=TM.dark(), hover_color=TM.accent(),
                      command=lambda: self.cbs["eps"](self.index,+1)).pack(side="left")

        if total:
            prog = ctk.CTkProgressBar(ctrl, height=5, corner_radius=3,
                                      progress_color=sc, fg_color=TM.C("bg0"))
            prog.set(min(watched/total,1.0))
            prog.pack(fill="x", pady=(6,0))

    def _load_cover(self, url):
        img = _dl_image(url, (82,114))
        if img:
            self._img_ref = img
            try: self.after(0, lambda: self._img_lbl.configure(image=img, text=""))
            except: pass

# ══════════════════════════════════════════════════════════════════════════════
#  ABA — MINHA LISTA
# ══════════════════════════════════════════════════════════════════════════════
class ListaTab(ctk.CTkFrame):
    _FILTERS = ["Todos","Favoritos","Assistindo","Planejo Assistir","Concluído"]

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app      = app
        self._filter  = ctk.StringVar(value="Todos")
        self._search  = ctk.StringVar()
        self._search.trace_add("write", lambda *_: self.refresh())
        self._build()

    def _build(self):
        tb = ctk.CTkFrame(self, fg_color=TM.C("bg0"), corner_radius=10)
        tb.pack(fill="x", padx=14, pady=(10,8))

        ctk.CTkEntry(tb, textvariable=self._search,
                     placeholder_text="🔍  Filtrar por nome...",
                     height=34, width=220, corner_radius=8,
                     border_color=TM.C("border")
                     ).pack(side="left", padx=10, pady=8)

        for f in self._FILTERS:
            ctk.CTkButton(tb, text=f, height=28, corner_radius=8, width=0,
                          fg_color="transparent", hover_color=TM.dark(),
                          text_color=TM.T("text"),  # ← TUPLA
                          font=ctk.CTkFont(size=11),
                          command=lambda x=f: self._set_f(x)
                          ).pack(side="left", padx=2, pady=8)

        ctk.CTkButton(tb, text="＋  Adicionar", height=30, corner_radius=8,
                      fg_color=TM.accent(), hover_color=TM.hover(),
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=self.app.open_add_modal
                      ).pack(side="right", padx=10, pady=8)

        self._banner_slot = ctk.CTkFrame(self, fg_color="transparent")
        self._banner_slot.pack(fill="x", padx=14)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=14, pady=(0,10))
        self._scroll.grid_columnconfigure(0, weight=1)

    def show_update_banner(self, info):
        for w in self._banner_slot.winfo_children():
            w.destroy()
        _UpdateBanner(self._banner_slot, info).pack(fill="x", pady=(0,6))

    def _set_f(self, f):
        self._filter.set(f)
        self.refresh()

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        q    = self._search.get().strip().lower()
        filt = self._filter.get()
        items = []
        for i, a in enumerate(self.app.animes):
            if filt == "Favoritos" and not a.get("favorito"): continue
            if filt not in ("Todos","Favoritos") and a.get("status") != filt: continue
            if q and q not in a.get("title","").lower(): continue
            items.append((i, a))
        items.sort(key=lambda x: (not x[1].get("favorito",False),))
        if not items:
            ctk.CTkLabel(self._scroll,
                         text="Nenhum anime aqui ainda  🌙",
                         font=ctk.CTkFont(size=15),
                         text_color=TM.T("muted")  # ← TUPLA
                         ).grid(row=0, column=0, pady=60)
            return
        cbs = {"edit":self.app.open_edit_modal,"del":self.app.delete_anime,
               "eps":self.app.update_eps,"fav":self.app.toggle_fav}
        for pos,(idx,anime) in enumerate(items):
            AnimeCard(self._scroll, anime, idx, cbs).grid(
                row=pos, column=0, sticky="ew", padx=4, pady=5)

# ══════════════════════════════════════════════════════════════════════════════
#  ABA — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
_GENRE_IDS = {
    "Action":1,"Ação":1,"Adventure":2,"Aventura":2,"Comedy":4,"Comédia":4,
    "Drama":8,"Fantasy":10,"Fantasia":10,"Horror":14,"Terror":14,"Romance":22,
    "Sci-Fi":24,"Sports":30,"Esportes":30,"Slice of Life":36,
    "Supernatural":37,"Sobrenatural":37,"Mystery":7,"Mistério":7,
}

class DashboardTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._s  = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._s.pack(fill="both", expand=True, padx=14, pady=10)

    def refresh(self):
        for w in self._s.winfo_children():
            w.destroy()
        an = self.app.animes
        total   = len(an)
        watch   = sum(1 for a in an if a.get("status")=="Assistindo")
        plan    = sum(1 for a in an if a.get("status")=="Planejo Assistir")
        done    = sum(1 for a in an if a.get("status")=="Concluído")
        favs    = sum(1 for a in an if a.get("favorito"))
        scored  = [a["score"] for a in an if a.get("score",0)>0]
        avg     = round(sum(scored)/len(scored),1) if scored else 0.0
        hours   = round(sum(a.get("eps_watched",0) for a in an)*24/60,1)

        ctk.CTkLabel(self._s, text="📊  Dashboard",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=TM.T("text"), anchor="w").pack(fill="x", pady=(4,12))

        # Chips
        cr = ctk.CTkFrame(self._s, fg_color="transparent")
        cr.pack(fill="x", pady=(0,16))
        for ico,val,lbl,col in [
            ("🎬",str(total),"Total",TM.accent()),
            ("✅",str(done),"Concluídos",TM.T("green")),
            ("▶",str(watch),"Assistindo","#5588ff"),
            ("⭐",str(favs),"Favoritos",TM.T("yellow")),
            ("★",f"{avg:.1f}","Nota Média",TM.T("yellow")),
            ("⏱",f"{hours}h","Horas",TM.accent()),
        ]:
            chip = ctk.CTkFrame(cr, fg_color=TM.C("bg2"), corner_radius=12,
                                border_width=1, border_color=TM.C("border"))
            chip.pack(side="left", padx=4, fill="y")
            ctk.CTkLabel(chip, text=ico, font=ctk.CTkFont(size=20)).pack(pady=(10,0),padx=18)
            ctk.CTkLabel(chip, text=val, font=ctk.CTkFont(size=22,weight="bold"),
                         text_color=col).pack(padx=18)
            ctk.CTkLabel(chip, text=lbl, font=ctk.CTkFont(size=10),
                         text_color=TM.T("muted")).pack(padx=18,pady=(0,10))

        # Progresso
        self._sec("PROGRESSO GERAL")
        pf = ctk.CTkFrame(self._s, fg_color=TM.C("bg2"), corner_radius=10)
        pf.pack(fill="x", pady=(0,16))
        for lbl,cnt,col in [("Concluídos",done,TM.C("green")),
                             ("Assistindo",watch,TM.accent()),
                             ("Planejados",plan,"#5588ff")]:
            pct = cnt/total if total else 0
            r   = ctk.CTkFrame(pf, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(r, text=f"{lbl} ({cnt})", width=180,
                         font=ctk.CTkFont(size=12),
                         text_color=TM.T("text"), anchor="w").pack(side="left")
            bar = ctk.CTkProgressBar(r, height=8, corner_radius=4,
                                     progress_color=col, fg_color=TM.C("bg0"))
            bar.set(pct)
            bar.pack(side="left", fill="x", expand=True, padx=(8,12))
            ctk.CTkLabel(r, text=f"{pct*100:.0f}%", width=36,
                         font=ctk.CTkFont(size=11),
                         text_color=TM.T("dim")).pack(side="left")

        # Top Favoritos
        top = sorted([a for a in an if a.get("favorito")],
                     key=lambda x:-x.get("score",0))[:5]
        if top:
            self._sec("⭐  TOP FAVORITOS")
            ff = ctk.CTkFrame(self._s, fg_color=TM.C("bg2"), corner_radius=10)
            ff.pack(fill="x", pady=(0,16))
            for a in top:
                r = ctk.CTkFrame(ff, fg_color="transparent")
                r.pack(fill="x", padx=16, pady=4)
                ctk.CTkLabel(r, text=f"⭐  {a['title']}",
                             font=ctk.CTkFont(size=12),
                             text_color=TM.T("text"), anchor="w").pack(side="left")
                ctk.CTkLabel(r, text=f"★ {a.get('score',0):.1f}",
                             font=ctk.CTkFont(size=12),
                             text_color=TM.T("yellow"), anchor="e").pack(side="right")

        # Recomendações
        self._sec("🤖  RECOMENDAÇÕES INTELIGENTES")
        self._rb = ctk.CTkFrame(self._s, fg_color=TM.C("bg2"), corner_radius=10)
        self._rb.pack(fill="x", pady=(0,10))
        if not REQUESTS_OK:
            ctk.CTkLabel(self._rb,
                         text="⚠  pip install requests para recomendações",
                         text_color=TM.T("muted")).pack(pady=14)
            return
        self._rl = ctk.CTkLabel(self._rb, text="⏳  Buscando recomendações...",
                                text_color=TM.accent())
        self._rl.pack(pady=14)
        threading.Thread(target=self._load_recs, daemon=True).start()

    def _sec(self, text):
        ctk.CTkLabel(self._s, text=text, font=ctk.CTkFont(size=11),
                     text_color=TM.T("muted"), anchor="w").pack(fill="x", pady=(6,4))

    def _load_recs(self):
        from collections import Counter
        fg = []
        for a in self.app.animes:
            if a.get("favorito") and a.get("genre"):
                fg += [g.strip() for g in a["genre"].split(",")]
        common = Counter(fg).most_common(3) if fg else []
        ids    = [str(_GENRE_IDS[g]) for g,_ in common if g in _GENRE_IDS]
        recs   = jikan_recs(",".join(ids) if ids else "1")
        self.after(0, lambda: self._show_recs(recs))

    def _show_recs(self, recs):
        try: self._rl.destroy()
        except: pass
        if not recs:
            ctk.CTkLabel(self._rb, text="Sem recomendações no momento.",
                         text_color=TM.T("muted")).pack(pady=12)
            return
        ctk.CTkLabel(self._rb,
                     text="  Baseado nos seus favoritos via Jikan / MyAnimeList",
                     font=ctk.CTkFont(size=10),
                     text_color=TM.T("muted"), anchor="w").pack(fill="x",padx=14,pady=(8,4))
        for r in recs:
            row = ctk.CTkFrame(self._rb, fg_color=TM.C("bg0"), corner_radius=8)
            row.pack(fill="x", padx=10, pady=4)
            ctk.CTkLabel(row, text=r["title"],
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=TM.T("text"), anchor="w").pack(side="left",padx=12,pady=8)
            ctk.CTkLabel(row, text=f"★ {r['score']:.1f}",
                         font=ctk.CTkFont(size=12),
                         text_color=TM.T("yellow"), anchor="e").pack(side="right",padx=12)
        ctk.CTkFrame(self._rb, height=8, fg_color="transparent").pack()

# ══════════════════════════════════════════════════════════════════════════════
#  ABA — CONFIGURAÇÕES
# ══════════════════════════════════════════════════════════════════════════════
class ConfigTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        s = ctk.CTkScrollableFrame(self, fg_color="transparent")
        s.pack(fill="both", expand=True, padx=22, pady=14)

        ctk.CTkLabel(s, text="⚙️  Configurações",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=TM.T("text"), anchor="w").pack(fill="x", pady=(0,18))

        # ── Aparência ─────────────────────────────────────────────────────────
        self._sec(s, "🎨  APARÊNCIA")

        mf = ctk.CTkFrame(s, fg_color=TM.C("bg2"), corner_radius=10)
        mf.pack(fill="x", pady=(0,8))
        ctk.CTkLabel(mf, text="Modo",
                     font=ctk.CTkFont(size=13),
                     text_color=TM.T("text"), anchor="w").pack(side="left",padx=16,pady=12)
        ctk.CTkSegmentedButton(
            mf, values=["Dark","Light"],
            variable=ctk.StringVar(value=TM.mode.capitalize()),
            command=self._ch_mode,
            fg_color=TM.C("bg0"),
            selected_color=TM.accent(),
            selected_hover_color=TM.hover(),
        ).pack(side="right", padx=16, pady=12)

        tf = ctk.CTkFrame(s, fg_color=TM.C("bg2"), corner_radius=10)
        tf.pack(fill="x", pady=(0,6))
        ctk.CTkLabel(tf, text="Cor de acento",
                     font=ctk.CTkFont(size=13),
                     text_color=TM.T("text"), anchor="w").pack(side="left",padx=16,pady=12)
        ctk.CTkSegmentedButton(
            tf, values=list(ACCENT_PRESETS.keys()),
            variable=ctk.StringVar(value=TM.preset),
            command=self._ch_theme,
            fg_color=TM.C("bg0"),
            selected_color=TM.accent(),
            selected_hover_color=TM.hover(),
        ).pack(side="right", padx=16, pady=12)

        ctk.CTkFrame(s, height=6, corner_radius=3,
                     fg_color=TM.accent()).pack(fill="x", pady=(0,20))

        # ── Dados ─────────────────────────────────────────────────────────────
        self._sec(s, "💾  DADOS")
        df = ctk.CTkFrame(s, fg_color=TM.C("bg2"), corner_radius=10)
        df.pack(fill="x", pady=(0,18))

        def _open_folder():
            if sys.platform == "win32":
                os.startfile(BASE_DIR)
            else:
                os.system(f"open '{BASE_DIR}' 2>/dev/null || xdg-open '{BASE_DIR}' 2>/dev/null")

        for lbl, desc, cmd in [
            ("Exportar Backup","Cópia datada de animes.json",export_backup),
            ("Abrir pasta","Pasta onde os dados ficam salvos",_open_folder),
        ]:
            r = ctk.CTkFrame(df, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=8)
            ctk.CTkLabel(r, text=lbl, font=ctk.CTkFont(size=13),
                         text_color=TM.T("text"), anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=desc, font=ctk.CTkFont(size=10),
                         text_color=TM.T("muted"), anchor="w").pack(side="left",padx=8)
            ctk.CTkButton(r, text="→", width=34, height=26, corner_radius=6,
                          fg_color=TM.accent(), hover_color=TM.hover(),
                          command=cmd).pack(side="right")

        # ── Changelog ─────────────────────────────────────────────────────────
        self._sec(s, "📋  NOTAS DA VERSÃO")
        clf = ctk.CTkFrame(s, fg_color=TM.C("bg2"), corner_radius=10)
        clf.pack(fill="x", pady=(0,18))
        for ver, lines in CHANGELOG.items():
            is_cur = (ver == CURRENT_VERSION)
            hf = ctk.CTkFrame(clf,
                              fg_color=TM.dark() if is_cur else "transparent",
                              corner_radius=6)
            hf.pack(fill="x", padx=10, pady=(8,2))
            ctk.CTkLabel(hf,
                         text=f"v{ver}{'  ◀ atual' if is_cur else ''}",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=TM.accent() if is_cur else TM.T("dim"),
                         anchor="w").pack(padx=10, pady=4)
            for line in lines:
                ctk.CTkLabel(clf, text=f"  {line}", anchor="w",
                             font=ctk.CTkFont(size=11),
                             text_color=TM.T("text"),
                             wraplength=580).pack(fill="x", padx=16, pady=1)
            ctk.CTkFrame(clf, height=1, fg_color=TM.C("border")).pack(fill="x",padx=14,pady=4)

        # ── Sobre ─────────────────────────────────────────────────────────────
        self._sec(s, "ℹ️  SOBRE")
        af = ctk.CTkFrame(s, fg_color=TM.C("bg2"), corner_radius=10)
        af.pack(fill="x")
        for txt, col, bold in [
            (f"✦ Anime Tracker Pro  v{CURRENT_VERSION}", TM.accent(), True),
            ("Interface: CustomTkinter  |  Imagens: Pillow  |  Rede: Requests",
             TM.T("text"), False),
            ("", TM.T("muted"), False),
            ("📡 Dados de anime fornecidos por Jikan API", TM.T("dim"), False),
            ("  api.jikan.moe — wrapper open-source não-oficial do MyAnimeList",
             TM.T("muted"), False),
            ("", TM.T("muted"), False),
            ("🔒 Seus dados ficam 100% offline no animes.json local.", TM.T("dim"), False),
            ("  Nenhuma informação pessoal é enviada a servidores externos.",
             TM.T("muted"), False),
        ]:
            ctk.CTkLabel(af, text=txt,
                         font=ctk.CTkFont(size=13, weight="bold" if bold else "normal"),
                         text_color=col, anchor="w").pack(
                         anchor="w", padx=16, pady=(10,0) if bold else (1,0))
        ctk.CTkFrame(af, height=14, fg_color="transparent").pack()

    def _sec(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=11),
                     text_color=TM.T("muted"), anchor="w").pack(fill="x", pady=(4,5))

    def _ch_mode(self, val):
        TM.set_mode(val.lower())
        self.app.apply_theme()

    def _ch_theme(self, val):
        TM.set_preset(val)
        self.app.apply_theme()

# ══════════════════════════════════════════════════════════════════════════════
#  APLICAÇÃO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
class AnimeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"✦ Anime Tracker Pro  v{CURRENT_VERSION}")
        self.geometry("1180x750")
        self.minsize(940,570)
        self.animes = load_data()
        backup_on_startup()
        self._build_layout()
        self._post_startup()

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Topbar
        topbar = ctk.CTkFrame(self, height=54, fg_color=TM.C("bg0"), corner_radius=0)
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_propagate(False)
        ctk.CTkLabel(topbar,
                     text=f"  ✦  ANIME TRACKER PRO  v{CURRENT_VERSION}",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=TM.accent()).pack(side="left", padx=16)
        self._sf = ctk.CTkFrame(topbar, fg_color="transparent")
        self._sf.pack(side="right", padx=16)
        self._rebuild_stats()

        # Tabs
        self._tabs = ctk.CTkTabview(
            self, corner_radius=0,
            fg_color=TM.C("bg1"),
            segmented_button_fg_color=TM.C("bg0"),
            segmented_button_selected_color=TM.accent(),
            segmented_button_selected_hover_color=TM.hover(),
            segmented_button_unselected_color=TM.C("bg0"),
            segmented_button_unselected_hover_color=TM.C("bg2"))
        self._tabs.grid(row=1, column=0, sticky="nsew")
        for name in ["🏠  Minha Lista","📊  Dashboard","⚙️  Configurações"]:
            self._tabs.add(name)

        self.lista_tab  = ListaTab(self._tabs.tab("🏠  Minha Lista"), self)
        self.lista_tab.pack(fill="both", expand=True)
        self.dash_tab   = DashboardTab(self._tabs.tab("📊  Dashboard"), self)
        self.dash_tab.pack(fill="both", expand=True)
        self.config_tab = ConfigTab(self._tabs.tab("⚙️  Configurações"), self)
        self.config_tab.pack(fill="both", expand=True)

        self._tabs.configure(command=self._on_tab)
        self.lista_tab.refresh()

    def _on_tab(self):
        if "Dashboard" in self._tabs.get():
            self.dash_tab.refresh()

    def _rebuild_stats(self):
        for w in self._sf.winfo_children():
            w.destroy()
        for ico,val,col in [
            ("🎬",len(self.animes),                                             TM.T("text")),
            ("▶", sum(1 for a in self.animes if a.get("status")=="Assistindo"), TM.accent()),
            ("⭐",sum(1 for a in self.animes if a.get("favorito")),             TM.T("yellow")),
            ("✅",sum(1 for a in self.animes if a.get("status")=="Concluído"),  TM.T("green")),
        ]:
            f = ctk.CTkFrame(self._sf, fg_color=TM.C("bg2"),
                             corner_radius=8, border_width=1, border_color=TM.C("border"))
            f.pack(side="left", padx=3)
            ctk.CTkLabel(f, text=f"{ico} {val}",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=col).pack(padx=10, pady=5)

    def _post_startup(self):
        if is_first_run():
            mark_version_seen()
            self.after(700, lambda: WhatsNewModal(self))
        if REQUESTS_OK:
            threading.Thread(target=self._bg_update, daemon=True).start()

    def _bg_update(self):
        info = check_for_updates()
        if info:
            self.after(0, lambda: self.lista_tab.show_update_banner(info))

    # ── Callbacks ────────────────────────────────────────────────────────────
    def open_add_modal(self):
        AnimeFormModal(self, on_save=self._add)

    def open_edit_modal(self, idx):
        AnimeFormModal(self, on_save=lambda d: self._edit(idx, d),
                       anime=self.animes[idx])

    def delete_anime(self, idx):
        name = self.animes[idx].get("title","este anime")
        if messagebox.askyesno("Confirmar", f'Deletar "{name}"?'):
            self.animes.pop(idx)
            save_data(self.animes)
            self._refresh_all()

    def update_eps(self, idx, delta):
        a = self.animes[idx]
        w = max(0, a.get("eps_watched",0) + delta)
        t = a.get("eps_total",0)
        if t and w > t: w = t
        self.animes[idx]["eps_watched"] = w
        if t and w == t and self.animes[idx].get("status") != "Concluído":
            self.animes[idx]["status"]         = "Concluído"
            self.animes[idx]["data_conclusao"] = today_str()
        save_data(self.animes)
        self._refresh_all()

    def toggle_fav(self, idx):
        self.animes[idx]["favorito"] = not self.animes[idx].get("favorito",False)
        save_data(self.animes)
        self._refresh_all()

    def _add(self, data):
        self.animes.append(data)
        save_data(self.animes)
        self._refresh_all()

    def _edit(self, idx, data):
        self.animes[idx] = data
        save_data(self.animes)
        self._refresh_all()

    def _refresh_all(self):
        self._rebuild_stats()
        self.lista_tab.refresh()

    def apply_theme(self):
        """Rebuild completo → todas as cores atualizadas."""
        for w in self.winfo_children():
            w.destroy()
        self._build_layout()

# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not REQUESTS_OK:
        print("⚠  Para busca e capas: pip install pillow requests")
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    AnimeApp().mainloop()
