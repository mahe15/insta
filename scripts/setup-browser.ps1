$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& '.\.venv\Scripts\python.exe' -m pip install -e '.[browser]'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$env:PLAYWRIGHT_BROWSERS_PATH = (& '.\.venv\Scripts\python.exe' -c "from cliper.config import Config; import os; Config.load(); print(os.environ.get('PLAYWRIGHT_BROWSERS_PATH'))")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& '.\.venv\Scripts\python.exe' -m playwright install chromium
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'Browser installed. Next run .\scripts\chatgpt-login.ps1, then select /provider chatgpt in Telegram.'
