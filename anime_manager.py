# ═══════════════════════════════════════════════════════════════════════════════
#  ✦  Anime Tracker Pro  v2.2.0
#  Dependências: pip install customtkinter pillow requests
#  Dados: Jikan API (MyAnimeList) — https://jikan.moe
# ═══════════════════════════════════════════════════════════════════════════════
import customtkinter as ctk
import json, os, sys, shutil, threading, io, random, time, re, webbrowser
from datetime import datetime
from tkinter import messagebox, filedialog

try:
    import requests
    from PIL import Image
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTES DE VERSÃO E GITHUB
# ══════════════════════════════════════════════════════════════════════════════
CURRENT_VERSION = "2.2.0"
GITHUB_REPO     = "seu-usuario/anime-tracker-pro"   # ← altere para seu repo
GITHUB_API_URL  = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_REL_URL  = f"https://github.com/{GITHUB_REPO}/releases/latest"

CHANGELOG = {
    "2.2.0": [
        "🔧 FIX: Resultados da Jikan exibidos em ScrollableFrame dentro do modal",
        "🔧 FIX: UI atualizada corretamente na main thread após busca em background",
        "🔧 FIX: Temas aplicam accent color em TODOS os widgets em tempo real",
        "➕ Botão 'Modo Manual' no modal — desbloqueia campos sem depender da API",
        "🔧 FIX: App não trava sem internet — fallback gracioso em toda chamada de rede",
        "🔄 Migração silenciosa: campos novos adicionados sem apagar dados antigos",
        "📋 Changelog completo na aba Configurações",
        "🎉 Popup de novidades no primeiro login de cada versão",
        "🔔 Banner discreto de atualização disponível (via GitHub Releases)",
    ],
    "2.1.0": [
        "✨ Auto-Update: verificação automática de novas versões no GitHub",
        "🔄 Migração de dados entre versões sem perda de informação",
        "📋 Notas da Versão na aba Configurações",
        "🎉 Popup de boas-vindas ao rodar uma versão nova",
        "🌐 Graceful offline: app funciona sem internet",
    ],
    "2.0.0": [
        "🗂 Navegação por abas: Minha Lista, Dashboard, Configurações",
        "📊 Dashboard com estatísticas e recomendações inteligentes",
        "🎨 Temas dinâmicos: Azul, Laranja, Vermelho + Dark/Light",
        "🔍 Modal de busca one-click com preenchimento automático",
        "📝 Notas pessoais por anime",
    ],
    "1.x": [
        "🎌 CRUD completo, busca, filtros, favoritos, capas via Jikan",
        "💾 Backup automático, datas, progresso de episódios",
    ],
}

# ══════════════════════════════════════════════════════════════════════════════
#  PORTABILIDADE — caminhos relativos ao executável
# ══════════════════════════════════════════════════════════════════════════════
def _base_dir() -> str:
    if getattr(sys, "frozen", False):          # rodando como .exe (PyInstaller)
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR    = _base_dir()
DATA_FILE   = os.path.join(BASE_DIR, "animes.json")
BACKUP_FILE = os.path.join(BASE_DIR, "animes_backup.json")
META_FILE   = os.path.join(BASE_DIR, ".app_meta.json")
COVERS_DIR  = os.path.join(BASE_DIR, "assets", "covers")
os.makedirs(COVERS_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
#  SCHEMA DE MIGRAÇÃO — campos obrigatórios com valores padrão
# ══════════════════════════════════════════════════════════════════════════════
ANIME_SCHEMA = {
    "title":         "",
    "genre":         "Não definido",
    "score":         0.0,
    "eps_watched":   0,
    "eps_total":     0,
    "status":        "Planejo Assistir",
    "cover_url":     "",
    "note":          "",
    "favorito":      False,
    "data_adicao":   "",
    "data_conclusao": None,
    "mal_id":        None,
}

# ══════════════════════════════════════════════════════════════════════════════
#  SISTEMA DE TEMAS — singleton com paleta dual dark/light
# ══════════════════════════════════════════════════════════════════════════════
ACCENT_PRESETS = {
    "Azul":     {"accent": "#3b8ed0", "hover": "#2a7abf", "dark": "#163a5e"},
    "Laranja":  {"accent": "#ff9500", "hover": "#e08400", "dark": "#5e3800"},
    "Vermelho": {"accent": "#e84040", "hover": "#cc2020", "dark": "#5e1010"},
}

_DARK_PALETTE = {
    "bg0": "#07070e", "bg1": "#0d0d1a", "bg2": "#12122a",
    "bg3": "#1a1a36", "bg_card": "#141426", "bg_fav": "#16102a",
    "border": "#1e1e3a", "border_fav": "#7744cc",
    "green": "#2ea043", "yellow": "#f0b429", "red": "#e84040",
    "muted": "#50507a", "dim": "#8080a8", "text": "#dde4ff",
}
_LIGHT_PALETTE = {
    "bg0": "#d4daf0", "bg1": "#e6eafa", "bg2": "#eef1fc",
    "bg3": "#d8e0f4", "bg_card": "#f2f4fe", "bg_fav": "#ede6fc",
    "border": "#bcc8e8", "border_fav": "#7744cc",
    "green": "#1a6e2a", "yellow": "#a06000", "red": "#cc2020",
    "muted": "#8090b8", "dim": "#5060a0", "text": "#1a1a3a",
}

class _ThemeManager:
    """
    Singleton. Guarda modo (dark/light) e preset de acento (Azul/Laranja/Vermelho).
    Fornece helpers accent(), hover(), dark(), C(key) para toda a UI.
    """
    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst              = super().__new__(cls)
            cls._inst._mode        = "dark"
            cls._inst._preset_name = "Azul"
        return cls._inst

    # ── getters ──
    @property
    def mode(self):  return self._mode
    @property
    def preset(self): return self._preset_name

    def accent(self)  -> str: return ACCENT_PRESETS[self._preset_name]["accent"]
    def hover(self)   -> str: return ACCENT_PRESETS[self._preset_name]["hover"]
    def dark(self)    -> str: return ACCENT_PRESETS[self._preset_name]["dark"]

    def C(self, key: str) -> str:
        p = _DARK_PALETTE if self._mode == "dark" else _LIGHT_PALETTE
        return p.get(key, "#ff00ff")   # magenta = bug indicator

    # ── setters ──
    def set_mode(self, mode: str):
        self._mode = mode.lower()
        ctk.set_appearance_mode(self._mode)

    def set_preset(self, name: str):
        if name in ACCENT_PRESETS:
            self._preset_name = name

TM = _ThemeManager()

# ── Frases motivacionais ──────────────────────────────────────────────────────
_PHRASES = [
    "O que vamos assistir hoje? 🍿",
    "Sua próxima aventura te espera ✨",
    "Qual história vai te conquistar? 🌸",
    "Anime bom nunca é demais 🎌",
    "O próximo clássico está logo ali 🏆",
]

# ══════════════════════════════════════════════════════════════════════════════
#  PERSISTÊNCIA
# ══════════════════════════════════════════════════════════════════════════════
def _migrate(anime: dict) -> tuple[dict, bool]:
    """Adiciona campos ausentes com valor padrão. Nunca remove campos existentes."""
    changed = False
    for field, default in ANIME_SCHEMA.items():
        if field not in anime:
            anime[field] = default
            changed = True
    return anime, changed

def load_data() -> list:
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            raw = json.load(f)
        except Exception:
            return []
    animes, any_migrated = [], False
    for item in raw:
        item, m = _migrate(item)
        if m:
            any_migrated = True
        animes.append(item)
    if any_migrated:
        save_data(animes)          # persiste migração imediatamente
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
        title="Exportar Backup",
        initialfile=f"animes_backup_{today}.json",
        defaultextension=".json",
        filetypes=[("JSON", "*.json")],
    )
    if dest and os.path.exists(DATA_FILE):
        shutil.copy2(DATA_FILE, dest)
        messagebox.showinfo("Backup exportado", f"Salvo em:\n{dest}")

def today_str() -> str:
    return datetime.now().strftime("%d/%m/%Y")

# ══════════════════════════════════════════════════════════════════════════════
#  META — rastreia versão vista pelo usuário
# ══════════════════════════════════════════════════════════════════════════════
def _load_meta() -> dict:
    if os.path.exists(META_FILE):
        try:
            with open(META_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_meta(meta: dict):
    try:
        with open(META_FILE, "w") as f:
            json.dump(meta, f, indent=2)
    except Exception:
        pass

def is_first_run_of_version() -> bool:
    return _load_meta().get("last_version") != CURRENT_VERSION

def mark_version_seen():
    meta = _load_meta()
    meta["last_version"] = CURRENT_VERSION
    _save_meta(meta)

# ══════════════════════════════════════════════════════════════════════════════
#  AUTO-UPDATE
# ══════════════════════════════════════════════════════════════════════════════
def _ver_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in re.sub(r"[^0-9.]", "", v).split(".") if x)
    except Exception:
        return (0,)

def check_for_updates() -> dict | None:
    """
    Retorna {'version':str,'url':str,'notes':str} ou None.
    Nunca levanta exceção.
    """
    if not REQUESTS_OK:
        return None
    try:
        r = requests.get(GITHUB_API_URL, timeout=5,
                         headers={"Accept": "application/vnd.github+json"})
        if r.status_code != 200:
            return None
        data = r.json()
        tag  = data.get("tag_name", "").lstrip("v")
        if _ver_tuple(tag) > _ver_tuple(CURRENT_VERSION):
            return {
                "version": tag,
                "url":     data.get("html_url", GITHUB_REL_URL),
                "notes":   (data.get("body") or "")[:600],
            }
    except Exception:
        pass
    return None

# ══════════════════════════════════════════════════════════════════════════════
#  JIKAN API  (com throttle e fallback gracioso)
# ══════════════════════════════════════════════════════════════════════════════
_LAST_REQ = 0.0
_JIKAN_SEARCH = "https://api.jikan.moe/v4/anime?q={q}&limit=5&sfw=true"
_JIKAN_RECS   = "https://api.jikan.moe/v4/anime?genres={g}&order_by=score&sort=desc&limit=5&sfw=true"

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

def _parse_item(item: dict) -> dict:
    genres_raw = item.get("genres", [])
    return {
        "mal_id":    item.get("mal_id"),
        "title":     item.get("title_english") or item.get("title", ""),
        "title_jp":  item.get("title", ""),
        "genres":    ", ".join(g["name"] for g in genres_raw) if genres_raw else "Não definido",
        "episodes":  item.get("episodes") or 0,
        "cover_url": item.get("images", {}).get("jpg", {}).get("image_url", ""),
        "year":      str(item.get("year") or ""),
        "score":     float(item.get("score") or 0),
    }

def jikan_search(query: str) -> list:
    if not REQUESTS_OK or not query.strip():
        return []
    data = _jikan_get(_JIKAN_SEARCH.format(q=requests.utils.quote(query.strip()))).get("data", [])
    return [_parse_item(i) for i in data[:5]]

def jikan_recommendations(genre_ids: str) -> list:
    if not REQUESTS_OK:
        return []
    data = _jikan_get(_JIKAN_RECS.format(g=genre_ids)).get("data", [])
    return [_parse_item(i) for i in data[:6]]

# ── Image helpers ─────────────────────────────────────────────────────────────
def _download_ctk_image(url: str, size=(80, 112)) -> "ctk.CTkImage | None":
    if not REQUESTS_OK or not url:
        return None
    try:
        raw = requests.get(url, timeout=8).content
        pil = Image.open(io.BytesIO(raw)).convert("RGBA")
        return ctk.CTkImage(light_image=pil, dark_image=pil, size=size)
    except Exception:
        return None

def _placeholder(size=(80, 112)) -> "ctk.CTkImage | None":
    if not REQUESTS_OK:
        return None
    try:
        col = (20, 20, 50, 255) if TM.mode == "dark" else (200, 210, 240, 255)
        pil = Image.new("RGBA", size, color=col)
        return ctk.CTkImage(light_image=pil, dark_image=pil, size=size)
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════════════════════
#  POPUPS  (WhatsNew, UpdateBanner)
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
                     text=f"✨  O que há de novo na v{CURRENT_VERSION}",
                     font=ctk.CTkFont(size=19, weight="bold"),
                     text_color=TM.accent()).pack(pady=(22, 4))
        ctk.CTkLabel(self, text="Obrigado por usar o Anime Tracker Pro!",
                     font=ctk.CTkFont(size=12), text_color=TM.C("dim")).pack()

        ctk.CTkFrame(self, height=1, fg_color=TM.C("border")).pack(fill="x", padx=28, pady=12)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", height=310)
        scroll.pack(fill="x", padx=24, pady=(0, 8))

        notes = CHANGELOG.get(CURRENT_VERSION, [])
        for line in notes:
            f = ctk.CTkFrame(scroll, fg_color=TM.C("bg2"), corner_radius=8)
            f.pack(fill="x", pady=3)
            ctk.CTkLabel(f, text=line, anchor="w",
                         font=ctk.CTkFont(size=12), text_color=TM.C("text"),
                         wraplength=440).pack(fill="x", padx=12, pady=6)

        ctk.CTkButton(self, text="🚀  Começar a usar",
                      height=40, fg_color=TM.accent(), hover_color=TM.hover(),
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self.destroy).pack(pady=(8, 16))


class _UpdateBanner(ctk.CTkFrame):
    def __init__(self, parent, info: dict):
        super().__init__(parent, fg_color="#0f2010",
                         border_width=1, border_color="#2a5020", corner_radius=8)
        self._info = info
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
#  MODAL DE ADIÇÃO / EDIÇÃO  (BUG-FIXED v2.2)
# ══════════════════════════════════════════════════════════════════════════════
class AnimeFormModal(ctk.CTkToplevel):
    """
    FIX v2.2:
    - Resultados exibidos em CTkScrollableFrame (sem overflow)
    - UI atualizada via self.after() na main thread
    - Modo Manual: botão que desbloqueia todos os campos sem API
    - Offline gracioso: API falhando não trava o modal
    """
    def __init__(self, parent, on_save, anime=None):
        super().__init__(parent)
        self.on_save    = on_save
        self.anime      = anime
        self._is_edit   = anime is not None
        self._api_pick  = {}          # dados do resultado selecionado na API
        self._manual    = self._is_edit   # modo manual ativo desde o início se editando
        self.cover_var  = ctk.StringVar(value=(anime or {}).get("cover_url", ""))

        self.title("✦ Editar Anime" if self._is_edit else "✦ Adicionar Anime")
        self.geometry("540x720")
        self.resizable(False, False)
        self.grab_set()
        self.focus()
        self._build()
        if self._is_edit:
            self._fill_fields(anime)

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=TM.C("bg0"), corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr,
                     text="Editar Anime" if self._is_edit else "Adicionar Anime",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(18, 2))
        subtitle = "Edite os campos abaixo" if self._is_edit else \
                   "Busque pelo nome ou use o modo manual"
        ctk.CTkLabel(hdr, text=subtitle,
                     font=ctk.CTkFont(size=11),
                     text_color=TM.C("dim")).pack(pady=(0, 14))

        # ── Busca (somente modo Adicionar) ────────────────────────────────────
        if not self._is_edit:
            search_frame = ctk.CTkFrame(self, fg_color="transparent")
            search_frame.pack(fill="x", padx=24, pady=(10, 0))

            self._search_ent = ctk.CTkEntry(
                search_frame,
                placeholder_text="🔍  Nome do anime...",
                height=40, corner_radius=10,
                border_color=TM.accent(),
            )
            self._search_ent.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self._search_ent.bind("<Return>", lambda _: self._do_search())

            self._search_btn = ctk.CTkButton(
                search_frame, text="Buscar", width=80, height=40,
                fg_color=TM.accent(), hover_color=TM.hover(),
                font=ctk.CTkFont(size=13, weight="bold"),
                command=self._do_search,
            )
            self._search_btn.pack(side="left", padx=(0, 6))

            # Botão Modo Manual
            self._manual_btn = ctk.CTkButton(
                search_frame, text="✏ Manual", width=80, height=40,
                fg_color=TM.C("bg3"), hover_color=TM.C("bg2"),
                font=ctk.CTkFont(size=12),
                command=self._activate_manual,
            )
            self._manual_btn.pack(side="left")

            # Status da busca
            self._status_lbl = ctk.CTkLabel(
                self, text="", font=ctk.CTkFont(size=11),
                text_color=TM.accent(),
            )
            self._status_lbl.pack(anchor="w", padx=24, pady=(4, 0))

            # ── Resultados em CTkScrollableFrame (FIX principal) ──────────────
            self._results_outer = ctk.CTkFrame(
                self, fg_color=TM.C("bg0"),
                border_width=1, border_color=TM.C("border"),
                corner_radius=10,
            )
            # Não empacotado até ter resultados
            self._results_scroll = ctk.CTkScrollableFrame(
                self._results_outer,
                fg_color="transparent",
                height=160,
            )
            self._results_scroll.pack(fill="both", expand=True, padx=4, pady=4)
            self._results_scroll.grid_columnconfigure(0, weight=1)

        # Separador e label de seção
        ctk.CTkFrame(self, height=1, fg_color=TM.C("border")).pack(fill="x", padx=24, pady=(10, 0))
        ctk.CTkLabel(self, text="DETALHES DO ANIME",
                     font=ctk.CTkFont(size=10),
                     text_color=TM.C("muted")).pack(anchor="w", padx=24, pady=(5, 0))

        p = {"padx": 24, "pady": (5, 0)}

        # Campos — bloqueados até busca ou modo manual (só no modo adicionar)
        ctk.CTkLabel(self, text="Título *", anchor="w").pack(fill="x", **p)
        self._title_ent = ctk.CTkEntry(self, placeholder_text="Ex.: Fullmetal Alchemist", height=36)
        self._title_ent.pack(fill="x", **p)

        ctk.CTkLabel(self, text="Gênero", anchor="w").pack(fill="x", **p)
        self._genre_ent = ctk.CTkEntry(self, placeholder_text="Ação, Aventura...", height=36)
        self._genre_ent.pack(fill="x", **p)

        # Linha: Vistos / Total / Nota
        row_num = ctk.CTkFrame(self, fg_color="transparent")
        row_num.pack(fill="x", **p)
        _vcmd = (self.register(lambda s: re.match(r"^\d*\.?\d*$", s) is not None), "%P")
        for attr, lbl, ph in [
            ("_eps_watched", "Ep. Vistos", "0"),
            ("_eps_total",   "Ep. Total",  "12"),
            ("_score",       "Nota (0-10)", "0.0"),
        ]:
            col = ctk.CTkFrame(row_num, fg_color="transparent")
            col.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ctk.CTkLabel(col, text=lbl, anchor="w").pack(fill="x")
            ent = ctk.CTkEntry(col, placeholder_text=ph, height=36,
                               validate="key", validatecommand=_vcmd)
            ent.pack(fill="x")
            setattr(self, attr, ent)

        # Status
        ctk.CTkLabel(self, text="Status", anchor="w").pack(fill="x", **p)
        self._status_var = ctk.StringVar(value="Planejo Assistir")
        self._status_opt = ctk.CTkOptionMenu(
            self,
            values=["Assistindo", "Planejo Assistir", "Concluído"],
            variable=self._status_var, height=36,
            fg_color=TM.C("bg2"),
            button_color=TM.accent(),
            button_hover_color=TM.hover(),
        )
        self._status_opt.pack(fill="x", **p)

        # Nota pessoal
        ctk.CTkLabel(self, text="Nota Pessoal", anchor="w").pack(fill="x", **p)
        self._note_ent = ctk.CTkEntry(
            self, placeholder_text="Comentário rápido...", height=36)
        self._note_ent.pack(fill="x", **p)

        # URL da capa
        ctk.CTkLabel(self, text="URL da Capa", anchor="w").pack(fill="x", **p)
        self._cover_ent = ctk.CTkEntry(
            self, textvariable=self.cover_var,
            placeholder_text="Preenchida automaticamente pela busca",
            height=36, text_color=TM.C("dim"),
        )
        self._cover_ent.pack(fill="x", **p)

        # Salvar
        ctk.CTkButton(
            self, text="💾  Salvar Anime", height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=TM.accent(), hover_color=TM.hover(),
            command=self._save,
        ).pack(fill="x", padx=24, pady=(14, 6))

        if not REQUESTS_OK:
            ctk.CTkLabel(
                self,
                text="⚠  requests/pillow não instalados — use Modo Manual",
                font=ctk.CTkFont(size=10), text_color="#dd8844",
            ).pack(pady=(0, 6))

        # Se modo adicionar, bloqueia campos até API ou Manual
        if not self._is_edit:
            self._set_fields_state("disabled")

    # ── Helpers de estado ─────────────────────────────────────────────────────
    def _set_fields_state(self, state: str):
        """Habilita ou desabilita todos os campos de detalhe."""
        for w in [self._title_ent, self._genre_ent,
                  self._eps_watched, self._eps_total,
                  self._score, self._note_ent, self._cover_ent]:
            w.configure(state=state)
        self._status_opt.configure(state=state)

    def _activate_manual(self):
        """Modo Manual: desbloqueia campos sem depender da API."""
        self._manual = True
        self._set_fields_state("normal")
        self._results_outer.pack_forget()
        if hasattr(self, "_status_lbl"):
            self._status_lbl.configure(
                text="✏  Modo Manual — preencha os campos livremente",
                text_color=TM.C("dim"))

    # ── Busca API ─────────────────────────────────────────────────────────────
    def _do_search(self):
        if not REQUESTS_OK:
            self._activate_manual()
            if hasattr(self, "_status_lbl"):
                self._status_lbl.configure(
                    text="❌  requests não instalado — modo manual ativado",
                    text_color="#dd4444")
            return
        q = self._search_ent.get().strip()
        if not q:
            return
        # UI → estado "buscando"
        self._search_btn.configure(state="disabled", text="⏳")
        if hasattr(self, "_status_lbl"):
            self._status_lbl.configure(
                text="⏳  Buscando em Jikan / MyAnimeList...",
                text_color=TM.accent())
        # Esconde resultados anteriores
        self._results_outer.pack_forget()
        # Limpa scroll de resultados
        for w in self._results_scroll.winfo_children():
            w.destroy()
        # Thread de busca
        threading.Thread(target=self._search_thread, args=(q,), daemon=True).start()

    def _search_thread(self, query: str):
        results = jikan_search(query)   # bloqueia aqui (fora da main thread)
        self.after(0, lambda: self._on_results(results))   # ← FIX: main thread

    def _on_results(self, results: list):
        """Chamado na main thread via self.after()."""
        self._search_btn.configure(state="normal", text="Buscar")
        if not results:
            if hasattr(self, "_status_lbl"):
                self._status_lbl.configure(
                    text="❌  Sem resultados. Tente outro nome ou use Modo Manual.",
                    text_color="#dd4444")
            return

        if hasattr(self, "_status_lbl"):
            self._status_lbl.configure(
                text=f"✅  {len(results)} resultado(s) — clique para selecionar",
                text_color=TM.C("green"))

        # Constrói botões no ScrollableFrame (FIX: sem overflow)
        for i, r in enumerate(results):
            y = f" ({r['year']})" if r.get("year") else ""
            e = f" · {r['episodes']} eps" if r.get("episodes") else ""
            s = f" · ★{r['score']:.1f}" if r.get("score") else ""
            label_top = f"{r['title']}{y}{e}{s}"
            label_sub = r.get("genres", "")

            item_frame = ctk.CTkFrame(
                self._results_scroll,
                fg_color=TM.C("bg2"), corner_radius=8)
            item_frame.pack(fill="x", pady=(0, 4))

            ctk.CTkButton(
                item_frame,
                text=label_top,
                anchor="w", height=32,
                fg_color="transparent",
                hover_color=TM.C("bg3"),
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda res=r: self._pick_result(res),
            ).pack(fill="x", padx=4, pady=(4, 0))

            if label_sub:
                ctk.CTkLabel(
                    item_frame,
                    text=f"  🎭 {label_sub}",
                    font=ctk.CTkFont(size=10),
                    text_color=TM.C("muted"),
                    anchor="w",
                ).pack(fill="x", padx=8, pady=(0, 4))

        # Exibe o container de resultados
        self._results_outer.pack(fill="x", padx=24, pady=(2, 0))

    def _pick_result(self, r: dict):
        """Preenche campos com dados do anime selecionado e habilita edição."""
        self._api_pick = r
        self._results_outer.pack_forget()
        if hasattr(self, "_status_lbl"):
            self._status_lbl.configure(
                text=f"✦  Selecionado: {r['title']}",
                text_color=TM.C("green"))

        # Desbloqueia campos
        self._set_fields_state("normal")

        # Preenche automaticamente
        for ent, val in [
            (self._title_ent, r["title"]),
            (self._genre_ent, r["genres"] or "Não definido"),
            (self._eps_total, str(r["episodes"]) if r.get("episodes") else ""),
        ]:
            ent.delete(0, "end")
            ent.insert(0, val)

        if not self._score.get().strip() and r.get("score"):
            self._score.insert(0, str(r["score"]))
        self.cover_var.set(r.get("cover_url", ""))

    # ── Populate (edição) ─────────────────────────────────────────────────────
    def _fill_fields(self, a: dict):
        for ent, key in [
            (self._title_ent, "title"),
            (self._genre_ent, "genre"),
            (self._score,     "score"),
            (self._eps_watched, "eps_watched"),
            (self._eps_total,   "eps_total"),
            (self._note_ent,    "note"),
        ]:
            ent.insert(0, str(a.get(key, "")))
        self._status_var.set(a.get("status", "Planejo Assistir"))

    # ── Salvar ────────────────────────────────────────────────────────────────
    def _save(self):
        title = self._title_ent.get().strip()
        if not title:
            messagebox.showwarning("Campo obrigatório", "O Título é obrigatório.", parent=self)
            return

        def _si(v, d=0):
            try:    return max(0, int(float(v)))
            except: return d
        def _sf(v, d=0.0):
            try:    return round(max(0.0, min(10.0, float(v))), 1)
            except: return d

        prev   = (self.anime or {}).get("status", "")
        status = self._status_var.get()
        data = {
            "title":         title,
            "genre":         self._genre_ent.get().strip() or "Não definido",
            "score":         _sf(self._score.get()),
            "eps_watched":   _si(self._eps_watched.get()),
            "eps_total":     _si(self._eps_total.get()),
            "status":        status,
            "cover_url":     self.cover_var.get().strip(),
            "note":          self._note_ent.get().strip(),
            "favorito":      (self.anime or {}).get("favorito", False),
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
_STATUS_COLORS = {
    "Assistindo":        "#3d7ef5",
    "Planejo Assistir":  "#5577ee",
    "Concluído":         "#2ea043",
}

class AnimeCard(ctk.CTkFrame):
    def __init__(self, parent, anime: dict, index: int, callbacks: dict):
        fav = anime.get("favorito", False)
        super().__init__(
            parent, corner_radius=12,
            fg_color=TM.C("bg_fav") if fav else TM.C("bg_card"),
            border_width=1,
            border_color=TM.C("border_fav") if fav else TM.C("border"),
        )
        self.anime      = anime
        self.index      = index
        self.cbs        = callbacks
        self._bg_normal = TM.C("bg_fav") if fav else TM.C("bg_card")
        self._cover_ref = None   # evita GC da CTkImage
        self._build()
        self._bind_hover(self)

    def _bind_hover(self, w):
        w.bind("<Enter>", lambda _: self.configure(fg_color=TM.C("bg3")), add="+")
        w.bind("<Leave>", lambda _: self.configure(fg_color=self._bg_normal), add="+")
        for c in w.winfo_children():
            self._bind_hover(c)

    def _build(self):
        a  = self.anime
        sc = _STATUS_COLORS.get(a.get("status", ""), TM.C("muted"))

        # Stripe lateral de status
        ctk.CTkFrame(self, width=4, corner_radius=0, fg_color=sc).pack(side="left", fill="y")

        # ── Capa ──────────────────────────────────────────────────────────────
        thumb = ctk.CTkFrame(self, width=90, fg_color="transparent")
        thumb.pack(side="left", padx=(8, 8), pady=8)
        thumb.pack_propagate(False)

        url = a.get("cover_url", "")
        if url and REQUESTS_OK:
            ph = _placeholder()
            self._img_lbl = ctk.CTkLabel(thumb, image=ph or None, text="" if ph else "🎬",
                                         font=ctk.CTkFont(size=26))
            self._img_lbl.pack(expand=True)
            threading.Thread(target=self._load_cover, args=(url,), daemon=True).start()
        else:
            box = ctk.CTkFrame(thumb, width=82, height=114, corner_radius=8,
                               fg_color=TM.C("bg0"), border_width=1, border_color=TM.C("border"))
            box.pack(expand=True)
            box.pack_propagate(False)
            ctk.CTkLabel(box, text="🎬", font=ctk.CTkFont(size=30)).place(relx=.5, rely=.5, anchor="center")

        # ── Informações centrais ───────────────────────────────────────────────
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, pady=8)

        # Linha título + favorito
        title_row = ctk.CTkFrame(info, fg_color="transparent")
        title_row.pack(fill="x")
        fav_ico = "⭐" if a.get("favorito") else "☆"
        ctk.CTkButton(
            title_row, text=fav_ico, width=24, height=22,
            fg_color="transparent", hover_color=TM.dark(),
            font=ctk.CTkFont(size=14),
            command=lambda: self.cbs["fav"](self.index),
        ).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(
            title_row,
            text=a.get("title", "—"),
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w", wraplength=270,
        ).pack(side="left", fill="x", expand=True)

        # Gênero
        ctk.CTkLabel(
            info, text=f"🎭  {a.get('genre') or '—'}",
            font=ctk.CTkFont(size=11), text_color=TM.C("dim"), anchor="w",
        ).pack(fill="x", pady=(2, 0))

        # Nota + badge de status
        meta_row = ctk.CTkFrame(info, fg_color="transparent")
        meta_row.pack(fill="x", pady=(3, 0))
        score = a.get("score", 0)
        score_col = TM.C("yellow") if score >= 8 else ("#88aaff" if score >= 6 else TM.C("muted"))
        ctk.CTkLabel(
            meta_row, text=f"★ {score:.1f}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=score_col, anchor="w",
        ).pack(side="left")
        ctk.CTkLabel(
            meta_row, text=f"  {a.get('status','—')}  ",
            font=ctk.CTkFont(size=10), text_color=sc,
            fg_color=TM.C("bg0"), corner_radius=5,
        ).pack(side="left", padx=6)

        # Nota pessoal
        if a.get("note", "").strip():
            ctk.CTkLabel(
                info, text=f"💬 {a['note']}",
                font=ctk.CTkFont(size=10), text_color=TM.C("muted"),
                anchor="w", wraplength=260,
            ).pack(fill="x", pady=(2, 0))

        # Datas
        parts = []
        if a.get("data_adicao"):    parts.append(f"📅 {a['data_adicao']}")
        if a.get("data_conclusao"): parts.append(f"✅ {a['data_conclusao']}")
        if parts:
            ctk.CTkLabel(
                info, text="  •  ".join(parts),
                font=ctk.CTkFont(size=10), text_color=TM.C("muted"), anchor="w",
            ).pack(fill="x", pady=(2, 0))

        # ── Controles direita ─────────────────────────────────────────────────
        ctrl = ctk.CTkFrame(self, fg_color="transparent", width=158)
        ctrl.pack(side="right", padx=(0, 12), pady=8)
        ctrl.pack_propagate(False)

        # Editar / Deletar
        action_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        action_row.pack(fill="x")
        ctk.CTkButton(
            action_row, text="✏", width=32, height=28, corner_radius=8,
            fg_color=TM.C("bg0"), hover_color=TM.C("bg3"),
            command=lambda: self.cbs["edit"](self.index),
        ).pack(side="left")
        ctk.CTkButton(
            action_row, text="✕", width=32, height=28, corner_radius=8,
            fg_color="#3a1010", hover_color="#6e1a1a", text_color="#ff7070",
            command=lambda: self.cbs["del"](self.index),
        ).pack(side="left", padx=(6, 0))

        # Contador de episódios
        eps_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        eps_row.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(
            eps_row, text="−", width=28, height=28, corner_radius=6,
            fg_color=TM.C("bg0"), hover_color=TM.C("bg3"),
            command=lambda: self.cbs["eps"](self.index, -1),
        ).pack(side="left")
        watched = a.get("eps_watched", 0)
        total   = a.get("eps_total", 0)
        ctk.CTkLabel(
            eps_row,
            text=f"Ep {watched}/{total}" if total else f"Ep {watched}",
            font=ctk.CTkFont(size=11), width=68,
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            eps_row, text="+", width=28, height=28, corner_radius=6,
            fg_color=TM.dark(), hover_color=TM.accent(),
            command=lambda: self.cbs["eps"](self.index, +1),
        ).pack(side="left")

        # Barra de progresso
        if total:
            prog = ctk.CTkProgressBar(ctrl, height=5, corner_radius=3,
                                      progress_color=sc, fg_color=TM.C("bg0"))
            prog.set(min(watched / total, 1.0))
            prog.pack(fill="x", pady=(6, 0))

    def _load_cover(self, url: str):
        img = _download_ctk_image(url, (82, 114))
        if img:
            self._cover_ref = img
            try:
                self.after(0, lambda: self._img_lbl.configure(image=img, text=""))
            except Exception:
                pass

# ══════════════════════════════════════════════════════════════════════════════
#  ABA — MINHA LISTA
# ══════════════════════════════════════════════════════════════════════════════
class ListaTab(ctk.CTkFrame):
    _FILTERS = ["Todos", "Favoritos", "Assistindo", "Planejo Assistir", "Concluído"]

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app        = app
        self._filter    = ctk.StringVar(value="Todos")
        self._search    = ctk.StringVar()
        self._search.trace_add("write", lambda *_: self.refresh())
        self._build()

    def _build(self):
        # Toolbar
        tb = ctk.CTkFrame(self, fg_color=TM.C("bg0"), corner_radius=10)
        tb.pack(fill="x", padx=14, pady=(10, 8))

        ctk.CTkEntry(
            tb, textvariable=self._search,
            placeholder_text="🔍  Filtrar por nome...",
            height=34, width=220, corner_radius=8,
            border_color=TM.C("border"),
        ).pack(side="left", padx=10, pady=8)

        for f in self._FILTERS:
            ctk.CTkButton(
                tb, text=f, height=28, corner_radius=8, width=0,
                fg_color="transparent", hover_color=TM.dark(),
                font=ctk.CTkFont(size=11),
                command=lambda x=f: self._set_filter(x),
            ).pack(side="left", padx=2, pady=8)

        ctk.CTkButton(
            tb, text="＋  Adicionar", height=30, corner_radius=8,
            fg_color=TM.accent(), hover_color=TM.hover(),
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.app.open_add_modal,
        ).pack(side="right", padx=10, pady=8)

        # Slot para banner de update
        self._banner_slot = ctk.CTkFrame(self, fg_color="transparent")
        self._banner_slot.pack(fill="x", padx=14)

        # Lista scrollável
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self._scroll.grid_columnconfigure(0, weight=1)

    def show_update_banner(self, info: dict):
        for w in self._banner_slot.winfo_children():
            w.destroy()
        _UpdateBanner(self._banner_slot, info).pack(fill="x", pady=(0, 6))

    def _set_filter(self, f: str):
        self._filter.set(f)
        self.refresh()

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        q     = self._search.get().strip().lower()
        filt  = self._filter.get()
        items = []
        for i, a in enumerate(self.app.animes):
            if filt == "Favoritos" and not a.get("favorito"):      continue
            if filt not in ("Todos", "Favoritos") and a.get("status") != filt: continue
            if q and q not in a.get("title", "").lower():          continue
            items.append((i, a))

        # Favoritos no topo
        items.sort(key=lambda x: (not x[1].get("favorito", False),))

        if not items:
            ctk.CTkLabel(
                self._scroll,
                text="Nenhum anime aqui ainda  🌙",
                font=ctk.CTkFont(size=15), text_color=TM.C("muted"),
            ).grid(row=0, column=0, pady=60)
            return

        cbs = {
            "edit": self.app.open_edit_modal,
            "del":  self.app.delete_anime,
            "eps":  self.app.update_eps,
            "fav":  self.app.toggle_fav,
        }
        for pos, (idx, anime) in enumerate(items):
            AnimeCard(self._scroll, anime, idx, cbs).grid(
                row=pos, column=0, sticky="ew", padx=4, pady=5)

# ══════════════════════════════════════════════════════════════════════════════
#  ABA — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
_GENRE_IDS = {
    "Action":1,"Ação":1,"Adventure":2,"Aventura":2,
    "Comedy":4,"Comédia":4,"Drama":8,"Fantasy":10,"Fantasia":10,
    "Horror":14,"Terror":14,"Romance":22,"Sci-Fi":24,
    "Sports":30,"Esportes":30,"Slice of Life":36,
    "Supernatural":37,"Sobrenatural":37,"Mystery":7,"Mistério":7,
}

class DashboardTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=14, pady=10)

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        animes    = self.app.animes
        total     = len(animes)
        watching  = sum(1 for a in animes if a.get("status") == "Assistindo")
        planned   = sum(1 for a in animes if a.get("status") == "Planejo Assistir")
        completed = sum(1 for a in animes if a.get("status") == "Concluído")
        favs      = sum(1 for a in animes if a.get("favorito"))
        scored    = [a["score"] for a in animes if a.get("score", 0) > 0]
        avg       = round(sum(scored) / len(scored), 1) if scored else 0.0
        eps_sum   = sum(a.get("eps_watched", 0) for a in animes)
        hours     = round(eps_sum * 24 / 60, 1)

        # ── Título ──
        ctk.CTkLabel(self._scroll, text="📊  Dashboard",
                     font=ctk.CTkFont(size=22, weight="bold"), anchor="w",
                     ).pack(fill="x", pady=(4, 12))

        # ── Chips de estatísticas ──────────────────────────────────────────────
        chips_row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        chips_row.pack(fill="x", pady=(0, 16))
        for ico, val, lbl, col in [
            ("🎬", str(total),    "Total",      TM.accent()),
            ("✅", str(completed),"Concluídos", TM.C("green")),
            ("▶",  str(watching), "Assistindo", "#5588ff"),
            ("⭐", str(favs),     "Favoritos",  TM.C("yellow")),
            ("★",  f"{avg:.1f}", "Nota Média", TM.C("yellow")),
            ("⏱",  f"{hours}h",  "Horas",      TM.accent()),
        ]:
            chip = ctk.CTkFrame(chips_row, fg_color=TM.C("bg2"), corner_radius=12,
                                border_width=1, border_color=TM.C("border"))
            chip.pack(side="left", padx=4, fill="y")
            ctk.CTkLabel(chip, text=ico, font=ctk.CTkFont(size=20)).pack(pady=(10,0), padx=18)
            ctk.CTkLabel(chip, text=val, font=ctk.CTkFont(size=22, weight="bold"),
                         text_color=col).pack(padx=18)
            ctk.CTkLabel(chip, text=lbl, font=ctk.CTkFont(size=10),
                         text_color=TM.C("muted")).pack(padx=18, pady=(0,10))

        # ── Barras de progresso ───────────────────────────────────────────────
        self._section("PROGRESSO GERAL")
        prog_frame = ctk.CTkFrame(self._scroll, fg_color=TM.C("bg2"), corner_radius=10)
        prog_frame.pack(fill="x", pady=(0, 16))
        for lbl, cnt, col in [("Concluídos", completed, TM.C("green")),
                               ("Assistindo", watching,  TM.accent()),
                               ("Planejados", planned,   "#5588ff")]:
            pct = cnt / total if total else 0
            r   = ctk.CTkFrame(prog_frame, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(r, text=f"{lbl} ({cnt})", width=180,
                         font=ctk.CTkFont(size=12), anchor="w").pack(side="left")
            bar = ctk.CTkProgressBar(r, height=8, corner_radius=4,
                                     progress_color=col, fg_color=TM.C("bg0"))
            bar.set(pct)
            bar.pack(side="left", fill="x", expand=True, padx=(8, 12))
            ctk.CTkLabel(r, text=f"{pct*100:.0f}%", width=36,
                         font=ctk.CTkFont(size=11), text_color=TM.C("dim")).pack(side="left")

        # ── Top Favoritos ─────────────────────────────────────────────────────
        top_favs = sorted([a for a in animes if a.get("favorito")],
                          key=lambda x: -x.get("score", 0))[:5]
        if top_favs:
            self._section("⭐  TOP FAVORITOS")
            ff = ctk.CTkFrame(self._scroll, fg_color=TM.C("bg2"), corner_radius=10)
            ff.pack(fill="x", pady=(0, 16))
            for a in top_favs:
                r = ctk.CTkFrame(ff, fg_color="transparent")
                r.pack(fill="x", padx=16, pady=4)
                ctk.CTkLabel(r, text=f"⭐  {a['title']}",
                             font=ctk.CTkFont(size=12), anchor="w").pack(side="left")
                ctk.CTkLabel(r, text=f"★ {a.get('score',0):.1f}",
                             font=ctk.CTkFont(size=12),
                             text_color=TM.C("yellow"), anchor="e").pack(side="right")

        # ── Recomendações ─────────────────────────────────────────────────────
        self._section("🤖  RECOMENDAÇÕES INTELIGENTES")
        self._rec_box = ctk.CTkFrame(self._scroll, fg_color=TM.C("bg2"), corner_radius=10)
        self._rec_box.pack(fill="x", pady=(0, 10))

        if not REQUESTS_OK:
            ctk.CTkLabel(self._rec_box,
                         text="⚠  pip install requests  para recomendações",
                         text_color=TM.C("muted")).pack(pady=14)
            return

        self._rec_loading = ctk.CTkLabel(self._rec_box,
                                         text="⏳  Buscando recomendações...",
                                         text_color=TM.accent())
        self._rec_loading.pack(pady=14)
        threading.Thread(target=self._load_recs, daemon=True).start()

    def _section(self, text: str):
        ctk.CTkLabel(self._scroll, text=text,
                     font=ctk.CTkFont(size=11), text_color=TM.C("muted"),
                     anchor="w").pack(fill="x", pady=(6, 4))

    def _load_recs(self):
        from collections import Counter
        fav_genres = []
        for a in self.app.animes:
            if a.get("favorito") and a.get("genre"):
                fav_genres += [g.strip() for g in a["genre"].split(",")]
        common     = Counter(fav_genres).most_common(3) if fav_genres else []
        ids        = [str(_GENRE_IDS[g]) for g, _ in common if g in _GENRE_IDS]
        genre_str  = ",".join(ids) if ids else "1"
        recs = jikan_recommendations(genre_str)
        self.after(0, lambda: self._show_recs(recs))

    def _show_recs(self, recs: list):
        try:
            self._rec_loading.destroy()
        except Exception:
            pass
        if not recs:
            ctk.CTkLabel(self._rec_box,
                         text="Nenhuma recomendação no momento.",
                         text_color=TM.C("muted")).pack(pady=12)
            return
        ctk.CTkLabel(self._rec_box,
                     text="  Baseado nos gêneros dos seus favoritos via Jikan / MyAnimeList",
                     font=ctk.CTkFont(size=10), text_color=TM.C("muted"),
                     anchor="w").pack(fill="x", padx=14, pady=(8, 4))
        for r in recs:
            row = ctk.CTkFrame(self._rec_box, fg_color=TM.C("bg0"), corner_radius=8)
            row.pack(fill="x", padx=10, pady=4)
            ctk.CTkLabel(row, text=r["title"],
                         font=ctk.CTkFont(size=12, weight="bold"),
                         anchor="w").pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(row, text=f"★ {r['score']:.1f}",
                         font=ctk.CTkFont(size=12),
                         text_color=TM.C("yellow"), anchor="e").pack(side="right", padx=12)
        ctk.CTkFrame(self._rec_box, height=8, fg_color="transparent").pack()

# ══════════════════════════════════════════════════════════════════════════════
#  ABA — CONFIGURAÇÕES  (FIX: tema aplicado em tempo real via rebuild)
# ══════════════════════════════════════════════════════════════════════════════
class ConfigTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=22, pady=14)

        ctk.CTkLabel(scroll, text="⚙️  Configurações",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     anchor="w").pack(fill="x", pady=(0, 18))

        # ── Aparência ─────────────────────────────────────────────────────────
        self._section(scroll, "🎨  APARÊNCIA")

        # Modo Dark/Light
        mf = ctk.CTkFrame(scroll, fg_color=TM.C("bg2"), corner_radius=10)
        mf.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(mf, text="Modo",
                     font=ctk.CTkFont(size=13), anchor="w").pack(side="left", padx=16, pady=12)
        mode_var = ctk.StringVar(value=TM.mode.capitalize())
        ctk.CTkSegmentedButton(
            mf, values=["Dark", "Light"], variable=mode_var,
            command=lambda v: self._change_mode(v),
            fg_color=TM.C("bg0"),
            selected_color=TM.accent(),
            selected_hover_color=TM.hover(),
        ).pack(side="right", padx=16, pady=12)

        # Tema de cor
        tf = ctk.CTkFrame(scroll, fg_color=TM.C("bg2"), corner_radius=10)
        tf.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(tf, text="Cor de acento",
                     font=ctk.CTkFont(size=13), anchor="w").pack(side="left", padx=16, pady=12)
        theme_var = ctk.StringVar(value=TM.preset)
        ctk.CTkSegmentedButton(
            tf, values=list(ACCENT_PRESETS.keys()), variable=theme_var,
            command=lambda v: self._change_theme(v),
            fg_color=TM.C("bg0"),
            selected_color=TM.accent(),
            selected_hover_color=TM.hover(),
        ).pack(side="right", padx=16, pady=12)

        # Barra prévia de cor
        self._preview = ctk.CTkFrame(scroll, height=6, corner_radius=3,
                                     fg_color=TM.accent())
        self._preview.pack(fill="x", pady=(0, 20))

        # ── Dados ─────────────────────────────────────────────────────────────
        self._section(scroll, "💾  DADOS")
        df = ctk.CTkFrame(scroll, fg_color=TM.C("bg2"), corner_radius=10)
        df.pack(fill="x", pady=(0, 18))

        def _open_folder():
            if sys.platform == "win32":
                os.startfile(BASE_DIR)
            else:
                os.system(f"open '{BASE_DIR}' 2>/dev/null || xdg-open '{BASE_DIR}' 2>/dev/null")

        for lbl, desc, cmd in [
            ("Exportar Backup",  "Cópia datada de animes.json",       export_backup),
            ("Abrir pasta",      f"Onde seus dados ficam salvos",      _open_folder),
        ]:
            r = ctk.CTkFrame(df, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=8)
            ctk.CTkLabel(r, text=lbl, font=ctk.CTkFont(size=13), anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=desc, font=ctk.CTkFont(size=10),
                         text_color=TM.C("muted"), anchor="w").pack(side="left", padx=8)
            ctk.CTkButton(r, text="→", width=34, height=26, corner_radius=6,
                          fg_color=TM.accent(), hover_color=TM.hover(),
                          command=cmd).pack(side="right")

        # ── Notas da Versão (Changelog) ───────────────────────────────────────
        self._section(scroll, "📋  NOTAS DA VERSÃO")
        clf = ctk.CTkFrame(scroll, fg_color=TM.C("bg2"), corner_radius=10)
        clf.pack(fill="x", pady=(0, 18))

        for ver, lines in CHANGELOG.items():
            is_cur = (ver == CURRENT_VERSION)
            hf = ctk.CTkFrame(clf,
                              fg_color=TM.dark() if is_cur else "transparent",
                              corner_radius=6)
            hf.pack(fill="x", padx=10, pady=(8, 2))
            lbl_text = f"v{ver}  ◀ versão atual" if is_cur else f"v{ver}"
            ctk.CTkLabel(hf, text=lbl_text,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=TM.accent() if is_cur else TM.C("dim"),
                         anchor="w").pack(padx=10, pady=4)
            for line in lines:
                ctk.CTkLabel(clf, text=f"  {line}", anchor="w",
                             font=ctk.CTkFont(size=11), text_color=TM.C("text"),
                             wraplength=580).pack(fill="x", padx=16, pady=1)
            ctk.CTkFrame(clf, height=1, fg_color=TM.C("border")).pack(fill="x", padx=14, pady=4)

        # ── Sobre ─────────────────────────────────────────────────────────────
        self._section(scroll, "ℹ️  SOBRE")
        af = ctk.CTkFrame(scroll, fg_color=TM.C("bg2"), corner_radius=10)
        af.pack(fill="x")
        for txt, col, bold in [
            (f"✦ Anime Tracker Pro  v{CURRENT_VERSION}", TM.accent(), True),
            ("Interface: CustomTkinter   |   Imagens: Pillow   |   API: Requests", TM.C("text"), False),
            ("", TM.C("muted"), False),
            ("📡 Dados de anime fornecidos por Jikan API", TM.C("dim"), False),
            ("  api.jikan.moe — wrapper open-source não-oficial do MyAnimeList", TM.C("muted"), False),
            ("", TM.C("muted"), False),
            ("🔒 Seus dados ficam 100% offline no animes.json local.", TM.C("dim"), False),
            ("  Nenhuma informação pessoal é enviada a servidores externos.", TM.C("muted"), False),
        ]:
            ctk.CTkLabel(af, text=txt,
                         font=ctk.CTkFont(size=13, weight="bold" if bold else "normal"),
                         text_color=col, anchor="w").pack(
                         anchor="w", padx=16, pady=(10, 0) if bold else (1, 0))
        ctk.CTkFrame(af, height=14, fg_color="transparent").pack()

    def _section(self, parent, text: str):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=11),
                     text_color=TM.C("muted"), anchor="w").pack(fill="x", pady=(4, 5))

    def _change_mode(self, val: str):
        TM.set_mode(val.lower())
        self.app.apply_theme()          # rebuild completo → cores novas em TUDO

    def _change_theme(self, val: str):
        TM.set_preset(val)
        self.app.apply_theme()          # rebuild completo → accent em TUDO

# ══════════════════════════════════════════════════════════════════════════════
#  APLICAÇÃO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
class AnimeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"✦ Anime Tracker Pro  v{CURRENT_VERSION}")
        self.geometry("1180x750")
        self.minsize(940, 570)
        self.animes = load_data()
        backup_on_startup()
        self._build_layout()
        self._post_startup()

    # ── Layout ────────────────────────────────────────────────────────────────
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

        self._stat_frame = ctk.CTkFrame(topbar, fg_color="transparent")
        self._stat_frame.pack(side="right", padx=16)
        self._rebuild_stats()

        # Tabs
        self._tabs = ctk.CTkTabview(
            self, corner_radius=0,
            fg_color=TM.C("bg1"),
            segmented_button_fg_color=TM.C("bg0"),
            segmented_button_selected_color=TM.accent(),
            segmented_button_selected_hover_color=TM.hover(),
            segmented_button_unselected_color=TM.C("bg0"),
            segmented_button_unselected_hover_color=TM.C("bg2"),
        )
        self._tabs.grid(row=1, column=0, sticky="nsew")

        for name in ["🏠  Minha Lista", "📊  Dashboard", "⚙️  Configurações"]:
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

    # ── Topbar stats ──────────────────────────────────────────────────────────
    def _rebuild_stats(self):
        for w in self._stat_frame.winfo_children():
            w.destroy()
        for ico, val, col in [
            ("🎬", len(self.animes),                                              TM.C("text")),
            ("▶",  sum(1 for a in self.animes if a.get("status") == "Assistindo"), TM.accent()),
            ("⭐", sum(1 for a in self.animes if a.get("favorito")),               TM.C("yellow")),
            ("✅", sum(1 for a in self.animes if a.get("status") == "Concluído"),  TM.C("green")),
        ]:
            f = ctk.CTkFrame(self._stat_frame, fg_color=TM.C("bg2"),
                             corner_radius=8, border_width=1, border_color=TM.C("border"))
            f.pack(side="left", padx=3)
            ctk.CTkLabel(f, text=f"{ico} {val}",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=col).pack(padx=10, pady=5)

    # ── Post-startup ──────────────────────────────────────────────────────────
    def _post_startup(self):
        if is_first_run_of_version():
            mark_version_seen()
            self.after(700, lambda: WhatsNewModal(self))
        if REQUESTS_OK:
            threading.Thread(target=self._bg_update_check, daemon=True).start()

    def _bg_update_check(self):
        info = check_for_updates()
        if info:
            self.after(0, lambda: self.lista_tab.show_update_banner(info))

    # ── Callbacks públicos ────────────────────────────────────────────────────
    def open_add_modal(self):
        AnimeFormModal(self, on_save=self._add_anime)

    def open_edit_modal(self, idx: int):
        AnimeFormModal(self, on_save=lambda d: self._edit_anime(idx, d),
                       anime=self.animes[idx])

    def delete_anime(self, idx: int):
        name = self.animes[idx].get("title", "este anime")
        if messagebox.askyesno("Confirmar exclusão", f'Deletar "{name}"?'):
            self.animes.pop(idx)
            save_data(self.animes)
            self._refresh_all()

    def update_eps(self, idx: int, delta: int):
        a       = self.animes[idx]
        watched = max(0, a.get("eps_watched", 0) + delta)
        total   = a.get("eps_total", 0)
        if total and watched > total:
            watched = total
        self.animes[idx]["eps_watched"] = watched
        if total and watched == total and self.animes[idx].get("status") != "Concluído":
            self.animes[idx]["status"]         = "Concluído"
            self.animes[idx]["data_conclusao"] = today_str()
        save_data(self.animes)
        self._refresh_all()

    def toggle_fav(self, idx: int):
        self.animes[idx]["favorito"] = not self.animes[idx].get("favorito", False)
        save_data(self.animes)
        self._refresh_all()

    def _add_anime(self, data: dict):
        self.animes.append(data)
        save_data(self.animes)
        self._refresh_all()

    def _edit_anime(self, idx: int, data: dict):
        self.animes[idx] = data
        save_data(self.animes)
        self._refresh_all()

    def _refresh_all(self):
        self._rebuild_stats()
        self.lista_tab.refresh()

    def apply_theme(self):
        """
        FIX v2.2: Reconstrói o layout inteiro para que TODOS os widgets
        recebam as novas cores de accent/modo — sem widgets "esquecidos".
        """
        for w in self.winfo_children():
            w.destroy()
        self._build_layout()
        # Não chama _post_startup() de novo para evitar popup duplicado

# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not REQUESTS_OK:
        print("⚠  Para busca e capas:  pip install pillow requests")
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = AnimeApp()
    app.mainloop()
