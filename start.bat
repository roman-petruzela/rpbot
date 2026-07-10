@echo off

if not exist .venv (
    echo .venv not found. Creating new...
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

echo Starting bot...
python main.py

echo.
echo Bot stopped.
pause
