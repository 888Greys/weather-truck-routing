# Start the API and the web app together (Windows PowerShell).
# Usage:  .\scripts\dev.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "Starting Django on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Start-Process -FilePath "$root\backend\.venv\Scripts\python.exe" `
  -ArgumentList "manage.py", "runserver", "127.0.0.1:8000" `
  -WorkingDirectory "$root\backend"

Start-Sleep -Seconds 3

Write-Host "Starting Vite on http://127.0.0.1:5173 ..." -ForegroundColor Cyan
Set-Location "$root\frontend"
npm run dev
