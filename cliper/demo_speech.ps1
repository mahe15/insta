param([Parameter(Mandatory=$true)][string]$TextPath,
      [Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$clipVoice = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $clipVoice.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSet,
                                [System.Speech.Synthesis.VoiceAge]::NotSet, 0,
                                [System.Globalization.CultureInfo]::GetCultureInfo('en-US'))
    $clipVoice.SetOutputToWaveFile($OutputPath)
    $clipVoice.Speak([System.IO.File]::ReadAllText($TextPath))
} finally {
    $clipVoice.Dispose()
}
