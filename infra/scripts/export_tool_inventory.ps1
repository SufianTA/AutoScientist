$repoRoot = Resolve-Path "$PSScriptRoot\..\.."
$env:PYTHONPATH = $repoRoot.Path
Push-Location "$repoRoot\apps\api"
try {
  python -m app.services.tool_inventory_exporter "$repoRoot\tool_inventory.json"
} finally {
  Pop-Location
}

