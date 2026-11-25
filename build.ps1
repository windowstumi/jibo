param([ValidateSet('portable','directory')][string]$Target='portable')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
& '.\.venv\Scripts\python.exe' scripts/build_backend.py
if($LASTEXITCODE -ne 0) {exit $LASTEXITCODE}
if($Target -eq 'portable') {& npm.cmd run dist:win} else {& npm.cmd run pack}
exit $LASTEXITCODE
