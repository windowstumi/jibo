param(
    [Parameter(Mandatory=$true)][string]$InputFile,
    [Parameter(Mandatory=$true)][string]$OutputFile,
    [string]$Voice = "",
    [int]$Rate = 0
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$speech = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    if ($Voice) { $speech.SelectVoice($Voice) }
    else {
        $chinese = $speech.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -eq 'zh-CN' } | Select-Object -First 1
        if (-not $chinese) { throw "No Chinese SAPI voice is installed." }
        $speech.SelectVoice($chinese.VoiceInfo.Name)
    }
    $speech.Rate = [Math]::Max(-5, [Math]::Min(5, $Rate))
    $speech.SetOutputToWaveFile($OutputFile)
    $speech.Speak([System.IO.File]::ReadAllText($InputFile, [System.Text.Encoding]::UTF8))
} finally {
    $speech.Dispose()
}
