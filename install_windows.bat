@echo off
setlocal

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if not exist .env (
    copy .env.example .env >nul
)

echo.
echo Instalacao concluida.
echo 1) Edite o arquivo .env
ECHO 2) Execute run_windows.bat
