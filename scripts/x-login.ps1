$ErrorActionPreference = 'Stop'
$cliperRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $cliperRoot
& "$cliperRoot/.venv/Scripts/python.exe" -m cliper x-login
