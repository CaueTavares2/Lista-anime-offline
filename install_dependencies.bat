@echo off
echo ========================================
echo   Anime Manager - Instalador
echo ========================================
echo.
echo Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado!
    echo Baixe em: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python encontrado. Instalando dependencias...
echo.
pip install --upgrade pip
pip install customtkinter
pip install pillow
pip install requests

echo.
echo ========================================
echo   Instalacao concluida!
echo   Execute: python anime_manager.py
echo ========================================
pause
