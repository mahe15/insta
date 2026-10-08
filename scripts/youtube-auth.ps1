param(
    [string]$Account = 'main'
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& '.\.venv\Scripts\python.exe' -m cliper youtube-auth --account $Account
exit $LASTEXITCODE
