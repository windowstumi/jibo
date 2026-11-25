$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath 'node_modules\electron\dist\electron.exe')) {
    Write-Host 'Please run npm install first. See README.md.'
    exit 1
}
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
& '.\node_modules\electron\dist\electron.exe' .
