@echo off
REM Start Zuberabot Gateway with E: drive Ollama

echo Starting Zuberabot Gateway...

REM Set Ollama location
set OLLAMA_MODELS=E:\ollama\models
set OLLAMA_KEEP_ALIVE=24h

REM Set Python env
set PYTHONIOENCODING=utf-8
set PYTHONPATH=e:\demo projects\zuberaa\zuberabot

REM Start gateway
cd /d "e:\demo projects\zuberaa\zuberabot"
.\venv\Scripts\python.exe -m zuberabot gateway

pause
