#!/bin/bash
set -e

if [ ! -d ".venv" ]; then
    echo ".venv not found. Creating new..."
    if command -v uv &> /dev/null; then
        echo "Using uv for environment setup..."
        uv venv .venv
        source .venv/bin/activate
        uv pip install -r requirements.txt
    else
        echo "Using pip for environment setup..."
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -r requirements.txt
    fi
else
    source .venv/bin/activate
fi

echo "Starting bot..."
python3 ./main.py

echo "Bot stopped."
