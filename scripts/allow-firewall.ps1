<#
.SYNOPSIS
    Allows inbound connections to CLIPER Studio (port 8788) through Windows Defender Firewall.
#>
param([int]$Port = 8788)
$ErrorActionPreference = 'Stop'

function Test-Administrator {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    Write-Host "Requesting administrator privileges to update Windows Firewall..." -ForegroundColor Yellow
    $script = $MyInvocation.MyCommand.Path
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Port $Port"
    Start-Process powershell.exe -Verb RunAs -ArgumentList $argList -Wait
    exit
}

$ruleName = "CLIPER Studio (Port $Port)"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

if ($existing) {
    Write-Host "Firewall rule '$ruleName' is already present." -ForegroundColor Green
} else {
    New-NetFirewallRule -DisplayName $ruleName `
        -Direction Inbound `
        -LocalPort $Port `
        -Protocol TCP `
        -Action Allow `
        -Profile Any `
        -Description "Allows access to CLIPER Studio from local network devices over Wi-Fi." | Out-Null
    Write-Host "Successfully added inbound Windows Firewall rule for port $Port." -ForegroundColor Green
}

$wifiIp = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "*Wi-Fi*" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty IPAddress -First 1)
if ($wifiIp) {
    Write-Host "Other devices on your Wi-Fi can now open: http://${wifiIp}:$Port" -ForegroundColor Cyan
}
Write-Host "Press any key to close..."
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
