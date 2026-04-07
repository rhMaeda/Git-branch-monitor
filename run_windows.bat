@echo off
setlocal

if not exist .venv (
    echo Ambiente virtual nao encontrado. Execute install_windows.bat primeiro.
    exit /b 1
)

call .venv\Scripts\activate.bat
python start_server.py
