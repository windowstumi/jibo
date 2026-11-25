param(
    [ValidateSet('setup','start','build','check')][string]$Action = 'setup',
    [ValidateSet('portable','directory')][string]$Target = 'portable',
    [switch]$WithLive2D,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $projectRoot
try {
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
        throw 'The automatic runtime installer supports Windows x64. See README for other platforms.'
    }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $versions = Get-Content -LiteralPath (Join-Path $projectRoot 'runtime.versions.json') -Raw | ConvertFrom-Json
    $runtimeRoot = Join-Path $projectRoot '.runtime'
    $cacheRoot = Join-Path $runtimeRoot 'downloads'
    New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null
    function Get-RangedArchive($Spec, [string]$Url, [string]$Output, [string]$CurlExe) {
        $chunkSize = 1MB
        $chunkCount = [int][Math]::Ceiling($Spec.size / $chunkSize)
        for ($batch = 0; $batch -lt $chunkCount; $batch += 4) {
            $running = @()
            for ($index = $batch; $index -lt [Math]::Min($batch + 4, $chunkCount); $index++) {
                $start = $index * $chunkSize
                $end = [Math]::Min($Spec.size - 1, $start + $chunkSize - 1)
                $chunk = "$Output.$($Spec.sha256.Substring(0,12)).$index"
                $expected = $end - $start + 1
                if ((Test-Path -LiteralPath $chunk) -and (Get-Item -LiteralPath $chunk).Length -eq $expected) { continue }
                $nativeArgs = "--fail --location --silent --show-error --connect-timeout 20 --max-time 180 --header `"Accept: application/octet-stream`" --range $start-$end --output `"$chunk`" `"$Url`""
                $process = Start-Process -FilePath $CurlExe -ArgumentList $nativeArgs -WindowStyle Hidden -PassThru -RedirectStandardError "$chunk.log"
                $null = $process.Handle
                $running += @{ Process=$process; Path=$chunk; Expected=$expected }
            }
            foreach ($job in $running) {
                $job.Process.WaitForExit()
                $job.Process.Refresh()
                if ($job.Process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $job.Path) -or (Get-Item -LiteralPath $job.Path).Length -ne $job.Expected) {
                    throw ("Runtime chunk failed (exit {0}): {1}. Rerun to resume completed chunks." -f $job.Process.ExitCode, $job.Path)
                }
            }
            Write-Host ("Runtime download: {0}/{1} chunks" -f [Math]::Min($batch+4,$chunkCount), $chunkCount)
        }
        $stream = [IO.File]::Create($Output)
        try {
            for ($index=0; $index -lt $chunkCount; $index++) {
                $chunkStream = [IO.File]::OpenRead("$Output.$($Spec.sha256.Substring(0,12)).$index")
                try { $chunkStream.CopyTo($stream) } finally { $chunkStream.Dispose() }
            }
        } finally { $stream.Dispose() }
    }
    function Get-VerifiedArchive($Spec, [string]$Name) {
        $archive = Join-Path $cacheRoot $Name
        if ((Test-Path -LiteralPath $archive) -and (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Spec.sha256) {
            Remove-Item -LiteralPath $archive
        }
        if (-not (Test-Path -LiteralPath $archive)) {
            Write-Host "Downloading $Name (first setup only)..."
            $partial = "$archive.part"
            $urls = @($Spec.url)
            if ($Spec.api_url) { $urls = @($Spec.api_url, $Spec.url) }
            for ($attempt = 0; $attempt -lt $urls.Count; $attempt++) {
                try {
                    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
                    if ($curl -and $Spec.size) {
                        Get-RangedArchive $Spec $urls[$attempt] $partial $curl.Source
                    } elseif ($curl) {
                        & $curl.Source --fail --location --silent --show-error --connect-timeout 20 --max-time 180 --header 'Accept: application/octet-stream' --user-agent 'jibo-bootstrap' --output $partial $urls[$attempt]
                        if ($LASTEXITCODE -ne 0) { throw "Download failed with curl exit code $LASTEXITCODE" }
                    } else {
                        Invoke-WebRequest -Uri $urls[$attempt] -Headers @{Accept='application/octet-stream';'User-Agent'='jibo-bootstrap'} -OutFile $partial -UseBasicParsing -TimeoutSec 120
                    }
                    if ((Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Spec.sha256) {
                        if ($Spec.size) {
                            for ($part=0; $part -lt [Math]::Ceiling($Spec.size / 1MB); $part++) {
                                $badChunk="$partial.$($Spec.sha256.Substring(0,12)).$part"
                                if (Test-Path -LiteralPath $badChunk) { Remove-Item -LiteralPath $badChunk }
                            }
                        }
                        throw "SHA256 verification failed: $Name"
                    }
                    Move-Item -LiteralPath $partial -Destination $archive -Force
                    break
                } catch {
                    if ($attempt -eq ($urls.Count - 1)) { throw }
                    Write-Host 'Download interrupted; trying the alternate official download endpoint.'
                }
            }
        }
        return $archive
    }
    $nodeRoot = Join-Path $runtimeRoot $versions.node.directory
    $nodeExe = Join-Path $nodeRoot 'node.exe'
    if (-not (Test-Path -LiteralPath $nodeExe)) {
        $archive = Get-VerifiedArchive $versions.node 'node.zip'
        Expand-Archive -LiteralPath $archive -DestinationPath $runtimeRoot -Force
    }
    $uvRoot = Join-Path $runtimeRoot ('uv-' + $versions.uv.version)
    if (-not (Test-Path -LiteralPath (Join-Path $uvRoot 'uv.exe'))) {
        $archive = Get-VerifiedArchive $versions.uv 'uv.zip'
        Expand-Archive -LiteralPath $archive -DestinationPath $uvRoot -Force
    }
    $env:PATH = $nodeRoot + [IO.Path]::PathSeparator + $env:PATH
    $arguments = @((Join-Path $PSScriptRoot 'workspace.cjs'), $Action, '--target', $Target)
    if ($WithLive2D) { $arguments += '--with-live2d' }
    if ($Force) { $arguments += '--force' }
    & $nodeExe @arguments
    exit $LASTEXITCODE
} catch {
    Write-Host ("Setup failed: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'No system Python/Node is required. First setup needs access to nodejs.org, GitHub and the package registry.'
    exit 1
}
