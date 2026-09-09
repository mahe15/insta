$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (Test-Path -LiteralPath '.\.venv\Scripts\python.exe') {
    & '.\.venv\Scripts\python.exe' -m cliper bot @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python -m cliper bot @args
} else {
    py -3.12 -m cliper bot @args
}
exit $LASTEXITCODE
