$repoRoot = Resolve-Path "$PSScriptRoot\..\.."
$env:PYTHONPATH = $repoRoot.Path
Push-Location "$repoRoot\apps\api"
try {
  python -m app.services.queue_worker
} finally {
  Pop-Location
}

