@echo off
set PYTHONPATH=.
set PYTHONIOENCODING=utf-8

:: Check if .env exists
if exist .env (
    echo Loading environment variables from .env
    for /f "tokens=*" %%a in (.env) do (
        :: Only process lines that aren't comments and contain an equals sign
        echo %%a | findstr /R "^[^#].*=" > nul && set "%%a"
    )
)

echo Starting Zuberabot API Server...
uvicorn zuberabot.api.server:app --host 0.0.0.0 --port 8000 --reload
