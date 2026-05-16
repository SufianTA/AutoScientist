$repoRoot = Resolve-Path "$PSScriptRoot\..\.."
$env:PYTHONPATH = $repoRoot.Path
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Push-Location "$repoRoot\apps\api"
try {
  python -m app.services.tool_inventory_exporter "$repoRoot\tool_inventory.json"
} finally {
  Pop-Location
}
