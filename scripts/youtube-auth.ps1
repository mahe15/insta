param(
    [string]$Account = '',
    [switch]$List
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

if ($List) {
    & '.\.venv\Scripts\python.exe' -m cliper youtube-auth --list
    exit $LASTEXITCODE
}

if ($Account) {
    & '.\.venv\Scripts\python.exe' -m cliper youtube-auth --account $Account
} else {
    & '.\.venv\Scripts\python.exe' -m cliper youtube-auth
}
exit $LASTEXITCODE

