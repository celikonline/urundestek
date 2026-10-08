$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path -LiteralPath '.venv/Scripts/python.exe')) { python -m venv .venv }
& .venv/Scripts/python.exe -m pip install -r backend/requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python bağımlılıkları kurulamadı.' }
if (!(Test-Path -LiteralPath 'frontend/node_modules')) { npm ci --prefix frontend --no-audit --no-fund }
if ($LASTEXITCODE -ne 0) { throw 'React bağımlılıkları kurulamadı.' }
$env:APP_ENV = 'development'
$env:COOKIE_SECURE = 'false'
$env:PUBLIC_URL = 'http://localhost:5173'
$env:PYTHONPATH = Join-Path $PSScriptRoot 'backend'
& .venv/Scripts/python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Veritabanı hazırlanamadı.' }
$apiProcess = Start-Process -FilePath (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--no-access-log') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
Write-Host 'SenseİK Destek: http://localhost:5173 — durdurmak için Ctrl+C'
try { npm run dev --prefix frontend } finally { if (!$apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id } }
