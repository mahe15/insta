$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& '.\.venv\Scripts\python.exe' -m cliper gemini-login
exit $LASTEXITCODE
