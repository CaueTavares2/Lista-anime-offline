# ✦ Anime Tracker Pro

> Gerencie sua lista de animes com estilo. Busca automática via Jikan API, capas, favoritos, dashboard com estatísticas e muito mais.

![Version](https://img.shields.io/badge/versão-2.2.0-blue)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-purple)
![Jikan](https://img.shields.io/badge/Dados-Jikan%20API-orange)
![License](https://img.shields.io/badge/licença-MIT-green)

---

## 🚀 Funcionalidades

| Recurso | Descrição |
|---|---|
| 🔍 Busca One-Click | Digite o nome, selecione o resultado — título, gênero, episódios e capa preenchidos automaticamente via Jikan API |
| ✏️ Modo Manual | Botão "Manual" no modal desbloqueia todos os campos sem depender da API |
| 🏠 Minha Lista | Cards horizontais com filtros, busca em tempo real e favoritos no topo |
| 📊 Dashboard | Estatísticas completas + Recomendações Inteligentes por gênero (via Jikan) |
| ⚙️ Configurações | Temas Azul / Laranja / Vermelho e modo Dark / Light — aplicados em tempo real |
| 💾 Backup | Backup automático na inicialização + exportação datada manual |
| 📝 Notas Pessoais | Campo de comentário rápido em cada card |
| 🔔 Auto-Update | Verifica novas versões no GitHub e exibe banner discreto |
| 🔄 Migração Silenciosa | Campos novos adicionados automaticamente sem apagar dados antigos |
| 🎉 Popup de Novidades | Mostra o changelog na primeira execução de cada versão |

---

## ⚙️ Instalação

### Método 1 — Script Python (recomendado para desenvolvimento)

```bash
# 1. Instale as dependências
pip install customtkinter pillow requests

# 2. Execute
python anime_manager.py
```

### Método 2 — Windows (instalação automática)

Execute o arquivo `install_dependencies.bat` incluído no pacote.

### Método 3 — Executável (.exe)

Baixe o `.exe` na página de [Releases](../../releases) e execute diretamente.
O arquivo `animes.json` será criado automaticamente na mesma pasta.

---

## 📦 Compilar para .exe (PyInstaller)

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name "AnimeTrackerPro" anime_manager.py
```

O executável estará em `dist/AnimeTrackerPro.exe`.
Copie o `.exe` para uma pasta vazia — o `animes.json` será criado ao lado dele.

---

## 📁 Estrutura de arquivos

```
AnimeTrackerPro/
├── anime_manager.py        ← código principal (único arquivo)
├── animes.json             ← sua lista (criado automaticamente)
├── animes_backup.json      ← backup automático (atualizado na inicialização)
├── .app_meta.json          ← controle de versão interna (não edite)
├── assets/
│   └── covers/             ← pasta de capas (criada automaticamente)
├── README.md
├── .gitignore
└── install_dependencies.bat
```

---

## 🔄 Migração de dados entre versões

O app detecta campos ausentes em registros antigos e os adiciona com valores
padrão **sem apagar nenhum dado existente**. Sua lista da v1.0 funciona
perfeitamente na v2.2 — basta substituir o `.exe` ou o `.py`.

---

## 🔧 Correções v2.2.0

- **FIX**: Resultados da Jikan exibidos em `CTkScrollableFrame` — sem overflow
- **FIX**: UI atualizada na main thread via `self.after()` após busca em background
- **FIX**: Temas aplicam accent color em **todos** os widgets via rebuild completo
- **NOVO**: Botão "Modo Manual" desbloqueia campos sem depender da API
- **NOVO**: App não trava sem internet — fallback gracioso em toda chamada de rede

---

## 📡 Créditos de dados

Os dados de anime (títulos, gêneros, episódios, capas e recomendações) são
fornecidos pela **[Jikan API](https://jikan.moe)**, um wrapper não-oficial
e open-source do [MyAnimeList](https://myanimelist.net).

Seus dados pessoais (`animes.json`) ficam **100% locais** na sua máquina.
Nenhuma informação é enviada a servidores externos.

---

## 📄 Licença

MIT — use, modifique e distribua livremente.
