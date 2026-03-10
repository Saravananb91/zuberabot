# Set environment paths
$env:PYTHONPATH = "."
$env:PYTHONIOENCODING = "utf-8"

# Load variables from .env file if it exists
if (Test-Path .env) {
    Write-Host "Loading environment variables from .env file..." -ForegroundColor Cyan
    Get-Content .env | Where-Object { 
        # Ignore empty lines and comments
        $_ -match "\S" -and $_ -notmatch "^\s*#" -and $_ -match "=" 
    } | ForEach-Object {
        $name, $value = $_.Split('=', 2)
        $name = $name.Trim()
        $value = $value.Trim().Trim('"').Trim("'")
        
        # Only set if it has a value
        if ($name) {
            [Environment]::SetEnvironmentVariable($name, $value)
        }
    }
}

Write-Host "Starting Zuberabot API Server via Uvicorn..." -ForegroundColor Green
Write-Host "API will be accessible at http://localhost:8000" -ForegroundColor Cyan
Write-Host "Auto-docs at http://localhost:8000/docs" -ForegroundColor Yellow

# Start the uvicorn server in reload mode for easier testing
uvicorn zuberabot.api.server:app --host 0.0.0.0 --port 8000 --reload
