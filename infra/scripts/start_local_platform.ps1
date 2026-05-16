$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path "$PSScriptRoot\..\.."
$apiRoot = Resolve-Path "$repoRoot\apps\api"
$frontendRoot = Resolve-Path "$repoRoot\apps\frontend"
$outputRoot = Join-Path $repoRoot.Path "outputs"
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

function Test-PortListening {
  param([int]$Port)
  $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  return $null -ne $connection
}

if (-not (Test-PortListening -Port 8000)) {
  $pythonPath = "$($repoRoot.Path);$($apiRoot.Path)"
  Start-Process powershell -WindowStyle Hidden -WorkingDirectory $apiRoot.Path -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    "`$env:PYTHONPATH='$pythonPath'; `$env:PYTHONUTF8='1'; `$env:PYTHONIOENCODING='utf-8'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 *> '$outputRoot\api_server.log'"
  )
  Write-Host "Started API on http://127.0.0.1:8000"
} else {
  Write-Host "API already listening on http://127.0.0.1:8000"
}

if (-not (Test-PortListening -Port 3000)) {
  Start-Process powershell -WindowStyle Hidden -WorkingDirectory $frontendRoot.Path -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    "npx next dev -H 127.0.0.1 -p 3000 *> '$outputRoot\frontend_server.log'"
  )
  Write-Host "Started frontend on http://127.0.0.1:3000"
} else {
  Write-Host "Frontend already listening on http://127.0.0.1:3000"
}

Start-Sleep -Seconds 3

try {
  $health = Invoke-RestMethod "http://127.0.0.1:8000/health"
  Write-Host "API health:" $health.status
} catch {
  Write-Host "API not ready yet. Check $outputRoot\api_server.log"
}

try {
  $frontendStatus = (Invoke-WebRequest "http://127.0.0.1:3000" -UseBasicParsing).StatusCode
  Write-Host "Frontend status:" $frontendStatus
} catch {
  Write-Host "Frontend not ready yet. Check $outputRoot\frontend_server.log"
}

Write-Host "Open workbench: http://127.0.0.1:3000"
