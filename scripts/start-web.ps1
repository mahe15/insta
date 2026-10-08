param(
    [Alias('Host')]
    [string]$HostName = '0.0.0.0',
    [int]$Port = 8788,
    [switch]$NoEngine,
    [switch]$NoOpen
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath 'frontend\dist\index.html')) {
    throw 'Run .\scripts\setup-web.ps1 first to install and build Studio.'
}

# Never terminate an unrelated application that happens to use this port.
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($busy) {
    throw "Port $Port is already in use. Open http://127.0.0.1:$Port if Studio is running, or choose another -Port."
}

$wifiIp = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "*Wi-Fi*" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty IPAddress -First 1)
if (-not $wifiIp) {
    $wifiIp = (Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -ExpandProperty IPAddress -First 1)
}
if ($wifiIp -and ($HostName -eq '0.0.0.0' -or $HostName -eq $wifiIp)) {
    Write-Host "Studio Wi-Fi access: http://${wifiIp}:$Port" -ForegroundColor Cyan
}

$webArgs = @('-m', 'cliper', 'web', '--host', "$HostName", '--port', "$Port")
if ($NoEngine) { $webArgs += '--no-engine' }
if (-not $NoOpen) { $webArgs += '--open' }
& $python @webArgs
if ($LASTEXITCODE -ne 0) { throw 'The Studio server stopped with an error. Check the message above.' }

