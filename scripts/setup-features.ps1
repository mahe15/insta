$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& '.\.venv\Scripts\python.exe' -m pip install -e '.[browser]'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
foreach ($clipConfigName in @('instagram', 'niches')) {
    $clipDestination = Join-Path 'config' ($clipConfigName + '.json')
    if (-not (Test-Path -LiteralPath $clipDestination)) {
        Copy-Item -LiteralPath (Join-Path 'config' ($clipConfigName + '.example.json')) -Destination $clipDestination
    }
}
Write-Host 'Add Instagram account IDs/owners, local token variables, public media URL and per-niche character paths.'
Write-Host 'Run scripts/gemini-login.ps1 once. Restart the bot and use its F1/F2 dashboard buttons.'
