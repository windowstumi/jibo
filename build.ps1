param([ValidateSet('portable','directory')][string]$Target='portable')
& (Join-Path $PSScriptRoot 'scripts\bootstrap.ps1') -Action build -Target $Target
exit $LASTEXITCODE
