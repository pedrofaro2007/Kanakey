@echo off
title Kanakey - Yamaha PSR-E473
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    python -m venv .venv
    .venv\Scripts\pip install pygame-ce pynput
)

.venv\Scripts\python.exe kanakey.py
