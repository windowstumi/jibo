param(
    [ValidateSet('doctor','generate','build','preview')][string]$Mode = 'doctor',
    [string]$Workspace = '',
    [string]$Source = '',
    [string]$Profile = '',
    [string]$ApiBase = 'https://api.openai.com/v1',
    [string]$Model = 'gpt-image-2',
    [int]$Port = 8768
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'
& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'scripts\bootstrap.ps1') -Action setup -WithLive2D
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$commandArgs = @((Join-Path $PSScriptRoot 'tools\avatar_pipeline\cli.py'), $Mode)
if ($Mode -ne 'doctor') {
    if (-not $Workspace) { throw 'Specify -Workspace <output-directory>.' }
    $commandArgs += @('--workspace', $Workspace)
}
if ($Mode -eq 'generate') {
    if (-not $Source) { throw 'Specify -Source <reference-image>.' }
    $commandArgs += @('--source', $Source, '--api-base', $ApiBase, '--model', $Model)
}
if ($Mode -eq 'build') {
    if (-not $Profile) { throw 'Specify -Profile <calibrated-profile.json>.' }
    $commandArgs += @('--profile', $Profile)
}
if ($Mode -eq 'preview') { $commandArgs += @('--port', "$Port") }
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') @commandArgs
exit $LASTEXITCODE
