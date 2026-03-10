# Nanobot Startup Script - Ollama (Qwen 2.5 3B)
$OutputEncoding = [System.Text.Encoding]::UTF8
[console]::InputEncoding = [console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

Write-Host "Starting Nanobot with Ollama (qwen2.5:3b)..." -ForegroundColor Green

# CRITICAL FIX: The disk is full, so pip install -e . fails.
# However, the site-packages has an unrelated "zuberabot" v0.4.1 robotics package blocking the local code!
# We just delete the wrong package from site-packages to force Python to use your local folder.
if (Test-Path ".\venv\Lib\site-packages\nanobot") {
    Write-Host "Removing conflicting 'zuberabot' package from site-packages..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force ".\venv\Lib\site-packages\nanobot" -ErrorAction SilentlyContinue
}
Remove-Item -Recurse -Force ".\venv\Lib\site-packages\nanobot_ai*.dist-info" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ".\venv\Lib\site-packages\nanobot-*.dist-info" -ErrorAction SilentlyContinue

# Check Ollama is reachable
Write-Host "Checking Ollama server at http://localhost:11434 ..." -ForegroundColor Cyan
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:11434" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    Write-Host "Ollama is running." -ForegroundColor Green
}
catch {
    Write-Host "WARNING: Ollama does not appear to be running on port 11434." -ForegroundColor Red
    Write-Host "Start it with:  ollama serve" -ForegroundColor Yellow
    Write-Host "Pull the model: ollama pull qwen2.5:3b" -ForegroundColor Yellow
    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -ne 'y' -and $continue -ne 'Y') { exit 1 }
}

# Add local directory to PYTHONPATH so it finds the local nanobot folder instead of nothing
$env:PYTHONPATH = (Get-Location).Path

# Start zuberabot
Write-Host "Starting zuberabot gateway (using local code)..." -ForegroundColor Yellow
.\venv\Scripts\python.exe -m zuberabot gateway
