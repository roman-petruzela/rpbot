#!/bin/bash

if [ ! -d ".venv" ]; then
    echo ".venv not found. Creating new..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

echo "Starting bot..."
python3 ./main.py

echo "Bot stopped."
