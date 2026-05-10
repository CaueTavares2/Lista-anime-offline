# ✦ Anime Manager

> Gerencie sua lista de animes com estilo. Busca automática via Jikan API, capas, favoritos, estatísticas e muito mais.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-purple) ![Jikan](https://img.shields.io/badge/Dados-Jikan%20API-orange)

---

## 🚀 Funcionalidades

| Recurso | Descrição |
|---|---|
| 🔍 Busca One-Click | Digite o nome, selecione o resultado — título, gênero, episódios e capa preenchidos automaticamente |
| 🏠 Minha Lista | Cards horizontais com filtros, favoritos no topo e progresso visual |
| 📊 Dashboard | Estatísticas completas + Recomendações Inteligentes por gênero (via Jikan) |
| ⚙️ Configurações | Temas Azul / Laranja / Vermelho e modo Dark / Light aplicados em tempo real |
| 💾 Backup | Backup automático na inicialização + exportação datada manual |
| 📝 Notas Pessoais | Campo de comentário rápido em cada card |

---

## ⚙️ Instalação

### Método 1 — Script Python
```bash
# 1. Instale as dependências
pip install customtkinter pillow requests

# 2. Execute
python anime_manager.py
```

### Método 2 — Executável (.exe / binário)
Faça o download do `.exe` na página de [Releases](../../releases) e execute diretamente.  
O arquivo `animes.json` será criado automaticamente na mesma pasta.

### Windows — instalação automática
```bat
install_dependencies.bat
```

---

## 📦 Compilar para .exe (PyInstaller)

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name "AnimeManager" anime_manager.py
```

O executável estará em `dist/AnimeManager.exe`.

---

## 📁 Estrutura de arquivos

```
AnimeManager/
├── anime_manager.py       ← código principal
├── animes.json            ← sua lista (criado automaticamente)
├── animes_backup.json     ← backup automático (criado na inicialização)
└── assets/
    └── covers/            ← pasta de capas (criada automaticamente)
```

---

## 📡 Créditos de dados

Os dados de anime (títulos, gêneros, episódios, capas e recomendações) são fornecidos pela **[Jikan API](https://jikan.moe)**, um wrapper não-oficial e open-source do [MyAnimeList](https://myanimelist.net).

---

## 📄 Licença

MIT — use, modifique e distribua livremente.
