$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& '.\.venv\Scripts\python.exe' -m pip install -e '.[gpu]'
if ($LASTEXITCODE -ne 0) { throw 'GPU dependency installation failed.' }
& '.\.venv\Scripts\python.exe' -c "from pathlib import Path; from dotenv import set_key; p=Path('.env'); p.touch(exist_ok=True); values={'WHISPER_DEVICE':'cuda','WHISPER_COMPUTE_TYPE':'int8_float16','GPU_DEVICE_INDEX':'0','VIDEO_ENCODER':'h264_nvenc'}; [set_key(str(p), k, v, quote_mode='never') for k,v in values.items()]"
if ($LASTEXITCODE -ne 0) { throw 'Could not save GPU settings.' }
& '.\.venv\Scripts\python.exe' -m cliper doctor
if ($LASTEXITCODE -notin @(0, 2)) { throw 'GPU setup check failed.' }
Write-Host 'GPU profile saved. Review doctor output above; add bot/API keys separately if needed.'
