$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 and run setup again.' }
}
& $python -m pip install -e '.[web,browser]'
if ($LASTEXITCODE -ne 0) { throw 'Web API dependency installation failed.' }
$node = (Get-Command node -ErrorAction Stop).Source
$npmCli = Join-Path (Split-Path -Parent $node) 'node_modules\npm\bin\npm-cli.js'
if (-not (Test-Path -LiteralPath $npmCli)) { throw 'Install Node.js LTS with npm, then run setup again.' }
Push-Location (Join-Path $projectRoot 'frontend')
try {
    & $node $npmCli ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    & $node $npmCli run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host 'CLIPER Studio is ready. Start it with .\scripts\start-web.ps1'
