& (Join-Path $PSScriptRoot 'scripts\bootstrap.ps1') -Action start @args
exit $LASTEXITCODE
